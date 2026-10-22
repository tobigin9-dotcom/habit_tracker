from datetime import date, datetime, time, timezone

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)


class User(Base):
    """Registered Telegram user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(120), default="Telegram user")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    habits: Mapped[list["Habit"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Habit(Base):
    """A habit owned by one user."""

    __tablename__ = "habits"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    goal: Mapped[str] = mapped_column(String(255), default="")
    target_completions: Mapped[int] = mapped_column(Integer, default=21)
    completion_count: Mapped[int] = mapped_column(Integer, default=0)
    reminder_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completions: Mapped[list["HabitCompletion"]] = relationship(
        back_populates="habit", cascade="all, delete-orphan"
    )
    owner: Mapped[User] = relationship(back_populates="habits")


class HabitCompletion(Base):
    """Daily completion record for a habit."""

    __tablename__ = "habit_completions"
    __table_args__ = (UniqueConstraint("habit_id", "completion_date", name="uq_habit_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True)
    completion_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    habit: Mapped[Habit] = relationship(back_populates="completions")


class ReminderDelivery(Base):
    """Track reminders already sent for a habit on a date."""

    __tablename__ = "reminder_deliveries"
    __table_args__ = (UniqueConstraint("habit_id", "reminder_date", name="uq_reminder_habit_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    habit_id: Mapped[int] = mapped_column(ForeignKey("habits.id", ondelete="CASCADE"), index=True)
    reminder_date: Mapped[date] = mapped_column(Date, index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
