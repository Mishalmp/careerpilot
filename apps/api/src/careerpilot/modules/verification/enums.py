from enum import StrEnum


class CheckKey(StrEnum):
    # The eight checks that make up the verdict.
    WEBSITE = "website"
    DOMAIN_AGE = "domain_age"
    MAIL_DOMAIN = "mail_domain"
    CAREERS_PAGE = "careers_page"
    REGISTRATION = "registration"
    CONTACT_DETAILS = "contact_details"
    PEOPLE = "people"
    INDEPENDENT_MENTIONS = "independent_mentions"
    # Hard red flags. For these, "fail" means the flag is raised.
    ASKS_FOR_MONEY = "asks_for_money"
    CHAT_ONLY_HIRING = "chat_only_hiring"
    NO_INTERVIEW = "no_interview"
    FREE_MAIL_RECRUITER = "free_mail_recruiter"


CHECKS: tuple[CheckKey, ...] = tuple(list(CheckKey)[:8])
FLAGS: tuple[CheckKey, ...] = tuple(list(CheckKey)[8:])


class CheckStatus(StrEnum):
    PASS = "pass"  # noqa: S105 - a check result, not a password
    FAIL = "fail"
    UNKNOWN = "unknown"


class CheckSource(StrEnum):
    AUTO = "auto"  # code looked something up
    AI = "ai"  # the model read the company's pages; its quote was verified by code
    MANUAL = "manual"  # you set it; automatic runs never overwrite it


class VerdictLabel(StrEnum):
    VERIFIED = "verified"
    LIKELY_GENUINE = "likely_genuine"
    NEEDS_CHECK = "needs_check"
    SUSPICIOUS = "suspicious"
