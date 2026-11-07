"""search profiles, job feeds, quick research flag, question mentions

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-08 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSON = postgresql.JSONB(astext_type=sa.Text())
_BEFORE = "kind IN ('greenhouse', 'lever', 'ashby')"
_AFTER = (
    "kind IN ('greenhouse', 'lever', 'ashby', 'remoteok', 'remotive', 'arbeitnow', "
    "'himalayas', 'weworkremotely')"
)


def upgrade() -> None:
    # A non-native enum column is as wide as its longest value: "weworkremotely" needs 14.
    op.alter_column("discovery_sources", "kind", type_=sa.String(14), existing_nullable=False)
    op.drop_constraint(
        op.f("ck_discovery_sources_discovery_source_kind"), "discovery_sources", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_discovery_sources_discovery_source_kind"), "discovery_sources", _AFTER
    )
    op.add_column("discovered_jobs", sa.Column("company_name", sa.Text(), nullable=True))
    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("regions", _JSON, nullable=False),
        sa.Column("cities", _JSON, nullable=False),
        sa.Column("work_modes", _JSON, nullable=False),
        sa.Column("keywords", _JSON, nullable=False),
        sa.Column("exclude", _JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_search_profiles_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_profiles")),
    )
    op.create_index(
        op.f("ix_search_profiles_owner_id"), "search_profiles", ["owner_id"], unique=False
    )
    op.add_column(
        "apply_items", sa.Column("deep", sa.Boolean(), nullable=False, server_default=sa.true())
    )
    op.add_column(
        "research_findings",
        sa.Column("mentions", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "research_findings",
        sa.Column("more_sources", _JSON, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("research_findings", "more_sources")
    op.drop_column("research_findings", "mentions")
    op.drop_column("apply_items", "deep")
    op.drop_index(op.f("ix_search_profiles_owner_id"), table_name="search_profiles")
    op.drop_table("search_profiles")
    op.drop_column("discovered_jobs", "company_name")
    op.execute("delete from discovery_sources where kind not in ('greenhouse', 'lever', 'ashby')")
    op.drop_constraint(
        op.f("ck_discovery_sources_discovery_source_kind"), "discovery_sources", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_discovery_sources_discovery_source_kind"), "discovery_sources", _BEFORE
    )
    op.alter_column("discovery_sources", "kind", type_=sa.String(10), existing_nullable=False)
