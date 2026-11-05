import argparse
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from getpass import getpass
from pathlib import Path

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from careerpilot.core.clock import today_in
from careerpilot.core.config import get_settings
from careerpilot.core.db import create_engine, create_sessionmaker
from careerpilot.modules.auth import service as auth_service
from careerpilot.modules.knowledge import evaluation as rag_eval
from careerpilot.modules.knowledge import service as knowledge_service
from careerpilot.modules.knowledge.embeddings import make_embedder
from careerpilot.modules.prep import service as prep_service
from careerpilot.modules.prep.curriculum import load_curriculum
from careerpilot.modules.tracker import importer


async def _run(action: Callable[[AsyncSession], Awaitable[None]]) -> None:
    engine = create_engine(get_settings().database_url)
    try:
        async with create_sessionmaker(engine)() as db:
            await action(db)
    finally:
        await engine.dispose()


def _create_user(args: argparse.Namespace) -> int:
    try:
        email = TypeAdapter(EmailStr).validate_python(args.email)
    except ValidationError:
        print("That is not a valid email address.", file=sys.stderr)
        return 2
    password = getpass("Password: ")
    if password != getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 2

    async def action(db: AsyncSession) -> None:
        await auth_service.create_user(db, email, password)

    try:
        asyncio.run(_run(action))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except auth_service.UserExistsError:
        print("A user with that email already exists.", file=sys.stderr)
        return 1
    print(f"Created user {email}.")
    return 0


def _seed_prep(_: argparse.Namespace) -> int:
    settings = get_settings()

    async def action(db: AsyncSession) -> None:
        user = await auth_service.sole_user(db)
        result = await prep_service.seed(db, user.id, load_curriculum(settings.content_dir))
        print(result.model_dump_json())

    return _guarded(action)


def _import_tracker(args: argparse.Namespace) -> int:
    settings = get_settings()
    path = Path(args.file)
    if not path.is_file():
        print(f"No such file: {path}", file=sys.stderr)
        return 2

    async def action(db: AsyncSession) -> None:
        user = await auth_service.sole_user(db)
        result = await importer.import_workbook(
            db, user.id, path, today=today_in(settings.timezone)
        )
        print(f"created {result.created}, already present {result.already_present}")
        for error in result.errors:
            print(f"  row {error.row}: {error.message}", file=sys.stderr)
        if result.ignored_columns:
            print("columns not imported yet: " + ", ".join(result.ignored_columns))

    return _guarded(action)


def _embedder():
    settings = get_settings()
    return make_embedder(settings.embedder, settings.embedding_model, settings.model_cache_dir)


def _ingest(_: argparse.Namespace) -> int:
    settings = get_settings()

    async def action(db: AsyncSession) -> None:
        user = await auth_service.sole_user(db)
        result = await knowledge_service.ingest(db, user.id, settings.content_dir, _embedder())
        print(result.model_dump_json())

    return _guarded(action)


def _search(args: argparse.Namespace) -> int:
    settings = get_settings()

    async def action(db: AsyncSession) -> None:
        user = await auth_service.sole_user(db)
        found = await knowledge_service.search(
            db, user.id, _embedder(), settings, args.query, args.limit
        )
        print(f"confident: {found.confident} (best similarity {found.best_similarity})")
        for hit in found.hits:
            sim = f"{hit.similarity:.2f}" if hit.similarity is not None else " -- "
            print(f"  {sim}  {hit.document_name} > {hit.heading_path or '(top)'}")
            print(f"        {hit.text[:110]!r}")

    return _guarded(action)


def _eval_rag(args: argparse.Namespace) -> int:
    settings = get_settings()

    async def action(db: AsyncSession) -> None:
        user = await auth_service.sole_user(db)
        questions = rag_eval.load_questions(settings.content_dir)
        results, skipped = await rag_eval.run(
            db, user.id, _embedder(), settings, questions, k=args.k, mode=args.mode
        )
        report = rag_eval.summarize(results, skipped, args.k)
        print(json.dumps(report.__dict__, indent=2))
        if args.details:
            for r in results:
                print(f"  {r.id:28s} rank={r.rank} confident={r.confident} sim={r.best_similarity}")

    return _guarded(action)


def _worker(_: argparse.Namespace) -> int:
    """Run the background worker on its own (the API also runs one while it is up)."""
    import asyncio
    import contextlib
    import signal

    from careerpilot.core.config import get_settings
    from careerpilot.core.db import create_engine, create_sessionmaker
    from careerpilot.core.fetcher import Fetcher
    from careerpilot.worker import worker_loop

    async def run() -> None:
        settings = get_settings()
        engine = create_engine(settings.database_url)
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for name in ("SIGINT", "SIGTERM"):
            if hasattr(signal, name):
                loop.add_signal_handler(getattr(signal, name), stop.set)
        try:
            await worker_loop(create_sessionmaker(engine), Fetcher(), settings, stop)
        finally:
            await engine.dispose()

    with contextlib.suppress(KeyboardInterrupt):  # Windows has no loop signal handlers
        asyncio.run(run())
    return 0


def _guarded(action: Callable[[AsyncSession], Awaitable[None]]) -> int:
    try:
        asyncio.run(_run(action))
    except (LookupError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careerpilot")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create the single local user")
    create.add_argument("--email", required=True)
    create.set_defaults(run=_create_user)
    seed = commands.add_parser("seed-prep", help="load the prep curriculum (safe to repeat)")
    seed.set_defaults(run=_seed_prep)
    imp = commands.add_parser("import-tracker", help="import jobs from the tracker workbook")
    imp.add_argument("file", help="path to Job_Hunt_Tracker.xlsx")
    imp.set_defaults(run=_import_tracker)
    commands.add_parser("ingest", help="index your notes for search (safe to repeat)").set_defaults(
        run=_ingest
    )
    commands.add_parser(
        "worker", help="run the background worker (job boards, daily digest)"
    ).set_defaults(func=_worker)
    find = commands.add_parser("search", help="search your notes")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    find.set_defaults(run=_search)
    measure = commands.add_parser(
        "eval-rag", help="measure retrieval quality on the golden questions"
    )
    measure.add_argument("--k", type=int, default=5)
    measure.add_argument("--details", action="store_true")
    measure.add_argument("--mode", choices=["hybrid", "vector", "text"], default="hybrid")
    measure.set_defaults(run=_eval_rag)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
