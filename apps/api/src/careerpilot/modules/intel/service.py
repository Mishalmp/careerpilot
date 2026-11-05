import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.evidence import normalize, quote_appears
from careerpilot.core.fetcher import Fetcher, FetchError
from careerpilot.core.llm import LlmClient, call_llm_json
from careerpilot.core.prompts import data_block, load_prompt
from careerpilot.modules.intel import repository
from careerpilot.modules.intel.enums import ItemKind, SourceKind
from careerpilot.modules.intel.models import IntelItem, IntelSource
from careerpilot.modules.intel.rules import (
    ItemFacts,
    RankedItem,
    build_brief,
    matching_prep_topics,
    normalize_key,
)
from careerpilot.modules.intel.schemas import (
    BriefOut,
    ExtractOut,
    IntelOut,
    IntelTopicOut,
    ItemOut,
    PeerOut,
    PeersOut,
    QuestionsOut,
    RawItems,
    RawPeers,
    RawQuestions,
    SourceCreate,
    SourceOut,
)
from careerpilot.modules.prep import service as prep_service
from careerpilot.modules.tracker import service as tracker_service

MAX_SOURCE_CHARS = 20_000
SHOWN_TO_MODEL = 12_000
MAX_ITEM_TEXT = 300
MAX_QUOTE = 300


def _same_company(a: str, b: str) -> bool:
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def _need_llm(llm: LlmClient | None) -> LlmClient:
    if llm is None:
        raise ProblemError(
            409, "Needs an API key", "Set ANTHROPIC_API_KEY to use the model for this step."
        )
    return llm


def _source_out(source: IntelSource, company_name: str, item_count: int) -> SourceOut:
    return SourceOut(
        id=source.id,
        kind=source.kind,
        label=source.label,
        url=source.url,
        about_company=source.about_company,
        inferred=not _same_company(source.about_company, company_name),
        published_on=source.published_on,
        item_count=item_count,
        characters=len(source.text),
    )


# --- reading -------------------------------------------------------------------------------


async def get_intel(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, *, today: date, ai_available: bool
) -> IntelOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    company = job.company
    sources = await repository.list_sources(db, owner_id, company.id)
    items: Sequence[IntelItem] = []
    if sources:
        items = await repository.list_items(db, owner_id, [s.id for s in sources])
    by_source = {s.id: s for s in sources}
    inferred = {s.id: not _same_company(s.about_company, company.name) for s in sources}

    facts = [
        ItemFacts(
            id=i.id,
            source_id=i.source_id,
            kind=i.kind,
            key=i.key,
            text=i.text,
            quote=i.quote,
            published_on=by_source[i.source_id].published_on,
            inferred=inferred[i.source_id],
        )
        for i in items
    ]
    own = [(s.id, s.published_on) for s in sources if not inferred[s.id]]
    brief = build_brief(facts, own, today)

    prep = [
        (t.title, t.area)
        for t in await prep_service.list_topics(db, owner_id, area=None, status=None, due_on=None)
    ]

    def item_out(ranked: RankedItem) -> ItemOut:
        item, source = ranked.facts, by_source[ranked.facts.source_id]
        return ItemOut(
            id=item.id,
            kind=item.kind,
            key=item.key,
            text=item.text,
            quote=item.quote,
            source_id=source.id,
            source_label=source.label,
            source_url=source.url,
            published_on=source.published_on,
            inferred=item.inferred,
            similar_to=source.about_company if item.inferred else None,
            reliability=ranked.reliability,
        )

    counts = {s.id: sum(1 for i in items if i.source_id == s.id) for s in sources}
    return IntelOut(
        job_id=job.id,
        company_name=company.name,
        sources=[_source_out(s, company.name, counts[s.id]) for s in sources],
        brief=BriefOut(
            rounds=[item_out(r) for r in brief.rounds],
            topics=[
                IntelTopicOut(
                    key=t.key,
                    sources=t.sources,
                    reliability=t.reliability,
                    inferred_only=t.inferred_only,
                    prep_topics=matching_prep_topics(t.key, prep),
                )
                for t in brief.topics
            ],
            likely_questions=[item_out(r) for r in brief.likely_questions],
            tips=[item_out(r) for r in brief.tips],
            own_recent_sources=brief.own_recent_sources,
            needs_more_sources=brief.needs_more_sources,
        ),
        ai_available=ai_available,
    )


# --- sources -------------------------------------------------------------------------------


