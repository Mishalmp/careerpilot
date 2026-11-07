"""profile contact details

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-08 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("contact_email", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("phone", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "phone")
    op.drop_column("user_profiles", "contact_email")
