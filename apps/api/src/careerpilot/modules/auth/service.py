from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.security import (
    DUMMY_HASH,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)
from careerpilot.modules.auth import repository
from careerpilot.modules.auth.models import AuthSession, User
from careerpilot.modules.auth.throttle import LoginThrottle

MIN_PASSWORD_LENGTH = 12


class UserExistsError(Exception):
    pass


@dataclass(frozen=True)
class LoginResult:
    token: str
    session: AuthSession


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def create_user(db: AsyncSession, email: str, password: str) -> User:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
    try:
        user = await repository.add_user(db, normalize_email(email), await hash_password(password))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise UserExistsError(email) from exc
    return user


async def authenticate(
    db: AsyncSession,
    throttle: LoginThrottle,
    settings: Settings,
    email: str,
    password: str,
) -> LoginResult:
    key = normalize_email(email)
    throttle.check(key)

    user = await repository.get_user_by_email(db, key)
    password_ok = await verify_password(user.password_hash if user else DUMMY_HASH, password)
    if user is None or not password_ok:
        throttle.record_failure(key)
        raise ProblemError(401, "Invalid credentials")
    throttle.reset(key)

    now = datetime.now(UTC)
    await repository.delete_expired_sessions(db, now)
    token = new_token()
    session = await repository.add_session(
        db,
        user.id,
        hash_token(token),
        new_token(),
        now + timedelta(hours=settings.session_ttl_hours),
    )
    await db.commit()
    return LoginResult(token=token, session=session)


async def get_live_session(db: AsyncSession, token: str) -> AuthSession | None:
    return await repository.get_live_session(db, hash_token(token), datetime.now(UTC))


async def logout(db: AsyncSession, session: AuthSession) -> None:
    await repository.delete_session(db, session.id)
    await db.commit()
