import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.evidence import normalize
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmClient, call_llm_json
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.modules.knowledge import service as knowledge_service
from careerpilot.modules.knowledge.embeddings import Embedder
from careerpilot.modules.outreach import repository
from careerpilot.modules.outreach.enums import Channel, OutreachStatus
from careerpilot.modules.outreach.lint import LintResult, lint
from careerpilot.modules.outreach.models import OutreachDraft
from careerpilot.modules.outreach.schemas import (
    DraftCreate,
    DraftEdit,
    DraftOut,
    FactIn,
    GenerateRequest,
    LintOut,
    Move,
    OutreachList,
    RawVariants,
)
from careerpilot.modules.outreach.workflow import can_move
from careerpilot.modules.tracker import service as tracker_service
from careerpilot.modules.tracker.enums import ContactKind, EmailMode
from careerpilot.modules.tracker.schemas import ApplicationUpdate
from careerpilot.modules.tracker.service import Contact, Job
from careerpilot.modules.verification import service as verification_service
from careerpilot.modules.verification.enums import VerdictLabel

FOLLOW_UP_AFTER_DAYS = 6
MAX_JD_CHARS = 4000
MAX_NOTE_CHARS = 600
PROOF_POINTS = 2


def _conflict(title: str, detail: str, **extra: Any) -> ProblemError:
    return ProblemError(409, title, detail, **extra)


def _out(draft: OutreachDraft) -> DraftOut:
    return DraftOut.model_validate(draft)


# --- reading -------------------------------------------------------------------------------


async def list_drafts(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, settings: Settings, today: date
) -> OutreachList:
    await tracker_service.get_job(db, owner_id, job_id)
    drafts = await repository.list_for_job(db, owner_id, job_id)
    return OutreachList(
        items=[_out(d) for d in drafts],
        approved_today=await repository.approved_since(db, owner_id, _day_start(today, settings)),
        daily_cap=settings.outreach_daily_cap,
    )


def _day_start(today: date, settings: Settings) -> datetime:
    return datetime.combine(today, time.min, tzinfo=ZoneInfo(settings.timezone)).astimezone(UTC)


# --- making drafts -------------------------------------------------------------------------


def _recipient(job: Job, contact_id: uuid.UUID | None, channel: Channel) -> Contact | None:
    """The contact to write to. An email needs an address the company published (or a referral)."""
    contact = None
    if contact_id is not None:
        contact = next((c for c in job.company.contacts if c.id == contact_id), None)
        if contact is None:
            raise ProblemError(422, "Unknown contact", "That contact does not belong to this job.")
    if channel is Channel.EMAIL:
        if contact is None or not contact.email:
            raise ProblemError(
                422, "An email needs a recipient", "Pick a contact that has an email address."
            )
        if contact.kind is not ContactKind.REFERRAL and not contact.source_url:
            raise ProblemError(
                422,
                "Where is this address published?",
                "Add the page where the company publishes it to the contact, or mark the contact "
                "as a referral. CareerPilot only drafts to addresses with a known source.",
            )
    return contact


async def _lint(
    db: AsyncSession, owner_id: uuid.UUID, job: Job, draft: OutreachDraft
) -> LintResult:
    others = await repository.other_bodies(db, owner_id, draft.job_id)
    return lint(
        draft.body,
        subject=draft.subject,
        company=job.company.name,
        facts=draft.facts,
        channel=draft.channel,
        others=others,
    )


def _store_lint(draft: OutreachDraft, result: LintResult) -> None:
    draft.lint = LintOut(words=result.words, flags=result.flags).model_dump()


async def create_manual(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, data: DraftCreate
) -> DraftOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    contact = _recipient(job, data.contact_id, data.channel)
    draft = repository.add(
        db,
        owner_id,
        job_id=job_id,
        contact_id=contact.id if contact else None,
        channel=data.channel,
        status=OutreachStatus.DRAFT,
        variant="manual",
        subject=data.subject,
        body=data.body,
        recipient_email=contact.email if contact else None,
        recipient_source_url=contact.source_url if contact else None,
        facts=data.facts,
        lint={},
    )
    _store_lint(draft, await _lint(db, owner_id, job, draft))
    await db.commit()
    await db.refresh(draft)
    return _out(draft)


