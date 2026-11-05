"""company checks

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05 03:17:26.662039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_checks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column(
            "key",
            sa.Enum(
                "website",
                "domain_age",
                "mail_domain",
                "careers_page",
                "registration",
                "contact_details",
                "people",
                "independent_mentions",
                "asks_for_money",
                "chat_only_hiring",
                "no_interview",
                "free_mail_recruiter",
                name="check_key",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pass",
                "fail",
                "unknown",
                name="check_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "auto",
                "ai",
                "manual",
                name="check_source",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("evidence_quote", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_company_checks_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_company_checks_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_checks")),
        sa.UniqueConstraint("company_id", "key", name="uq_company_checks_company_id_key"),
    )
    op.create_index(
        op.f("ix_company_checks_owner_id"), "company_checks", ["owner_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_company_checks_owner_id"), table_name="company_checks")
    op.drop_table("company_checks")
