from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from sqlalchemy import text

from careerpilot.core.deps import DbSession
from careerpilot.core.errors import ProblemError

ALEMBIC_DIR = Path(__file__).resolve().parents[2] / "alembic"

router = APIRouter(tags=["ops"])


def migration_head() -> str | None:
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return ScriptDirectory.from_config(config).get_current_head()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: DbSession) -> dict[str, str]:
    try:
        current = await db.scalar(text("select version_num from alembic_version"))
    except Exception as exc:
        raise ProblemError(503, "Database not ready", "Run `alembic upgrade head`.") from exc
    head = migration_head()
    if current != head:
        raise ProblemError(503, "Migrations not current", f"database={current} code={head}")
    return {"status": "ready"}
