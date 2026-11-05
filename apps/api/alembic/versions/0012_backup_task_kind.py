"""allow the backup task kind

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-06 12:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_tasks_task_kind"


def upgrade() -> None:
    op.drop_constraint(op.f(_CONSTRAINT), "tasks", type_="check")  # op.f: exact name
    op.create_check_constraint(
        op.f(_CONSTRAINT), "tasks", "kind IN ('discover', 'daily_digest', 'backup')"
    )


def downgrade() -> None:
    op.execute("delete from tasks where kind = 'backup'")
    op.drop_constraint(op.f(_CONSTRAINT), "tasks", type_="check")  # op.f: exact name
    op.create_check_constraint(op.f(_CONSTRAINT), "tasks", "kind IN ('discover', 'daily_digest')")
