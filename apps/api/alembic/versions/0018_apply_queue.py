"""daily apply queue

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-07 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS_BEFORE = "kind IN ('discover', 'daily_digest', 'backup', 'research')"
_KINDS_AFTER = "kind IN ('discover', 'daily_digest', 'backup', 'research', 'apply_queue')"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_tasks_task_kind"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_task_kind"), "tasks", _KINDS_AFTER)
    op.create_table(
        "apply_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("queued_on", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ready",
                "approved",
                "applied",
                "skipped",
                "blocked",
                name="apply_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("match_score", sa.SmallInteger(), nullable=False),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pay", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("interview", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("also_listed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("company_check", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_score BETWEEN 0 AND 100", name=op.f("ck_apply_items_match_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_apply_items_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_apply_items_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apply_items")),
        sa.UniqueConstraint("owner_id", "job_id", name="uq_apply_items_owner_job"),
    )
    op.create_index(
        "ix_apply_items_owner_status_queued",
        "apply_items",
        ["owner_id", "status", "queued_on"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_apply_items_owner_status_queued", table_name="apply_items")
    op.drop_table("apply_items")
    op.execute("delete from tasks where kind = 'apply_queue'")
    op.drop_constraint(op.f("ck_tasks_task_kind"), "tasks", type_="check")
    op.create_check_constraint(op.f("ck_tasks_task_kind"), "tasks", _KINDS_BEFORE)
