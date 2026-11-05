import uuid
from collections.abc import Iterable
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.evidence import quote_appears
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmClient
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.verification import repository
from careerpilot.modules.verification.autochecks import (
    CheckResult,
    run_auto_checks,
    website_host,
)
from careerpilot.modules.verification.enums import (
    CHECKS,
    FLAGS,
    CheckKey,
    CheckSource,
    CheckStatus,
)
from careerpilot.modules.verification.models import CompanyCheck
from careerpilot.modules.verification.pagereview import gather_pages, review_pages
from careerpilot.modules.verification.rules import compute_verdict, scan_job_text
from careerpilot.modules.verification.schemas import NOTICE, CheckOut, CheckUpdate, VerificationOut


async def get_verification(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, *, ai_available: bool
) -> VerificationOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    stored = {c.key: c for c in await repository.list_checks(db, owner_id, job.company_id)}
    verdict = compute_verdict({key: check.status for key, check in stored.items()})
    return VerificationOut(
        job_id=job.id,
        company_name=job.company.name,
        website=job.company.website,
        verdict=verdict.label,
        passed=verdict.passed,
        total=len(CHECKS),
        raised_flags=list(verdict.raised_flags),
        needs_review=verdict.label.value != "verified",
        notice=NOTICE,
        ai_available=ai_available,
        checks=[_check_out(key, stored.get(key)) for key in (*CHECKS, *FLAGS)],
    )


def _check_out(key: CheckKey, row: CompanyCheck | None) -> CheckOut:
    kind = "flag" if key in FLAGS else "check"
    if row is None:
        return CheckOut(
            key=key,
            kind=kind,
            status=CheckStatus.UNKNOWN,
            source=None,
            evidence_url=None,
            evidence_quote=None,
            note=None,
            checked_at=None,
        )
    return CheckOut(
        key=key,
        kind=kind,
        status=row.status,
        source=row.source,
        evidence_url=row.evidence_url,
        evidence_quote=row.evidence_quote,
        note=row.note,
        checked_at=row.checked_at,
    )


async def _save(
    db: AsyncSession,
    owner_id: uuid.UUID,
    company_id: uuid.UUID,
    results: Iterable[CheckResult],
    source: CheckSource,
) -> None:
    for result in results:
        await repository.upsert_check(
            db,
            owner_id=owner_id,
            company_id=company_id,
            key=result.key,
            status=result.status,
            source=source,
            evidence_url=result.evidence_url,
            evidence_quote=result.evidence_quote,
            note=result.note,
        )


async def run(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    fetcher: Fetcher,
    llm: LlmClient | None,
    settings: Settings,
    today: date,
    use_ai: bool,
) -> VerificationOut:
    """Look the company up, scan the job text, and (optionally) have the model read its pages.

    Safe to repeat: results are upserted, and anything you set by hand is left alone.
    """
    job = await tracker_service.get_job(db, owner_id, job_id)
    company_id, website = job.company_id, job.company.website

    await _save(
        db, owner_id, company_id, await run_auto_checks(fetcher, website, today), CheckSource.AUTO
    )

    # Red flags only ever get raised automatically. Clearing one is your decision.
    if job.jd_text:
        flags = scan_job_text(job.jd_text)
        raised = (
            CheckResult(key, CheckStatus.FAIL, "Stated in the job description.", job.jd_url, quote)
            for key, quote in flags.items()
        )
        await _save(db, owner_id, company_id, raised, CheckSource.AUTO)

    await db.commit()  # keep the lookups even if the model step below fails or is capped

    host = website_host(website)
    if use_ai and llm is not None and host is not None:
        pages = await gather_pages(fetcher, host)
        if pages.texts:
            _, results = await review_pages(db, owner_id, llm, settings, pages)
            await _save(db, owner_id, company_id, results, CheckSource.AI)

    await db.commit()
    return await get_verification(db, owner_id, job_id, ai_available=llm is not None)


async def set_check(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    key: CheckKey,
    data: CheckUpdate,
    *,
    fetcher: Fetcher,
    ai_available: bool,
) -> VerificationOut:
    """Record your own finding. A quote is only saved if it is on the page you point to."""
    job = await tracker_service.get_job(db, owner_id, job_id)
    if data.evidence_quote and not data.evidence_url:
        raise ProblemError(422, "A quote needs a page", "Give the page address the quote is from.")
    if data.evidence_quote and data.evidence_url:
        try:
            page = await fetcher.fetch(data.evidence_url)
        except FetchError as exc:
            raise ProblemError(422, "That page could not be read", exc.message) from exc
        if not quote_appears(data.evidence_quote, page.text):
            raise ProblemError(
                422,
                "Quote not found on that page",
                "The quote must be copied exactly from the page. Check the address and the text.",
            )
    await repository.upsert_check(
        db,
        owner_id=owner_id,
        company_id=job.company_id,
        key=key,
        status=data.status,
        source=CheckSource.MANUAL,
        evidence_url=data.evidence_url,
        evidence_quote=data.evidence_quote,
        note=data.note,
    )
    await db.commit()
    return await get_verification(db, owner_id, job_id, ai_available=ai_available)


async def clear_check(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    key: CheckKey,
    *,
    ai_available: bool,
) -> VerificationOut:
    """Remove a check so the next automatic run can fill it in again."""
    job = await tracker_service.get_job(db, owner_id, job_id)
    await repository.delete_check(db, owner_id, job.company_id, key)
    await db.commit()
    return await get_verification(db, owner_id, job_id, ai_available=ai_available)
