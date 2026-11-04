"""tracker and prep tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 01:29:01.042093
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_companies_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
        sa.UniqueConstraint(
            "owner_id", "normalized_name", name="uq_companies_owner_id_normalized_name"
        ),
    )
    op.create_index(op.f("ix_companies_owner_id"), "companies", ["owner_id"], unique=False)
    op.create_table(
        "prep_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("focus", sa.Text(), nullable=False),
        sa.Column("core_topics", sa.Text(), nullable=False),
        sa.Column("practice", sa.Text(), nullable=False),
        sa.Column("speaking", sa.Text(), nullable=False),
        sa.Column("hours", sa.Integer(), nullable=False),
        sa.Column("deliverable", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "Planned",
                "Done",
                "Skipped",
                "Moved",
                name="day_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_prep_days_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_days")),
        sa.UniqueConstraint("owner_id", "day", name="uq_prep_days_owner_id_day"),
    )
    op.create_table(
        "prep_plans",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_prep_plans_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("owner_id", name=op.f("pk_prep_plans")),
    )
    op.create_table(
        "prep_topics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            sa.Enum(
                "High",
                "Medium",
                "Low",
                name="topic_priority",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.SmallInteger(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "Not started",
                "Learning",
                "Revised",
                "Mock-tested",
                name="topic_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("last_reviewed_on", sa.Date(), nullable=True),
        sa.Column("next_review_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "confidence BETWEEN 1 AND 5", name=op.f("ck_prep_topics_confidence_range")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_prep_topics_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prep_topics")),
        sa.UniqueConstraint("owner_id", "key", name="uq_prep_topics_owner_id_key"),
    )
    op.create_index(
        "ix_prep_topics_owner_id_area", "prep_topics", ["owner_id", "area"], unique=False
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "published_business",
                "recruiter",
                "referral",
                name="contact_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind <> 'published_business' OR source_url IS NOT NULL",
            name=op.f("ck_contacts_published_business_needs_source"),
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_contacts_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_contacts_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index(op.f("ix_contacts_company_id"), "contacts", ["company_id"], unique=False)
    op.create_index(op.f("ix_contacts_owner_id"), "contacts", ["owner_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "LinkedIn",
                "Indeed",
                "Naukri",
                "Glassdoor",
                "Wellfound",
                "Instahyre",
                "Bayt",
                "NaukriGulf",
                "GulfTalent",
                "We Work Remotely",
                "Himalayas",
                "Remote.com",
                "Other",
                name="portal",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "region",
            sa.Enum(
                "India",
                "Europe",
                "USA",
                "UAE / Middle East",
                "Remote (Global)",
                name="region",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("location_text", sa.Text(), nullable=True),
        sa.Column(
            "work_mode",
            sa.Enum(
                "Remote",
                "Hybrid",
                "Onsite",
                name="work_mode",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "job_type",
            sa.Enum(
                "Permanent Full-time",
                "Contract",
                "Contract-to-Hire",
                name="job_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "hiring_from_india",
            sa.Enum(
                "Yes",
                "India only",
                "No",
                "Unknown",
                name="hiring_from_india",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "currency",
            sa.Enum(
                "INR",
                "USD",
                "EUR",
                "GBP",
                "AED",
                "CAD",
                "AUD",
                "SGD",
                "Other",
                name="currency",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("salary_text", sa.Text(), nullable=True),
        sa.Column("est_ctc_lpa", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column(
            "visa",
            sa.Enum(
                "Not needed",
                "Sponsorship offered",
                "Not offered",
                "Unknown",
                name="visa",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("found_on", sa.Date(), nullable=True),
        sa.Column("posted_on", sa.Date(), nullable=True),
        sa.Column("jd_url", sa.Text(), nullable=True),
        sa.Column("apply_url", sa.Text(), nullable=True),
        sa.Column("careers_url", sa.Text(), nullable=True),
        sa.Column("jd_text", sa.Text(), nullable=True),
        sa.Column("jd_summary", sa.Text(), nullable=True),
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
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_jobs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_jobs_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("owner_id", "fingerprint", name="uq_jobs_owner_id_fingerprint"),
    )
    op.create_index(op.f("ix_jobs_owner_id"), "jobs", ["owner_id"], unique=False)
    op.create_index(
        "ix_jobs_owner_id_updated_at_id", "jobs", ["owner_id", "updated_at", "id"], unique=False
    )
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "learn",
                "practice",
                "review",
                "mock",
                name="study_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("studied_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "minutes BETWEEN 1 AND 720", name=op.f("ck_study_sessions_minutes_range")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_study_sessions_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["prep_topics.id"],
            name=op.f("fk_study_sessions_topic_id_prep_topics"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_sessions")),
    )
    op.create_index(
        "ix_study_sessions_owner_id_studied_on",
        "study_sessions",
        ["owner_id", "studied_on"],
        unique=False,
    )
    op.create_index(
        op.f("ix_study_sessions_topic_id"), "study_sessions", ["topic_id"], unique=False
    )
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "New",
                "Shortlisted",
                "Applied - Pending",
                "Follow-up Sent",
                "Interview Confirmed",
                "Technical Round",
                "Next Round",
                "HR Round",
                "Manager Round",
                "Offer Received",
                "Offer Accepted",
                "Rejected",
                "No Response",
                "On Hold",
                "Withdrawn",
                "Job Closed",
                name="application_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("applied_on", sa.Date(), nullable=True),
        sa.Column("next_followup_on", sa.Date(), nullable=True),
        sa.Column(
            "portal_mode",
            sa.Enum(
                "Not yet",
                "Done",
                "Not available",
                name="portal_mode",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "site_mode",
            sa.Enum(
                "Not yet",
                "Done",
                "Not available",
                name="site_mode",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "email_mode",
            sa.Enum(
                "Not yet",
                "Draft ready",
                "Sent",
                "No email found",
                name="email_mode",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("resume_version", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            ["job_id"], ["jobs.id"], name=op.f("fk_applications_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_applications_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint("job_id", name=op.f("uq_applications_job_id")),
    )
    op.create_index(op.f("ix_applications_owner_id"), "applications", ["owner_id"], unique=False)
    op.create_index(
        "ix_applications_owner_id_next_followup_on",
        "applications",
        ["owner_id", "next_followup_on"],
        unique=False,
    )
    op.create_index(
        "ix_applications_owner_id_status", "applications", ["owner_id", "status"], unique=False
    )
    op.create_table(
        "application_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "created",
                "status_changed",
                "reopened",
                name="event_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.Enum(
                "New",
                "Shortlisted",
                "Applied - Pending",
                "Follow-up Sent",
                "Interview Confirmed",
                "Technical Round",
                "Next Round",
                "HR Round",
                "Manager Round",
                "Offer Received",
                "Offer Accepted",
                "Rejected",
                "No Response",
                "On Hold",
                "Withdrawn",
                "Job Closed",
                name="event_from_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "New",
                "Shortlisted",
                "Applied - Pending",
                "Follow-up Sent",
                "Interview Confirmed",
                "Technical Round",
                "Next Round",
                "HR Round",
                "Manager Round",
                "Offer Received",
                "Offer Accepted",
                "Rejected",
                "No Response",
                "On Hold",
                "Withdrawn",
                "Job Closed",
                name="event_to_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["applications.id"],
            name=op.f("fk_application_events_application_id_applications"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_events")),
    )
    op.create_index(
        "ix_application_events_application_id_at",
        "application_events",
        ["application_id", "at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_application_events_application_id_at", table_name="application_events")
    op.drop_table("application_events")
    op.drop_index("ix_applications_owner_id_status", table_name="applications")
    op.drop_index("ix_applications_owner_id_next_followup_on", table_name="applications")
    op.drop_index(op.f("ix_applications_owner_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index(op.f("ix_study_sessions_topic_id"), table_name="study_sessions")
    op.drop_index("ix_study_sessions_owner_id_studied_on", table_name="study_sessions")
    op.drop_table("study_sessions")
    op.drop_index("ix_jobs_owner_id_updated_at_id", table_name="jobs")
    op.drop_index(op.f("ix_jobs_owner_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_contacts_owner_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_company_id"), table_name="contacts")
    op.drop_table("contacts")
    op.drop_index("ix_prep_topics_owner_id_area", table_name="prep_topics")
    op.drop_table("prep_topics")
    op.drop_table("prep_plans")
    op.drop_table("prep_days")
    op.drop_index(op.f("ix_companies_owner_id"), table_name="companies")
    op.drop_table("companies")
