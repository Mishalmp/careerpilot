"""profile setup answers and cv source

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-07 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("full_name", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("headline", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("current_role", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("location", sa.Text(), nullable=True))
    for name in ("target_roles", "target_levels", "regions", "work_modes", "links"):
        op.add_column(
            "user_profiles",
            sa.Column(name, _JSON, nullable=False, server_default=sa.text("'[]'::jsonb")),
        )
    op.add_column(
        "user_profiles",
        sa.Column("needs_visa", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("user_profiles", sa.Column("salary_floor_lpa", sa.Numeric(8, 2), nullable=True))
    op.add_column("user_profiles", sa.Column("salary_target_lpa", sa.Numeric(8, 2), nullable=True))
    op.add_column("user_profiles", sa.Column("cv_source", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("cv_filename", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("cv_chars", sa.Integer(), nullable=True))
    op.add_column(
        "user_profiles", sa.Column("setup_completed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    for name in (
        "setup_completed_at",
        "cv_chars",
        "cv_filename",
        "cv_source",
        "salary_target_lpa",
        "salary_floor_lpa",
        "needs_visa",
        "links",
        "work_modes",
        "regions",
        "target_levels",
        "target_roles",
        "location",
        "current_role",
        "headline",
        "full_name",
    ):
        op.drop_column("user_profiles", name)
