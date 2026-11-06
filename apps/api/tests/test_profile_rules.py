"""Reading a CV: titles, years, list cleaning.
# covers: REQ-28 (profile derived from the CV, no hard-coded role list)
"""

import pytest

from careerpilot.modules.profile import rules

CV = """
Mishal MP
Software Engineer, Acme Corp (2022 - present)
- Built Python Full Stack applications; promoted from Junior Software Developer.
- Senior Python Full Stack Developer on the payments team.
Python Full Stack Developer at Beta Ltd, 2 years experience.
5+ years of professional experience in backend development.
SDE 2 level responsibilities. Interested in Software Developer roles.
"""


def test_titles_come_from_the_cv_most_frequent_first() -> None:
    titles = rules.role_titles(CV)
    assert "Python Full Stack Developer" in titles
    assert "Software Engineer" in titles
    assert "Software Developer" in titles
    assert "SDE" in titles
    assert not any(t.startswith(("Senior ", "Junior ")) for t in titles)
    # Both are named twice (once with a seniority word); the one that appears first wins a tie.
    assert set(titles[:2]) == {"Python Full Stack Developer", "Software Developer"}
    assert len(titles) <= rules.MAX_TITLES


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Senior Backend Engineer", ["Backend Engineer"]),  # seniority is not part of the role
        ("Worked as a data engineer and a Data Engineer", ["Data Engineer"]),
        ("SDE-2 at Acme", ["SDE"]),
        ("SDE II and SDE 3", ["SDE"]),
        ("An engineer who likes tea", []),  # a bare noun says nothing
        ("Developer", []),
        ("", []),
    ],
)
def test_title_extraction_table(text: str, expected: list[str]) -> None:
    got = rules.role_titles(text)
    assert got == expected


def test_titles_are_bounded() -> None:
    many = "\n".join(
        f"Senior {a} Engineer"
        for a in [
            "Python",
            "Java",
            "Data",
            "Cloud",
            "Platform",
            "Web",
            "Mobile",
            "Security",
            "Test",
            "QA",
        ]
    )
    assert len(rules.role_titles(many)) == rules.MAX_TITLES


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("5+ years of professional experience", 5),
        ("Total experience: 3 yrs", 3),
        ("2 years experience at X and 4 years experience at Y", 4),
        ("Founded in 1998, 25 years in the industry", 25),
        ("It took 3 years to build a house", None),  # not about experience
        ("experience: 99 years", None),  # implausible
        ("no numbers here", None),
    ],
)
def test_years_table(text: str, years: int | None) -> None:
    assert rules.years_experience(text) == years


def test_clean_list_trims_dedupes_and_bounds() -> None:
    got = rules.clean_list(["  Python ", "python", "", "  Go  Lang ", "x" * 100], limit=3)
    assert got == ["Python", "Go Lang", "x" * 60]
    assert rules.clean_list([], limit=5) == []
