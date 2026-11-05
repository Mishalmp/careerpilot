"""Scoring rules and skill extraction: pure functions, tested without a database."""

from pathlib import Path

import pytest

from careerpilot.core.config import REPO_ROOT
from careerpilot.modules.scoring.profile import Profile
from careerpilot.modules.scoring.rules import (
    WEIGHTS,
    Component,
    combine,
    company_component,
    growth_component,
    location_component,
    pay_component,
    seniority_component,
    skills_component,
)
from careerpilot.modules.scoring.skills import (
    Vocabulary,
    level_of_title,
    load_vocabulary,
    skills_in,
    years_required,
)
from careerpilot.modules.tracker.enums import HiringFromIndia, Region, Visa, WorkMode
from careerpilot.modules.verification.enums import VerdictLabel


def profile(**overrides: object) -> Profile:
    base: dict[str, object] = {
        "years_experience": 2,
        "target_levels": ["junior", "mid"],
        "skills": ["python"],
        "regions": [Region.INDIA, Region.REMOTE_GLOBAL],
        "salary_floor_lpa": 10,
        "salary_target_lpa": 20,
    }
    return Profile.model_validate(base | overrides)


def test_weights_add_up_to_one_hundred() -> None:
    assert sum(WEIGHTS.values()) == 100


# --- skills --------------------------------------------------------------------------------


def test_skills_need_enough_named_skills_to_mean_anything() -> None:
    assert skills_component({"python", "sql"}, {"python"}).score is None


def test_skills_score_is_the_share_you_have_and_names_what_is_missing() -> None:
    result = skills_component({"python", "sql", "kafka", "go"}, {"python", "sql", "react"})
    assert result.score == 50
    assert "2 of the 4" in result.detail and "go, kafka" in result.detail
    assert skills_component({"python", "sql", "kafka"}, {"python", "sql", "kafka"}).score == 100


# --- seniority -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("asked", "expected"),
    [(1, 100), (2, 100), (3, 70), (4, 40), (5, 10), (10, 10)],
)
def test_asking_for_more_years_than_you_have_lowers_the_score(asked: int, expected: int) -> None:
    assert seniority_component(None, asked, profile()).score == expected


def test_a_senior_title_caps_the_score_unless_you_aim_for_senior() -> None:
    assert seniority_component("senior", None, profile()).score == 40
    assert seniority_component("senior", None, profile(target_levels=["senior"])).score == 100


def test_a_junior_title_is_a_poor_match_for_an_experienced_engineer() -> None:
    assert seniority_component("junior", None, profile(years_experience=6)).score == 60
    assert seniority_component("junior", None, profile()).score == 100


def test_no_level_information_is_not_guessed() -> None:
    assert seniority_component(None, None, profile()).score is None


# --- pay -----------------------------------------------------------------------------------


def test_pay_is_left_out_when_either_side_is_unknown() -> None:
    assert pay_component(None, profile()).score is None
    unset = profile(salary_floor_lpa=None, salary_target_lpa=None)
    assert pay_component(18, unset).score is None


@pytest.mark.parametrize(
    ("estimate", "expected"),
    [(25, 100), (20, 100), (15, 80), (10, 60), (7.5, 30), (5, 0), (1, 0)],
)
def test_pay_scales_between_floor_and_target(estimate: float, expected: int) -> None:
    assert pay_component(estimate, profile()).score == expected


def test_a_floor_alone_is_used_as_the_target_too() -> None:
    assert pay_component(12, profile(salary_target_lpa=None)).score == 100


# --- company -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (VerdictLabel.VERIFIED, 100),
        (VerdictLabel.LIKELY_GENUINE, 75),
        (VerdictLabel.NEEDS_CHECK, 40),
        (VerdictLabel.SUSPICIOUS, 0),
        (None, None),
    ],
)
def test_company_score_follows_the_verification_verdict(
    verdict: VerdictLabel | None, expected: int | None
) -> None:
    assert company_component(verdict).score == expected


# --- location and visa ---------------------------------------------------------------------


def loc(
    region: Region | None,
    mode: WorkMode | None = None,
    india: HiringFromIndia | None = None,
    visa: Visa | None = None,
    overrides: dict[str, object] | None = None,
) -> int | None:
    return location_component(region, mode, india, visa, profile(**(overrides or {}))).score


def test_location_rules() -> None:
    assert loc(None) is None
    assert loc(Region.INDIA) == 100
    assert loc(Region.USA) == 20  # not among your regions
    both: dict[str, object] = {"regions": [Region.INDIA, Region.USA]}
    assert loc(Region.USA, india=HiringFromIndia.NO, overrides=both) == 0
    assert loc(Region.USA, WorkMode.REMOTE, HiringFromIndia.YES, overrides=both) == 100
    assert loc(Region.USA, WorkMode.ONSITE, HiringFromIndia.YES, overrides=both) == 70
    needs: dict[str, object] = {
        "regions": [Region.INDIA, Region.USA],
        "needs_visa_sponsorship": True,
    }
    assert loc(Region.USA, WorkMode.ONSITE, None, Visa.NOT_OFFERED, overrides=needs) == 10
    assert loc(Region.USA, WorkMode.ONSITE, None, Visa.SPONSORSHIP_OFFERED, overrides=needs) == 70
    assert loc(Region.USA, WorkMode.ONSITE, None, Visa.UNKNOWN, overrides=needs) == 50


