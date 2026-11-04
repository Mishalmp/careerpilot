from enum import StrEnum

from sqlalchemy import Enum, MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Store a StrEnum as text with a CHECK constraint (native PG enums are painful to migrate)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=_enum_values,
    )


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
