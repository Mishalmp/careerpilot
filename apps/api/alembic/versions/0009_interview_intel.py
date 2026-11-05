"""interview intel

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-05 03:45:40.043865
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intel_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "pasted",
                "fetched",
                name="intel_source_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("about_company", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_intel_sources_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_intel_sources_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intel_sources")),
    )
    op.create_index(
        "ix_intel_sources_owner_id_company_id",
        "intel_sources",
        ["owner_id", "company_id"],
        unique=False,
    )
    op.create_table(
        "intel_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "round",
                "topic",
                "question",
                "tip",
                name="intel_item_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_intel_items_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["intel_sources.id"],
            name=op.f("fk_intel_items_source_id_intel_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intel_items")),
    )
    op.create_index(op.f("ix_intel_items_owner_id"), "intel_items", ["owner_id"], unique=False)
    op.create_index(op.f("ix_intel_items_source_id"), "intel_items", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_intel_items_source_id"), table_name="intel_items")
    op.drop_index(op.f("ix_intel_items_owner_id"), table_name="intel_items")
    op.drop_table("intel_items")
    op.drop_index("ix_intel_sources_owner_id_company_id", table_name="intel_sources")
    op.drop_table("intel_sources")