async def _check_fact(fact: FactIn, jd_text: str | None, fetcher: Fetcher) -> None:
    """A fact must be in the job description, or on the page you say it came from."""
    wanted = normalize(fact.text)
    if jd_text and wanted in normalize(jd_text):
        return
    if fact.source_url is None:
        raise ProblemError(
            422,
            "Where is that fact from?",
            f"'{fact.text}' is not in the job description. Give the page it comes from.",
        )
    try:
        page = await fetcher.fetch(fact.source_url)
    except FetchError as exc:
        raise ProblemError(422, "That page could not be read", exc.message) from exc
    if wanted not in normalize(page.text):
        raise ProblemError(
            422,
            "Fact not found on that page",
            f"'{fact.text}' does not appear on {fact.source_url}. "
            "Use the page's own words, or pick another fact.",
        )


async def _proof_points(
    db: AsyncSession,
    owner_id: uuid.UUID,
    embedder: Embedder,
    settings: Settings,
    job: Job,
) -> list[str]:
    """Passages from your own notes that match the role. None if the notes do not cover it."""
    query = f"{job.title}. {(job.jd_text or '')[:400]}"
    found = await knowledge_service.search(
        db, owner_id, embedder, settings, query, limit=PROOF_POINTS
    )
    if not found.confident:
        return []
    return [hit.text[:MAX_NOTE_CHARS] for hit in found.hits[:PROOF_POINTS]]


async def generate(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    data: GenerateRequest,
    *,
    settings: Settings,
    llm: LlmClient | None,
    fetcher: Fetcher,
    embedder: Embedder,
) -> list[DraftOut]:
    """Two variants written by the model from facts you checked and notes that are yours."""
    if llm is None:
        raise _conflict(
            "Drafting needs an API key",
            "Set ANTHROPIC_API_KEY to let the model draft, or write the draft yourself.",
        )
    job = await tracker_service.get_job(db, owner_id, job_id)
    contact = _recipient(job, data.contact_id, data.channel)
    for fact in data.facts:
        await _check_fact(fact, job.jd_text, fetcher)

    notes = await _proof_points(db, owner_id, embedder, settings, job)
    lines = [
        f"Channel: {data.channel.value}",
        f"Role: {job.title} at {job.company.name}",
        f"Sender first name: {data.sender_name}",
    ]
    if data.constraint:
        lines.append(f"Constraint to mention: {data.constraint}")
    lines.append("Facts to include word for word:")
    lines.extend(f"- {fact.text}" for fact in data.facts)
    sections = ["\n".join(lines)]
    if job.jd_text:
        sections.append(data_block("job_description", job.jd_text[:MAX_JD_CHARS]))
    sections.append(
        data_block("notes", "\n\n".join(f"[{n}] {t}" for n, t in enumerate(notes, 1)))
        if notes
        else "No notes about the sender's work are available. Make no claim about past work."
    )

    prompt = load_prompt(settings.prompts_dir, "outreach-draft", 1)
    raw = await call_llm_json(
        db,
        owner_id,
        llm,
        settings,
        prompt=prompt,
        user="\n\n".join(sections),
        schema=RawVariants,
    )

    drafts: list[OutreachDraft] = []
    for label, variant in zip("AB", raw.variants, strict=False):
        draft = repository.add(
            db,
            owner_id,
            job_id=job_id,
            contact_id=contact.id if contact else None,
            channel=data.channel,
            status=OutreachStatus.DRAFT,
            variant=label,
            subject=variant.subject,
            body=variant.body,
            recipient_email=contact.email if contact else None,
            recipient_source_url=contact.source_url if contact else None,
            facts=[fact.text for fact in data.facts],
            lint={},
        )
        _store_lint(draft, await _lint(db, owner_id, job, draft))
        drafts.append(draft)
    await db.commit()
    for draft in drafts:
        await db.refresh(draft)
    return [_out(d) for d in drafts]


# --- changing drafts -----------------------------------------------------------------------


async def _get_draft(
    db: AsyncSession, owner_id: uuid.UUID, draft_id: uuid.UUID, *, lock: bool = False
) -> OutreachDraft:
    draft = await repository.get(db, owner_id, draft_id, lock=lock)
    if draft is None:
        raise ProblemError(404, "Not found", "Draft not found.")
    return draft