def test_growth_needs_a_reading() -> None:
    assert growth_component(None, None).score is None
    assert growth_component(80, "Owns a product.").score == 80


# --- combining -----------------------------------------------------------------------------


def comp(key: str, score: int | None) -> Component:
    return Component(key, score, "")


def everything(**scores: int | None) -> list[Component]:
    return [comp(key, scores.get(key, 80)) for key in WEIGHTS]


def test_the_total_is_the_weighted_average_of_what_was_measured() -> None:
    total = combine([comp("skills", 100), comp("pay", 0), comp("growth", None)])
    # skills 30 and pay 20 are measured: (30*100 + 20*0) / 50
    assert total.score == 60 and total.coverage == 50


def test_nothing_measured_gives_no_score() -> None:
    total = combine([comp(key, None) for key in WEIGHTS])
    assert (total.score, total.coverage, total.chance, total.priority) == (None, 0, "unknown", None)


@pytest.mark.parametrize(
    ("score", "chance", "priority"),
    [
        (90, "good", "high"),
        (75, "good", "high"),
        (74, "possible", "medium"),
        (55, "possible", "medium"),
        (54, "unlikely", "low"),
    ],
)
def test_chance_and_priority_thresholds(score: int, chance: str, priority: str) -> None:
    total = combine(everything(**{key: score for key in WEIGHTS}))
    assert (total.score, total.chance, total.priority) == (score, chance, priority)


def test_too_little_information_says_unknown_instead_of_guessing() -> None:
    total = combine([comp("skills", 90), comp("growth", 90)])  # 40 percent of the weight
    assert total.coverage == 40 and total.chance == "unknown"


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"skills": 20}, "fewer than a third"),
        ({"location": 0}, "unworkable"),
        ({"company": 0}, "suspicious"),
        ({"seniority": 10}, "much more experience"),
    ],
)
def test_a_blocker_caps_the_chance_whatever_the_total(
    overrides: dict[str, int], blocker: str
) -> None:
    total = combine(everything(**{"pay": 100, "growth": 100, "skills": 100} | overrides))
    assert total.chance == "unlikely"
    assert any(blocker in b for b in total.blockers)


# --- skills in text ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def vocabulary():
    return load_vocabulary(REPO_ROOT / "content")


def found(text: str, vocabulary: Vocabulary) -> set[str]:
    return skills_in(text, vocabulary)


def test_skills_are_found_in_prose_and_lists(vocabulary: Vocabulary) -> None:
    text = "You know Python3, FastAPI and Postgres. Nice: Docker/K8s, CI/CD, Node.js and C++."
    assert found(text, vocabulary) >= {
        "python",
        "fastapi",
        "postgresql",
        "docker",
        "kubernetes",
        "ci/cd",
        "node.js",
        "c++",
    }


def test_one_skill_name_does_not_match_inside_another(vocabulary: Vocabulary) -> None:
    assert found("We use JavaScript and TypeScript daily.", vocabulary) == {
        "javascript",
        "typescript",
    }
    assert "java" not in found("Strong JavaScript skills", vocabulary)
    assert found("Experience with Java.", vocabulary) == {"java"}
    assert "sql" not in found("We use PostgreSQL", vocabulary)
    assert "react" not in found("a reactive approach", vocabulary)
    assert "go" not in found("Ready to go the extra mile", vocabulary)
    assert "golang" in found("Backend in Golang", vocabulary)
    assert "git" not in found("digital transformation, github pages", vocabulary)


def test_aliases_normalise_to_one_name(vocabulary: Vocabulary) -> None:
    assert vocabulary.canonical("Postgres") == vocabulary.canonical("PostgreSQL") == "postgresql"
    assert vocabulary.canonical("  K8S ") == "kubernetes"
    assert vocabulary.canonical("Obscure Tool") == "obscure tool"


def test_the_vocabulary_has_no_duplicate_spellings() -> None:
    import yaml

    entries = yaml.safe_load((REPO_ROOT / "content" / "skills.yaml").read_text(encoding="utf-8"))
    spellings = [s.lower() for e in entries["skills"] for s in [e["name"], *e.get("aliases", [])]]
    assert len(spellings) == len(set(spellings))


def test_a_missing_vocabulary_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_vocabulary(tmp_path)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3+ years of experience with Python", 3),
        ("Minimum 4 yrs relevant experience", 4),
        ("2-4 years experience in backend", 2),
        ("5 to 7 years of professional experience", 5),
        ("Experience: 6+ years", 6),
        ("The company has 10 years of history", None),
        ("Great culture", None),
        ("1 year experience required; 3+ years preferred", 1),  # the smallest number is the bar
    ],
)
def test_years_asked_are_read_only_near_the_word_experience(
    text: str, expected: int | None
) -> None:
    assert years_required(text) == expected


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Senior Backend Engineer", "senior"),
        ("Staff Engineer", "senior"),
        ("Engineering Manager", "senior"),
        ("Junior Developer", "junior"),
        ("Software Engineering Intern", "junior"),
        ("Backend Engineer", None),
    ],
)
def test_title_level(title: str, level: str | None) -> None:
    assert level_of_title(title) == level
