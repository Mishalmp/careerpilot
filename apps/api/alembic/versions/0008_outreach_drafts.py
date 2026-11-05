"""outreach drafts

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05 03:36:07.125210
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outreach_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum(
                "email",
                "recruiter_message",
                "referral_request",
                name="outreach_channel",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "sent",
                "rejected",
                name="outreach_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("variant", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("recipient_email", sa.Text(), nullable=True),
        sa.Column("recipient_source_url", sa.Text(), nullable=True),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_outreach_drafts_contact_id_contacts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_outreach_drafts_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_outreach_drafts_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_drafts")),
    )
    op.create_index(op.f("ix_outreach_drafts_job_id"), "outreach_drafts", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_outreach_drafts_owner_id"), "outreach_drafts", ["owner_id"], unique=False
    )
    op.create_index(
        "uq_outreach_drafts_one_per_job_channel",
        "outreach_drafts",
        ["owner_id", "job_id", "channel"],
        unique=True,
        postgresql_where=sa.text("status IN ('approved', 'sent')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_outreach_drafts_one_per_job_channel",
        table_name="outreach_drafts",
        postgresql_where=sa.text("status IN ('approved', 'sent')"),
    )
    op.drop_index(op.f("ix_outreach_drafts_owner_id"), table_name="outreach_drafts")
    op.drop_index(op.f("ix_outreach_drafts_job_id"), table_name="outreach_drafts")
    op.drop_table("outreach_drafts")
