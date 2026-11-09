"""what the last read of a board kept and why the rest was left out

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-09 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("discovery_sources", sa.Column("last_kept", sa.Integer(), nullable=True))
    op.add_column("discovery_sources", sa.Column("last_left_out", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("discovery_sources", "last_left_out")
    op.drop_column("discovery_sources", "last_kept")
