"""Your Telegram chat as a second front door: read the day's list, decide, save links.

Everything here calls the same services the web app does, so the same rules apply: nothing is
sent anywhere, `/approve` only marks the job Shortlisted, and the model is never called (so
Telegram cannot spend AI budget). Only messages from the one configured chat reach this code.
"""

import re
import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.config import Settings
from careerpilot.core.errors import ProblemError
from careerpilot.core.llm import spend
from careerpilot.modules.apply import service as apply_service
from careerpilot.modules.apply.enums import ApplyStatus
from careerpilot.modules.apply.schemas import ApplyItemOut
from careerpilot.modules.tasks import service as tasks_service
from careerpilot.modules.tracker import service as tracker_service

SHOWN = 10  # items per message; the web app has the rest
_URL = re.compile(r"https?://\S+")
_CODE = re.compile(r"^[0-9a-f]{4,12}$")

HELP = """CareerPilot commands
/today - the jobs ready for you (10 at a time)
/more - the next 10
/show CODE - reasons, pay source and company check for one job
/approve CODE - you read it and want to apply (marks it Shortlisted)
/applied CODE - you applied yourself
/skip CODE - not for you
/build - make a fresh list now
/status - what is running, what failed, AI spend
/spend - AI spend today and this month
Send or forward any job link (LinkedIn, Indeed, Naukri, a company page) to save it.
Nothing is ever sent or submitted from here: you press apply on the site."""


def code_of(item: ApplyItemOut) -> str:
    return item.id.hex[:6]


def _pay(item: ApplyItemOut) -> str:
    pay = item.pay
    if pay is None or pay.mid is None:
        return "pay unknown"
    cur = pay.currency or ""
    if pay.low is not None and pay.high is not None:
        return f"pay ~{cur} {pay.low:,.0f}-{pay.high:,.0f} ({pay.label.lower()})"
    return f"pay ~{cur} {pay.mid:,.0f} ({pay.label.lower()})"


def line(item: ApplyItemOut) -> str:
    where = ", ".join(x for x in (item.location, item.work_mode) if x) or "place not stated"
    link = item.apply_url or item.jd_url or "no link"
    return (
        f"[{code_of(item)}] {item.title} - {item.company}\n"
        f"    {where} - match {item.match_score} - {_pay(item)}\n"
        f"    {link}"
    )


def render(items: list[ApplyItemOut], *, start: int = 0) -> str:
    ready = [i for i in items if i.status is ApplyStatus.READY]
    if not ready:
        return "Nothing ready right now. /build makes a fresh list."
    page = ready[start : start + SHOWN]
    if not page:
        return "That is the whole list."
    head = f"{len(ready)} ready; showing {start + 1}-{start + len(page)}."
    more = " /more for the next ones." if len(ready) > start + SHOWN else ""
    return (
        head
        + "\n\n"
        + "\n\n".join(line(i) for i in page)
        + f"\n\nUse /approve CODE or /skip CODE.{more}"
    )


def queue_ready_message(items: list[ApplyItemOut]) -> str:
    ready = [i for i in items if i.status is ApplyStatus.READY]
    return f"Your apply list is ready: {len(ready)} jobs.\n\n" + render(items)


def _find(items: list[ApplyItemOut], code: str) -> ApplyItemOut | str:
    code = code.strip().lower().lstrip("[").rstrip("]")
    if not _CODE.match(code):
        return "Give the code in brackets, for example /approve a1b2c3."
    hits = [i for i in items if i.id.hex.startswith(code)]
    if not hits:
        return f"No job with code {code}. /today shows the codes."
    if len(hits) > 1:
        return f"{code} matches {len(hits)} jobs. Use more characters."
    return hits[0]


def _detail(item: ApplyItemOut) -> str:
    out = [line(item), ""]
    if item.reasons:
        out += ["Why it matches:"] + [f"- {r}" for r in item.reasons[:5]]
    if item.pay and item.pay.evidence:
        out.append(f"Pay source: {item.pay.evidence[0].url}")
    if item.interview and item.interview.label:
        out.append(f"Interview notes: {item.interview.label}")
    if item.company_check:
        out.append(f"Company check: {item.company_check.model_dump_json()[:200]}")
    out += [f"Note: {n}" for n in item.notes[:3]]
    return "\n".join(out)


async def _money(db: AsyncSession, owner_id: uuid.UUID, settings: Settings) -> str:
    money = await spend(db, owner_id, settings)
    return (
        f"AI spend: ${money.today_usd:.2f} of ${money.daily_budget_usd:.2f} today, "
        f"${money.month_usd:.2f} of ${money.monthly_budget_usd:.2f} this month."
    )


async def handle(
    db: AsyncSession, owner_id: uuid.UUID, text: str, settings: Settings, *, today: date
) -> str:
    """The reply to one message from your chat. Never raises for a user mistake."""
    text = text.strip()
    if not text:
        return HELP
    if not text.startswith("/"):
        links = _URL.findall(text)
        return await _save_links(db, owner_id, links, today) if links else HELP
    command, _, rest = text.partition(" ")
    command = command.split("@")[0].lower()
    try:
        return await _run(db, owner_id, command, rest.strip(), settings, today)
    except ProblemError as exc:
        return f"{exc.title}. {exc.detail or ''}".strip()


async def _save_links(db: AsyncSession, owner_id: uuid.UUID, links: list[str], today: date) -> str:
    results = await tracker_service.add_links(db, owner_id, links[:50], today=today)
    lines: list[str] = []
    for r in results:
        if r.status == "rejected":
            lines.append(f"- not saved: {r.note}")
        else:
            said = "saved" if r.status == "added" else "already saved"
            more = " (open it in the app to add the company or role)" if r.needs_details else ""
            lines.append(f"- {said}: {r.title} - {r.company}{more}")
    return "\n".join(lines) or "No links found."


async def _run(
    db: AsyncSession, owner_id: uuid.UUID, command: str, rest: str, settings: Settings, today: date
) -> str:
    if command in ("/start", "/help"):
        return HELP
    if command == "/spend":
        return await _money(db, owner_id, settings)
    if command == "/status":
        listing = await tasks_service.list_tasks(db, owner_id, None)
        c = listing.counts
        ready = await apply_service.ready_count(db, owner_id)
        return (
            f"{ready} jobs ready. Tasks: {c.running} running, {c.queued} queued, "
            f"{c.failed} failed.\n{await _money(db, owner_id, settings)}"
        )
    if command == "/build":
        queued = await apply_service.request_build(db, owner_id, settings)
        if queued:
            return "Building the list; I will message you when it is ready."
        return "A build was already started this minute."
    if command == "/links":
        links = _URL.findall(rest)
        if not links:
            return "Add links after /links."
        return await _save_links(db, owner_id, links, today)
    if command in ("/today", "/more"):
        queue = await apply_service.get_queue(db, owner_id, settings, today)
        return render(queue.items, start=SHOWN if command == "/more" else 0)
    if command in ("/show", "/approve", "/applied", "/skip"):
        queue = await apply_service.get_queue(db, owner_id, settings, today)
        found = _find(queue.items, rest)
        if isinstance(found, str):
            return found
        if command == "/show":
            return _detail(found)
        action = {
            "/approve": apply_service.approve,
            "/applied": apply_service.mark_applied,
            "/skip": apply_service.skip,
        }[command]
        done = await action(db, owner_id, found.id, None, today=today)
        return f"[{code_of(done)}] {done.title} - {done.company}: {done.status.value}."
    return "I do not know that command. /help lists them."
