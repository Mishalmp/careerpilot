from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from careerpilot.modules.tracker.schemas import Url

Item = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Level = Literal["junior", "mid", "senior", "lead"]
Phone = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^\+?[0-9][0-9 ()\-]{5,19}$")
]
Lpa = Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)]
LinkKind = Literal["linkedin", "github", "leetcode", "naukri", "portfolio", "other"]
# Spelled out for the type checker; a test proves they equal the tracker enums.
RegionName = Literal["India", "Europe", "USA", "UAE / Middle East", "Remote (Global)"]
WorkModeName = Literal["Remote", "Hybrid", "Onsite"]

# A link of these kinds must point at the site it claims to be, so a typo or a pasted wrong link is
# caught here and not found later. "portfolio" and "other" can be anywhere.
LINK_HOSTS: dict[str, str] = {
    "linkedin": "linkedin.com",
    "github": "github.com",
    "leetcode": "leetcode.com",
    "naukri": "naukri.com",
}


class ProfileLink(BaseModel):
    kind: LinkKind
    url: Url

    @model_validator(mode="after")
    def _right_site(self) -> Self:
        wanted = LINK_HOSTS.get(self.kind)
        host = (urlsplit(self.url).hostname or "").lower()
        if wanted and not (host == wanted or host.endswith("." + wanted)):
            raise ValueError(f"a {self.kind} link must be on {wanted}")
        return self


class CvInfo(BaseModel):
    has_cv: bool
    source: str | None  # paste | pdf | docx | text | ocr
    filename: str | None
    chars: int | None


class SetupStatus(BaseModel):
    complete: bool
    completed_at: datetime | None
    missing: list[str]  # plain names of what is still needed, in the order to do them


class ProfileOut(BaseModel):
    has_cv: bool
    skills: list[str]
    role_titles: list[str]
    years_experience: int | None
    updated_at: datetime | None
    full_name: str | None
    headline: str | None
    current_role: str | None
    location: str | None
    contact_email: str | None
    phone: str | None
    target_roles: list[str]
    target_levels: list[str]
    regions: list[str]
    work_modes: list[str]
    needs_visa: bool
    salary_floor_lpa: float | None
    salary_target_lpa: float | None
    links: list[ProfileLink]
    cv: CvInfo
    setup: SetupStatus


class CvIn(BaseModel):
    text: Annotated[str, StringConstraints(min_length=20, max_length=60_000)]


class CvUploadOut(BaseModel):
    profile: ProfileOut
    notes: list[str]  # things to check, in plain words (OCR used, pages skipped, name guessed)


class ProfileUpdate(BaseModel):
    """Only the fields you send change. Use this to fix what the CV reading got wrong."""

    skills: Annotated[list[Item], Field(max_length=60)] | None = None
    role_titles: Annotated[list[Item], Field(max_length=12)] | None = None
    years_experience: Annotated[int, Field(ge=0, le=60)] | None = None
    full_name: Text | None = None
    headline: Text | None = None
    current_role: Text | None = None
    location: Text | None = None
    contact_email: EmailStr | None = None  # an empty value clears it
    phone: Phone | None = None
    target_roles: Annotated[list[Item], Field(max_length=8)] | None = None
    target_levels: Annotated[list[Level], Field(max_length=4)] | None = None
    regions: Annotated[list[RegionName], Field(max_length=5)] | None = None
    work_modes: Annotated[list[WorkModeName], Field(max_length=3)] | None = None
    needs_visa: bool | None = None
    salary_floor_lpa: (
        Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)] | None
    ) = None
    salary_target_lpa: (
        Annotated[Decimal, Field(ge=0, le=1000, max_digits=8, decimal_places=2)] | None
    ) = None
    links: Annotated[list[ProfileLink], Field(max_length=8)] | None = None

    @model_validator(mode="after")
    def _salary_order(self) -> Self:
        floor, target = self.salary_floor_lpa, self.salary_target_lpa
        if floor is not None and target is not None and floor > target:
            raise ValueError("the lowest salary you would accept cannot be above your target")
        return self


class GithubLanguage(BaseModel):
    name: str
    repos: int


class GithubReading(BaseModel):
    username: str
    repos_read: int
    languages: list[GithubLanguage]
    suggested_skills: list[str]  # not saved: you choose which to add
    notes: list[str]
