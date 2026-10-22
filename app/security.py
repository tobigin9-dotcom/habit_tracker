from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models import User

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Return an Argon2 password hash."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(telegram_id: int) -> str:
    """Create a short-lived signed JWT for a Telegram account."""
    expires_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": str(telegram_id), "exp": expires_at, "iat": datetime.now(UTC)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


CredentialsDependency = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: CredentialsDependency,
    session: SessionDependency,
) -> User:
    """Resolve and return the active user represented by a JWT."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        telegram_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise unauthorized from None
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise unauthorized
    return user


def verify_internal_token(token: str | None) -> None:
    """Reject requests that do not carry the internal service token."""
    import secrets

    if not token or not secrets.compare_digest(token, settings.bot_api_token):
        raise HTTPException(
            status_code=401, detail="Invalid internal service token"
        )
