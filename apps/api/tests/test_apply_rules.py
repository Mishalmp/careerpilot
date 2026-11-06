"""Pay figures, ranges, role matching and the policy file.
# covers: the assisted daily apply list (docs/phase-7/11, tasks A01, A02): nothing is guessed silently
"""

from datetime import date
from pathlib import Path

import pytest

from careerpilot.modules.apply import matching, pay
from careerpilot.modules.apply.policy import Policy, PolicyProblem, load_policy


def figures(text: str) -> list[tuple[str, float, float | None]]:
    return [(f.currency, f.low, f.high) for f in pay.find_pay(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Salary: 12-18 LPA based on experience", [("INR", 1_200_000, 1_800_000)]),
        ("CTC Rs. 15 lakhs per annum", [("INR", 1_500_000, None)]),
        ("INR 12 to 18 LPA", [("INR", 1_200_000, 1_800_000)]),
        ("₹ 20 - 30 LPA", [("INR", 2_000_000, 3_000_000)]),
        ("INR 1,200,000 - 1,800,000", [("INR", 1_200_000, 1_800_000)]),
        ("Rs 75,000 per month", [("INR", 900_000, None)]),
        ("$90,000 - $120,000 a year", [("USD", 90_000, 120_000)]),
        ("USD 90k-120k", [("USD", 90_000, 120_000)]),
        ("EUR 70,000", [("EUR", 70_000, None)]),
        ("£60k", [("GBP", 60_000, None)]),
        ("$45 per hour", []),  # hourly is not yearly pay
        ("$5,000 per month", [("USD", 60_000, None)]),
        (
            "2 years of experience and 5 lakh lines of code",
            [],
        ),  # "lakh" without "per annum" is not pay
        ("Upto 700 LPA", []),  # implausible
        ("No pay information here", []),
        ("", []),
    ],
)
def test_pay_table(text: str, expected: list[tuple[str, float, float | None]]) -> None:
    assert figures(text) == expected


def test_every_figure_carries_the_words_it_came_from() -> None:
    text = (
        "We are hiring a backend engineer in Pune. Compensation is 12-18 LPA plus bonus. Apply now."
    )
    (figure,) = pay.find_pay(text)
    assert "12-18 LPA" in figure.quote
    assert figure.quote in " ".join(text.split())  # the quote is real text from the source
    assert figure.lpa == (12.0, 18.0)


def test_the_same_amount_is_not_counted_twice() -> None:
    assert len(pay.find_pay("INR 12-18 LPA (that is Rs 1,200,000 - 1,800,000)")) == 2
    assert len(pay.find_pay("12-18 LPA")) == 1


def test_summarise_ranges() -> None:
    assert pay.summarise([]) is None
    one = pay.summarise([10.0])
    assert one and (one.low, one.mid, one.high, one.n) == (10.0, 10.0, 10.0, 1)
    two = pay.summarise([10.0, 20.0])
    assert two and (two.low, two.high, two.mid) == (10.0, 20.0, 15.0)
    many = pay.summarise([10, 12, 14, 16, 18, 20, 100])
    assert many and many.n == 7
    assert (
        many.mid == 16 and many.low < many.mid < many.high < 100
    )  # an outlier does not stretch it


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Senior Python Backend Developer", "Python Backend Engineer", True),
        ("Software Engineer", "Python Full Stack Developer", True),  # a plain role is close to any
        ("SDE 2", "Software Developer", True),
        ("Python Developer", "Java Developer", False),
        ("Marketing Manager", "Software Engineer", False),
        ("Data Engineer", "Backend Engineer", False),
    ],
)
def test_similar_titles(a: str, b: str, same: bool) -> None:
    assert matching.similar_titles(a, b) is same
    assert matching.similar_titles(b, a) is same  # symmetric


TODAY = date(2026, 11, 7)


def test_match_scores_and_explains_itself() -> None:
    m = matching.match(
        job_title="Senior Python Backend Developer",
        job_skills=["python", "fastapi", "postgresql", "kafka"],
        profile_skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        profile_titles=["Python Full Stack Developer"],
        posted_on=date(2026, 11, 1),
        today=TODAY,
    )
    assert m.score == 45 + 30 + 10  # 3 of 4 skills, similar title, fresh
    assert m.shared_skills == ["fastapi", "postgresql", "python"]
    assert any("3 of the 4 skills" in r for r in m.reasons)
    assert any("like one on your CV" in r for r in m.reasons)


def test_unknowns_are_neutral_and_said_out_loud() -> None:
    m = matching.match(
        job_title="Engineer II",
        job_skills=[],
        profile_skills=["python"],
        profile_titles=[],
        posted_on=None,
        today=TODAY,
    )
    assert m.score == 30 + 0 + 5
    assert any("names no skills" in r for r in m.reasons)
    assert any("No posting date" in r for r in m.reasons)


def test_old_posts_lose_the_freshness_points() -> None:
    m = matching.match(
        job_title="X Developer",
        job_skills=["python"],
        profile_skills=["python"],
        profile_titles=[],
        posted_on=date(2026, 9, 1),
        today=TODAY,
    )
    assert m.score == 60


def test_requirement_overlap() -> None:
    assert matching.requirement_overlap([], []) is None
    assert matching.requirement_overlap(["python", "sql"], ["Python", "SQL"]) == 1.0
    assert matching.requirement_overlap(["python", "sql"], ["python", "java"]) == pytest.approx(
        1 / 3
    )
    assert matching.requirement_overlap(["python"], []) == 0.0


# --- policy file ---------------------------------------------------------------------------------


def test_defaults_apply_when_no_file_exists(tmp_path: Path) -> None:
    policy, source = load_policy(tmp_path)
    assert policy == Policy() and source == "built-in defaults"
    assert policy.daily_limit == 3 and policy.block_if_company_suspicious is True


def test_the_private_file_wins_over_the_example(tmp_path: Path) -> None:
    (tmp_path / "private").mkdir()
    (tmp_path / "apply-policy.example.yaml").write_text("daily_limit: 5\n", encoding="utf-8")
    (tmp_path / "private" / "apply-policy.yaml").write_text(
        "daily_limit: 2\nregions: [India]\n", encoding="utf-8"
    )
    policy, source = load_policy(tmp_path)
    assert (policy.daily_limit, policy.regions, source) == (
        2,
        ["India"],
        "private/apply-policy.yaml",
    )


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        ("daily_limit: 99\n", "daily_limit"),
        ("daily_limit: three\n", "daily_limit"),
        ("auto_submit: true\n", "auto_submit"),  # a setting that must not exist
        ("work_modes: [Underwater]\n", "work_modes"),
        ("min_match_score: -1\n", "min_match_score"),
        ("daily_limit: [1\n", "not valid YAML"),
        ("- just\n- a list\n", "must be a list of settings"),
    ],
)
def test_a_bad_file_gives_plain_problems_instead_of_silent_defaults(
    tmp_path: Path, content: str, fragment: str
) -> None:
    (tmp_path / "apply-policy.example.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(PolicyProblem) as info:
        load_policy(tmp_path)
    assert fragment in str(info.value)


def test_the_shipped_example_is_valid_and_has_no_auto_submit() -> None:
    from careerpilot.core.config import REPO_ROOT

    _policy, source = load_policy(REPO_ROOT / "content")
    assert source in ("private/apply-policy.yaml", "apply-policy.example.yaml")
    assert "auto_submit" not in Policy.model_fields
