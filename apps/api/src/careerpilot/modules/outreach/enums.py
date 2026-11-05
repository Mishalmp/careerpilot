from enum import StrEnum


class OutreachStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    SENT = "sent"  # you sent it yourself, from your own mail client, and recorded it here
    REJECTED = "rejected"


class Channel(StrEnum):
    EMAIL = "email"  # to an address the company publishes for hiring
    RECRUITER_MESSAGE = "recruiter_message"
    REFERRAL_REQUEST = "referral_request"