async def add_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    data: SourceCreate,
    *,
    fetcher: Fetcher,
    llm: LlmClient | None,
    settings: Settings,
) -> ExtractOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    if data.text:
        kind, text, url = SourceKind.PASTED, data.text, data.url
    elif data.url:
        try:
            page = await fetcher.fetch(data.url)
        except FetchError as exc:
            raise ProblemError(422, "That page could not be read", exc.message) from exc
        if len(page.text) < 40:
            raise ProblemError(422, "That page has almost no text", "There is nothing to read.")
        kind, text, url = SourceKind.FETCHED, page.text, page.url
    else:
        raise ProblemError(422, "Nothing to read", "Give the text you copied or a page address.")
    source = repository.add_source(
        db,
        owner_id,
        company_id=job.company_id,
        kind=kind,
        label=data.label,
        url=url,
        about_company=data.about_company or job.company.name,
        published_on=data.published_on,
        text=text[:MAX_SOURCE_CHARS],
    )
    await db.flush()
    if llm is None:
        await db.commit()
        return ExtractOut(source=_source_out(source, job.company.name, 0), kept=0, dropped=0)
    return await _extract(db, owner_id, source, job.company.name, llm, settings)


async def extract_source(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    source_id: uuid.UUID,
    *,
    llm: LlmClient | None,
    settings: Settings,
) -> ExtractOut:
    """Read a source again (for example after the prompt improved). Replaces its items."""
    job = await tracker_service.get_job(db, owner_id, job_id)
    source = await repository.get_source(db, owner_id, job.company_id, source_id)
    if source is None:
        raise ProblemError(404, "Not found", "Source not found.")
    return await _extract(db, owner_id, source, job.company.name, _need_llm(llm), settings)


async def _extract(
    db: AsyncSession,
    owner_id: uuid.UUID,
    source: IntelSource,
    company_name: str,
    llm: LlmClient,
    settings: Settings,
) -> ExtractOut:
    shown = source.text[:SHOWN_TO_MODEL]
    prompt = load_prompt(settings.prompts_dir, "intel-extract", 1)
    try:
        raw = await call_llm_json(
            db,
            owner_id,
            llm,
            settings,
            prompt=prompt,
            user=f"The source is about: {source.about_company}\n\n{data_block('source', shown)}",
            schema=RawItems,
        )
    except ProblemError:
        await db.commit()  # keep the source even when reading it failed; it can be retried
        raise

    kept: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw.items:
        text, quote = item.text.strip()[:MAX_ITEM_TEXT], item.quote.strip()
        marker = (item.kind, normalize(text))
        if marker in seen or not quote_appears(quote, shown) or len(quote) > MAX_QUOTE:
            continue
        seen.add(marker)
        kept.append(
            {
                "kind": ItemKind(item.kind),
                "key": normalize_key(item.key),
                "text": text,
                "quote": quote,
            }
        )
    await repository.replace_items(db, owner_id, source.id, kept)
    await db.commit()
    return ExtractOut(
        source=_source_out(source, company_name, len(kept)),
        kept=len(kept),
        dropped=len(raw.items) - len(kept),
    )


async def delete_source(
    db: AsyncSession, owner_id: uuid.UUID, job_id: uuid.UUID, source_id: uuid.UUID
) -> None:
    job = await tracker_service.get_job(db, owner_id, job_id)
    if not await repository.delete_source(db, owner_id, job.company_id, source_id):
        raise ProblemError(404, "Not found", "Source not found.")
    await db.commit()


# --- suggestions (not facts) ---------------------------------------------------------------


async def suggest_peers(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    llm: LlmClient | None,
    settings: Settings,
) -> PeersOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    details = [f"Company: {job.company.name}", f"Role: {job.title}"]
    if job.company.country:
        details.append(f"Country: {job.company.country}")
    if job.company.website:
        details.append(f"Website: {job.company.website}")
    if job.jd_text:
        details.append(data_block("job_description", job.jd_text[:800]))
    raw = await call_llm_json(
        db,
        owner_id,
        _need_llm(llm),
        settings,
        prompt=load_prompt(settings.prompts_dir, "intel-peers", 1),
        user="\n".join(details),
        schema=RawPeers,
    )
    peers = [p for p in raw.peers if not _same_company(p.name, job.company.name)]
    return PeersOut(peers=[PeerOut(name=p.name.strip(), why=p.why.strip()) for p in peers])


async def suggest_questions(
    db: AsyncSession,
    owner_id: uuid.UUID,
    job_id: uuid.UUID,
    *,
    llm: LlmClient | None,
    settings: Settings,
) -> QuestionsOut:
    job = await tracker_service.get_job(db, owner_id, job_id)
    if not job.jd_text:
        raise ProblemError(409, "No job description", "Save the job description first.")
    raw = await call_llm_json(
        db,
        owner_id,
        _need_llm(llm),
        settings,
        prompt=load_prompt(settings.prompts_dir, "intel-ask", 1),
        user=f"Role: {job.title}\nCompany: {job.company.name}\n\n"
        + data_block("job_description", job.jd_text[:4000]),
        schema=RawQuestions,
    )
    return QuestionsOut(questions=raw.questions)
