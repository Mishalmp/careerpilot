"""task events and progress

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-07 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("progress", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_table(
        "task_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("level", sa.Text(), nullable=False),
        sa.Column("step", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_task_events_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_events_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_events")),
    )
    op.create_index(op.f("ix_task_events_owner_id"), "task_events", ["owner_id"], unique=False)
    op.create_index("ix_task_events_task_at", "task_events", ["task_id", "at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_events_task_at", table_name="task_events")
    op.drop_index(op.f("ix_task_events_owner_id"), table_name="task_events")
    op.drop_table("task_events")
    op.drop_column("tasks", "progress")
