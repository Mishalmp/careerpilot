"""mock interviews

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-06 01:18:27.774447
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mock_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("focus", sa.Text(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("turns", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_mock_sessions_job_id_jobs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_mock_sessions_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mock_sessions")),
    )
    op.create_index(
        op.f("ix_mock_sessions_created_at"), "mock_sessions", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_mock_sessions_owner_id"), "mock_sessions", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mock_sessions_owner_id"), table_name="mock_sessions")
    op.drop_index(op.f("ix_mock_sessions_created_at"), table_name="mock_sessions")
    op.drop_table("mock_sessions")
