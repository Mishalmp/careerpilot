"""fx rates and star stories

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-06 02:52:59.647520
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("to_inr", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_fx_rates_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fx_rates")),
        sa.UniqueConstraint("owner_id", "currency", name="uq_fx_rates_owner_currency"),
    )
    op.create_index(op.f("ix_fx_rates_owner_id"), "fx_rates", ["owner_id"], unique=False)
    op.create_table(
        "star_stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_star_stories_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_star_stories")),
    )
    op.create_index(op.f("ix_star_stories_owner_id"), "star_stories", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_star_stories_owner_id"), table_name="star_stories")
    op.drop_table("star_stories")
    op.drop_index(op.f("ix_fx_rates_owner_id"), table_name="fx_rates")
    op.drop_table("fx_rates")