async def edit(
    db: AsyncSession, owner_id: uuid.UUID, draft_id: uuid.UUID, data: DraftEdit
) -> DraftOut:
    draft = await _get_draft(db, owner_id, draft_id, lock=True)
    if draft.status is not OutreachStatus.DRAFT:
        raise _conflict("Only a draft can be edited", "Move it back to draft first.")
    for field in data.model_fields_set:
        setattr(draft, field, getattr(data, field))
    job = await tracker_service.get_job(db, owner_id, draft.job_id)
    _store_lint(draft, await _lint(db, owner_id, job, draft))
    await db.commit()
    await db.refresh(draft)
    return _out(draft)


async def delete(db: AsyncSession, owner_id: uuid.UUID, draft_id: uuid.UUID) -> None:
    draft = await _get_draft(db, owner_id, draft_id, lock=True)
    if draft.status in (OutreachStatus.APPROVED, OutreachStatus.SENT):
        raise _conflict("Approved and sent messages are kept", "Reject an approved draft instead.")
    await repository.delete_draft(db, owner_id, draft_id)
    await db.commit()


async def move(
    db: AsyncSession,
    owner_id: uuid.UUID,
    draft_id: uuid.UUID,
    data: Move,
    *,
    settings: Settings,
    today: date,
) -> DraftOut:
    draft = await _get_draft(db, owner_id, draft_id, lock=True)
    if not can_move(draft.status, data.status):
        raise _conflict(
            "That move is not allowed",
            f"A {draft.status.value} message cannot become {data.status.value}.",
        )
    job = await tracker_service.get_job(db, owner_id, draft.job_id)

    if data.status is OutreachStatus.APPROVED:
        await _check_can_approve(db, owner_id, job, draft, data, settings, today)
        draft.approved_at = datetime.now(UTC)
        await repository.reject_sibling_drafts(db, owner_id, draft)
    elif data.status is OutreachStatus.SENT:
        draft.sent_at = datetime.now(UTC)
    elif data.status is OutreachStatus.DRAFT:
        draft.approved_at = None
    draft.status = data.status

    try:
        await db.commit()
    except IntegrityError as exc:  # two approvals racing for the same role
        await db.rollback()
        raise _conflict(
            "This role already has an approved or sent message",
            "Only one message per role and channel.",
        ) from exc
    await db.refresh(draft)

    if draft.channel is Channel.EMAIL and data.status in (
        OutreachStatus.APPROVED,
        OutreachStatus.SENT,
    ):
        mode = EmailMode.DRAFT_READY if data.status is OutreachStatus.APPROVED else EmailMode.SENT
        update = ApplicationUpdate(email_mode=mode)
        if data.status is OutreachStatus.SENT and job.application.next_followup_on is None:
            update.next_followup_on = today + timedelta(days=FOLLOW_UP_AFTER_DAYS)
        await tracker_service.update_application(db, owner_id, job.application.id, update)
    return _out(draft)


async def _check_can_approve(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job: Job,
    draft: OutreachDraft,
    data: Move,
    settings: Settings,
    today: date,
) -> None:
    result = await _lint(db, owner_id, job, draft)
    _store_lint(draft, result)
    if result.flags and not data.acknowledge_flags:
        raise _conflict(
            "Read the lint flags first",
            "This draft still has flags. Fix them, or approve again with acknowledge_flags set.",
            flags=result.flags,
        )
    if draft.channel is Channel.EMAIL and not draft.recipient_email:
        raise _conflict("No recipient", "An email needs a contact with an address.")

    verification = await verification_service.get_verification(
        db, owner_id, job.id, ai_available=False
    )
    checked = any(check.source is not None for check in verification.checks)
    if checked and verification.verdict is VerdictLabel.SUSPICIOUS:
        raise _conflict(
            "The company looks suspicious",
            "Review its verification before reaching out. If you have good reason to trust it, "
            "record your own finding on the failing checks.",
        )

    existing = await repository.active_for_job(db, owner_id, draft.job_id, draft.channel)
    if existing is not None and existing.id != draft.id:
        raise _conflict(
            "This role already has an approved or sent message",
            "Only one message per role and channel. Reject the other one first.",
        )
    used = await repository.approved_since(db, owner_id, _day_start(today, settings))
    if used >= settings.outreach_daily_cap:
        raise ProblemError(
            429,
            "Daily outreach limit reached",
            f"{used} messages were approved today; the limit is {settings.outreach_daily_cap}. "
            "Small volumes keep outreach personal.",
        )
