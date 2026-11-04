"""practice submissions

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05 02:00:44.421046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("problem_slug", sa.Text(), nullable=False),
        sa.Column(
            "language",
            sa.Enum(
                "python",
                "javascript",
                "typescript",
                "sql",
                name="submission_language",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "passed >= 0 AND passed <= total", name=op.f("ck_submissions_passed_within_total")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_submissions_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(
        "ix_submissions_owner_id_problem_slug_created_at",
        "submissions",
        ["owner_id", "problem_slug", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_owner_id_problem_slug_created_at", table_name="submissions")
    op.drop_table("submissions")
