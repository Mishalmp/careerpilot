from enum import StrEnum


class ApplyStatus(StrEnum):
    READY = "ready"  # waiting for you to read it
    APPROVED = "approved"  # you read it and want to apply; the job is Shortlisted
    APPLIED = "applied"  # you applied yourself and said so; the job is Applied - Pending
    SKIPPED = "skipped"
    BLOCKED = "blocked"  # held back by the company check; shown so you can see why


class PayLevel(StrEnum):
    """Where a pay figure came from, best evidence first."""

    POSTED = "posted"
    SAME_JOB_ELSEWHERE = "same_job_elsewhere"
    PREVIOUS_POST = "previous_post"
    SIMILAR_ROLES = "similar_roles"


class InterviewLevel(StrEnum):
    POSTED = "posted"
    THIS_COMPANY = "this_company"
    SIMILAR_ROLES = "similar_roles"


class ListingKind(StrEnum):
    SAME_JOB = "same_job"
    SIMILAR_ROLE = "similar_role"
