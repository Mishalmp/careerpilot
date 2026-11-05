import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.modules.verification.enums import CheckKey, CheckSource, CheckStatus
from careerpilot.modules.verification.models import CompanyCheck


async def list_checks(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID
) -> list[CompanyCheck]:
    rows = await db.scalars(
        select(CompanyCheck).where(
            CompanyCheck.owner_id == owner_id, CompanyCheck.company_id == company_id
        )
    )
    return list(rows)


async def upsert_check(
    db: AsyncSession,
    *,
    owner_id: uuid.UUID,
    company_id: uuid.UUID,
    key: CheckKey,
    status: CheckStatus,
    source: CheckSource,
    evidence_url: str | None,
    evidence_quote: str | None,
    note: str | None,
) -> None:
    """Insert or update one check. An automatic result never replaces a manual one."""
    values = {
        "status": status,
        "source": source,
        "evidence_url": evidence_url,
        "evidence_quote": evidence_quote,
        "note": note,
    }
    statement = insert(CompanyCheck).values(
        owner_id=owner_id, company_id=company_id, key=key, **values
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_company_checks_company_id_key",
        set_={**values, "checked_at": func.now()},
        where=or_(
            CompanyCheck.source != CheckSource.MANUAL,
            statement.excluded.source == CheckSource.MANUAL.value,
        ),
    )
    await db.execute(statement)


async def delete_check(
    db: AsyncSession, owner_id: uuid.UUID, company_id: uuid.UUID, key: CheckKey
) -> bool:
    result = await db.execute(
        delete(CompanyCheck)
        .where(
            CompanyCheck.owner_id == owner_id,
            CompanyCheck.company_id == company_id,
            CompanyCheck.key == key,
        )
        .returning(CompanyCheck.id)
    )
    return result.first() is not None
