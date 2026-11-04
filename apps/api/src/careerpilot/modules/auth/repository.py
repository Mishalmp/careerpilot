import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.auth.models import AuthSession, User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def list_users(db: AsyncSession, limit: int) -> list[User]:
    return list((await db.scalars(select(User).order_by(User.created_at).limit(limit))).all())


async def add_user(db: AsyncSession, email: str, password_hash: str) -> User:
    user = User(email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user


async def add_session(
    db: AsyncSession, user_id: uuid.UUID, token_hash: str, csrf_token: str, expires_at: datetime
) -> AuthSession:
    session = AuthSession(
        user_id=user_id, token_hash=token_hash, csrf_token=csrf_token, expires_at=expires_at
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def get_live_session(db: AsyncSession, token_hash: str, now: datetime) -> AuthSession | None:
    return await db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash, AuthSession.expires_at > now
        )
    )


async def delete_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.id == session_id))


async def delete_expired_sessions(db: AsyncSession, now: datetime) -> None:
    await db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
