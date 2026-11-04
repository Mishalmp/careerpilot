from enum import StrEnum


class Status(StrEnum):
    NEW = "New"
    SHORTLISTED = "Shortlisted"
    APPLIED_PENDING = "Applied - Pending"
    FOLLOW_UP_SENT = "Follow-up Sent"
    INTERVIEW_CONFIRMED = "Interview Confirmed"
    TECHNICAL_ROUND = "Technical Round"
    NEXT_ROUND = "Next Round"
    HR_ROUND = "HR Round"
    MANAGER_ROUND = "Manager Round"
    OFFER_RECEIVED = "Offer Received"
    OFFER_ACCEPTED = "Offer Accepted"
    REJECTED = "Rejected"
    NO_RESPONSE = "No Response"
    ON_HOLD = "On Hold"
    WITHDRAWN = "Withdrawn"
    JOB_CLOSED = "Job Closed"


class Region(StrEnum):
    INDIA = "India"
    EUROPE = "Europe"
    USA = "USA"
    UAE = "UAE / Middle East"
    REMOTE_GLOBAL = "Remote (Global)"


class WorkMode(StrEnum):
    REMOTE = "Remote"
    HYBRID = "Hybrid"
    ONSITE = "Onsite"


class JobType(StrEnum):
    PERMANENT = "Permanent Full-time"
    CONTRACT = "Contract"
    CONTRACT_TO_HIRE = "Contract-to-Hire"


class Visa(StrEnum):
    NOT_NEEDED = "Not needed"
    SPONSORSHIP_OFFERED = "Sponsorship offered"
    NOT_OFFERED = "Not offered"
    UNKNOWN = "Unknown"


class HiringFromIndia(StrEnum):
    YES = "Yes"
    INDIA_ONLY = "India only"
    NO = "No"
    UNKNOWN = "Unknown"


class Currency(StrEnum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    AED = "AED"
    CAD = "CAD"
    AUD = "AUD"
    SGD = "SGD"
    OTHER = "Other"


class Portal(StrEnum):
    LINKEDIN = "LinkedIn"
    INDEED = "Indeed"
    NAUKRI = "Naukri"
    GLASSDOOR = "Glassdoor"
    WELLFOUND = "Wellfound"
    INSTAHYRE = "Instahyre"
    BAYT = "Bayt"
    NAUKRIGULF = "NaukriGulf"
    GULFTALENT = "GulfTalent"
    WE_WORK_REMOTELY = "We Work Remotely"
    HIMALAYAS = "Himalayas"
    REMOTE_COM = "Remote.com"
    OTHER = "Other"


class PortalMode(StrEnum):
    """Used for both the job-portal mode and the company-site mode."""

    NOT_YET = "Not yet"
    DONE = "Done"
    NOT_AVAILABLE = "Not available"


class EmailMode(StrEnum):
    NOT_YET = "Not yet"
    DRAFT_READY = "Draft ready"
    SENT = "Sent"
    NO_EMAIL = "No email found"


class ContactKind(StrEnum):
    PUBLISHED_BUSINESS = "published_business"
    RECRUITER = "recruiter"
    REFERRAL = "referral"


class EventType(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    REOPENED = "reopened"
