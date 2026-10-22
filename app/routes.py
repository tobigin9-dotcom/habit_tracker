from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import Habit, HabitCompletion, ReminderDelivery, User
from app.schemas import (
    CompletionRequest,
    CompletionResponse,
    DueReminder,
    HabitCreate,
    HabitResponse,
    HabitStatsResponse,
    HabitUpdate,
    RegisterRequest,
    TokenRequest,
    TokenResponse,
    UserResponse,
)
from app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_internal_token,
    verify_password,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/auth/register", response_model=TokenResponse, status_code=201)
async def register_user(payload: RegisterRequest, session: SessionDependency):
    """Create a user and return a JWT."""
    existing = await session.scalar(
        select(User).where(User.telegram_id == payload.telegram_id)
    )
    if existing:
        raise HTTPException(
            status_code=409, detail="Telegram account is already registered"
        )
    user = User(
        telegram_id=payload.telegram_id,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    await session.commit()
    return TokenResponse(access_token=create_access_token(user.telegram_id))


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(payload: TokenRequest, session: SessionDependency):
    """Authenticate a user and issue a JWT."""
    user = await session.scalar(
        select(User).where(User.telegram_id == payload.telegram_id)
    )
    if user is None or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(
            status_code=401, detail="Incorrect Telegram ID or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    return TokenResponse(access_token=create_access_token(user.telegram_id))


@router.get("/users/me", response_model=UserResponse)
async def get_user_profile(user: CurrentUser):
    """Return the authenticated user's public profile."""
    return user


@router.get("/habits", response_model=list[HabitResponse])
async def list_habits(
    user: CurrentUser,
    session: SessionDependency,
    active_only: Annotated[bool, Query()] = True,
):
    """List the current user's habits."""
    query = select(Habit).where(Habit.owner_id == user.id)
    if active_only:
        query = query.where(Habit.is_active.is_(True))
    result = await session.scalars(query.order_by(Habit.id))
    return list(result.all())


@router.post("/habits", response_model=HabitResponse, status_code=201)
async def create_habit(
    payload: HabitCreate, user: CurrentUser, session: SessionDependency
):
    """Create a habit for the authenticated user."""
    if not payload.name.strip():
        raise HTTPException(
            status_code=422, detail="Habit name cannot be blank"
        )
    habit = Habit(
        owner_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
        goal=payload.goal,
        target_completions=payload.target_completions,
        reminder_time=payload.reminder_time,
    )
    session.add(habit)
    await session.commit()
    await session.refresh(habit)
    return habit


async def get_owned_habit(
    habit_id: int, user_id: int, session: AsyncSession
) -> Habit:
    """Return a habit only if it belongs to the given user."""
    habit = await session.scalar(
        select(Habit).where(Habit.id == habit_id, Habit.owner_id == user_id)
    )
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit


@router.get("/habits/{habit_id}", response_model=HabitResponse)
async def get_habit(
    habit_id: int, user: CurrentUser, session: SessionDependency
):
    """Get one owned habit."""
    return await get_owned_habit(habit_id, user.id, session)


@router.patch("/habits/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: int,
    payload: HabitUpdate,
    user: CurrentUser,
    session: SessionDependency,
):
    """Update fields of an owned habit."""
    habit = await get_owned_habit(habit_id, user.id, session)
    for field_name, field_value in payload.model_dump(
        exclude_unset=True
    ).items():
        setattr(habit, field_name, field_value)
    await session.commit()
    await session.refresh(habit)
    return habit


@router.delete("/habits/{habit_id}", status_code=204)
async def delete_habit(
    habit_id: int, user: CurrentUser, session: SessionDependency
):
    """Delete an owned habit and its completion history."""
    habit = await get_owned_habit(habit_id, user.id, session)
    await session.delete(habit)
    await session.commit()


@router.post(
    "/habits/{habit_id}/completion", response_model=CompletionResponse
)
async def record_completion(
    habit_id: int,
    payload: CompletionRequest,
    user: CurrentUser,
    session: SessionDependency,
    completion_date: Annotated[
        date,
        Query(
            default_factory=lambda: datetime.now(
                ZoneInfo(settings.timezone)
            ).date()
        ),
    ],
):
    """Set today's state; repeated requests update rather than duplicate."""
    habit = await get_owned_habit(habit_id, user.id, session)
    completion = await session.scalar(
        select(HabitCompletion).where(
            HabitCompletion.habit_id == habit.id,
            HabitCompletion.completion_date == completion_date,
        )
    )
    previous_state = completion.is_completed if completion else False
    if completion is None:
        completion = HabitCompletion(
            habit_id=habit.id,
            completion_date=completion_date,
            is_completed=payload.is_completed,
        )
        session.add(completion)
    else:
        completion.is_completed = payload.is_completed
    if payload.is_completed and not previous_state:
        habit.completion_count += 1
    elif previous_state and not payload.is_completed:
        habit.completion_count = max(0, habit.completion_count - 1)
    if habit.completion_count >= habit.target_completions:
        habit.is_active = False
    elif habit.completion_count < habit.target_completions:
        habit.is_active = True
    await session.commit()
    return CompletionResponse(
        habit_id=habit.id,
        completion_date=completion_date,
        is_completed=payload.is_completed,
        completion_count=habit.completion_count,
    )


@router.get("/habits/{habit_id}/stats", response_model=HabitStatsResponse)
async def get_habit_stats(
    habit_id: int, user: CurrentUser, session: SessionDependency
):
    """Return completion statistics for an owned habit."""
    habit = await get_owned_habit(habit_id, user.id, session)
    total_days = (
        await session.scalar(
            select(func.count(HabitCompletion.id)).where(
                HabitCompletion.habit_id == habit.id
            )
        )
        or 0
    )
    completed_days = (
        await session.scalar(
            select(func.count(HabitCompletion.id)).where(
                HabitCompletion.habit_id == habit.id,
                HabitCompletion.is_completed.is_(True),
            )
        )
        or 0
    )
    return HabitStatsResponse(
        habit_id=habit.id,
        name=habit.name,
        target_completions=habit.target_completions,
        completion_count=habit.completion_count,
        remaining_completions=max(
            0, habit.target_completions - habit.completion_count
        ),
        total_recorded_days=total_days,
        completed_days=completed_days,
        completion_rate_percent=round(completed_days / total_days * 100, 1)
        if total_days
        else 0.0,
    )


def require_internal_service(
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticate the internal reminder worker."""
    verify_internal_token(x_internal_token)


@router.get("/internal/reminders/due", response_model=list[DueReminder])
async def list_due_reminders(
    session: SessionDependency,
    _: Annotated[None, Depends(require_internal_service)],
):
    """List habits due now without completion or reminder today."""
    now = datetime.now(ZoneInfo(settings.timezone))
    local_date = now.date()
    local_time = now.time().replace(tzinfo=None, second=0, microsecond=0)
    habits = (
        await session.scalars(
            select(Habit, User.telegram_id)
            .join(User, User.id == Habit.owner_id)
            .where(
                Habit.is_active.is_(True), Habit.reminder_time <= local_time
            )
        )
    ).all()
    due_items = []
    for habit, telegram_id in habits:
        already_sent = await session.scalar(
            select(ReminderDelivery.id).where(
                ReminderDelivery.habit_id == habit.id,
                ReminderDelivery.reminder_date == local_date,
            )
        )
        if already_sent:
            continue
        completion = await session.scalar(
            select(HabitCompletion).where(
                HabitCompletion.habit_id == habit.id,
                HabitCompletion.completion_date == local_date,
                HabitCompletion.is_completed.is_(True),
            )
        )
        due_items.append(
            DueReminder(
                habit_id=habit.id,
                telegram_id=telegram_id,
                name=habit.name,
                description=habit.description,
                is_completed_today=completion is not None,
            )
        )
    return due_items


@router.post("/internal/reminders/{habit_id}/sent", status_code=204)
async def record_reminder_sent(
    habit_id: int,
    session: SessionDependency,
    _: Annotated[None, Depends(require_internal_service)],
):
    """Record that a reminder was sent for this habit today."""
    from sqlalchemy.dialects.postgresql import insert

    statement = (
        insert(ReminderDelivery)
        .values(
            habit_id=habit_id,
            reminder_date=datetime.now(ZoneInfo(settings.timezone)).date(),
            sent_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["habit_id", "reminder_date"])
    )
    await session.execute(statement)
    await session.commit()
