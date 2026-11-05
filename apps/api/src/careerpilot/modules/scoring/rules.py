"""How a job is scored. Pure functions: no database, no network, no model.

Six components, each 0 to 100 or None when there is not enough information. A component that is
None is left out and the others are re-weighted, and `coverage` says how much of the total weight
was actually measured, so a score built from two facts never looks as solid as one built from six.

Changing a weight or a rule means bumping SCORING_VERSION, so stored scores can be told apart.
"""

from dataclasses import dataclass
from typing import Literal

from careerpilot.modules.scoring.profile import Profile
from careerpilot.modules.tracker.enums import HiringFromIndia, Region, Visa, WorkMode
from careerpilot.modules.verification.enums import VerdictLabel

SCORING_VERSION = 1

WEIGHTS: dict[str, int] = {
    "skills": 30,
    "pay": 20,
    "seniority": 15,
    "company": 15,
    "location": 10,
    "growth": 10,
}

Chance = Literal["good", "possible", "unlikely", "unknown"]
Priority = Literal["high", "medium", "low"]

MIN_JD_SKILLS = 3  # fewer than this and the description says too little to judge skills
MIN_COVERAGE = 50  # below this percent of measured weight, no chance label is given


@dataclass(frozen=True)
class Component:
    key: str
    score: int | None
    detail: str

    @property
    def weight(self) -> int:
        return WEIGHTS[self.key]


# --- components ----------------------------------------------------------------------------


def skills_component(jd_skills: set[str], my_skills: set[str]) -> Component:
    if len(jd_skills) < MIN_JD_SKILLS:
        return Component("skills", None, "The description names too few known skills to compare.")
    matched = jd_skills & my_skills
    missing = sorted(jd_skills - my_skills)
    score = round(100 * len(matched) / len(jd_skills))
    detail = f"You have {len(matched)} of the {len(jd_skills)} skills it names."
    if missing:
        detail += " Missing: " + ", ".join(missing[:8]) + "."
    return Component("skills", score, detail)


def seniority_component(
    title_level: str | None, years_asked: int | None, profile: Profile
) -> Component:
    if years_asked is None and title_level is None:
        return Component("seniority", None, "No level or years of experience are stated.")
    score = 100
    notes: list[str] = []
    if years_asked is not None:
        gap = years_asked - profile.years_experience
        score = 100 if gap <= 0 else 10 if gap >= 3 else round(100 - 30 * gap)
        notes.append(f"asks for {years_asked}+ years; you have {profile.years_experience:g}")
    if title_level == "senior" and "senior" not in profile.target_levels:
        score = min(score, 40)
        notes.append("the title is senior-level")
    if title_level == "junior" and profile.years_experience >= 5:
        score = min(score, 60)
        notes.append("the title is junior-level")
    return Component("seniority", score, "The posting " + "; ".join(notes) + ".")


def pay_component(est_ctc_lpa: float | None, profile: Profile) -> Component:
    floor, target = profile.salary_floor_lpa, profile.salary_target_lpa
    if est_ctc_lpa is None:
        return Component("pay", None, "The job has no pay estimate.")
    if floor is None and target is None:
        return Component("pay", None, "Your profile has no salary floor or target yet.")
    target = target or floor or est_ctc_lpa
    floor = floor or target
    if est_ctc_lpa >= target:
        score = 100
    elif est_ctc_lpa >= floor:
        span = max(target - floor, 1e-9)
        score = round(60 + 40 * (est_ctc_lpa - floor) / span)
    else:
        score = max(0, round(60 * (est_ctc_lpa - floor / 2) / (floor / 2)))
    detail = f"Estimated {est_ctc_lpa:g} LPA against your floor {floor:g} and target {target:g}."
    return Component("pay", score, detail)


COMPANY_SCORES: dict[VerdictLabel, int] = {
    VerdictLabel.VERIFIED: 100,
    VerdictLabel.LIKELY_GENUINE: 75,
    VerdictLabel.NEEDS_CHECK: 40,
    VerdictLabel.SUSPICIOUS: 0,
}


def company_component(verdict: VerdictLabel | None) -> Component:
    if verdict is None:
        return Component("company", None, "The company has not been verified yet.")
    return Component("company", COMPANY_SCORES[verdict], f"Verification verdict: {verdict.value}.")


def location_component(
    region: Region | None,
    work_mode: WorkMode | None,
    hiring_from_india: HiringFromIndia | None,
    visa: Visa | None,
    profile: Profile,
) -> Component:
    if region is None:
        return Component("location", None, "The job has no region.")
    if region not in profile.regions:
        return Component("location", 20, f"{region.value} is not among your regions.")
    if region is Region.INDIA:
        return Component("location", 100, "In India.")
    # Outside India: can they hire you, and do you need sponsorship?
    if hiring_from_india is HiringFromIndia.NO:
        return Component("location", 0, "It does not hire from India.")
    if work_mode is WorkMode.REMOTE and hiring_from_india in (
        HiringFromIndia.YES,
        HiringFromIndia.INDIA_ONLY,
    ):
        return Component("location", 100, "Remote and hires from India.")
    if not profile.needs_visa_sponsorship or visa in (Visa.NOT_NEEDED, Visa.SPONSORSHIP_OFFERED):
        return Component("location", 70, "Workable from India.")
    if visa is Visa.NOT_OFFERED:
        return Component("location", 10, "You need sponsorship and it is not offered.")
    return Component("location", 50, "Sponsorship is unknown; ask before investing time.")


def growth_component(score: int | None, reason: str | None) -> Component:
    if score is None:
        return Component("growth", None, "No reading of the description yet (needs the AI step).")
    return Component("growth", score, reason or "From the model's reading of the description.")


# --- combining -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Total:
    score: int | None
    coverage: int  # percent of the total weight that was measured
    chance: Chance
    priority: Priority | None
    blockers: tuple[str, ...]


def combine(components: list[Component]) -> Total:
    """The weighted average of what was measured. The chance label is a rule of thumb, not a
    probability: it is not calibrated against real outcomes, and it says "unknown" rather than
    guess when too little was measured."""
    known = [c for c in components if c.score is not None]
    weight = sum(c.weight for c in known)
    coverage = round(100 * weight / sum(WEIGHTS.values()))
    if not known:
        return Total(None, 0, "unknown", None, ())
    score = round(sum(c.weight * (c.score or 0) for c in known) / weight)
    blockers = _blockers(components)
    chance: Chance
    if coverage < MIN_COVERAGE:
        chance = "unknown"
    elif blockers or score < 55:
        chance = "unlikely"
    else:
        chance = "good" if score >= 75 else "possible"
    priority: Priority = "high" if score >= 75 else "medium" if score >= 55 else "low"
    return Total(score, coverage, chance, priority, blockers)


def _blockers(components: list[Component]) -> tuple[str, ...]:
    by_key = {c.key: c for c in components}
    found: list[str] = []
    skills, location = by_key.get("skills"), by_key.get("location")
    company, seniority = by_key.get("company"), by_key.get("seniority")
    if skills and skills.score is not None and skills.score < 30:
        found.append("You have fewer than a third of the skills it names.")
    if location and location.score is not None and location.score <= 10:
        found.append("Location or visa makes this unworkable.")
    if company and company.score == 0:
        found.append("The company looks suspicious.")
    if seniority and seniority.score is not None and seniority.score <= 25:
        found.append("It asks for much more experience than you have.")
    return tuple(found)
