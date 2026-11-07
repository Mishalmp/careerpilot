"""The evidence ladder for pay and interview information, with a fake search service and web.
# covers: the assisted daily apply list (docs/phase-7/11, tasks A03-A06): every answer says where
# it came from, the first level with an answer wins, and sites that forbid automation are not read
"""

import pytest

from careerpilot.core.search import SearchHit
from careerpilot.modules.apply import chain
from careerpilot.modules.apply.enrich import JobFacts, PoolEntry, enrich
from careerpilot.modules.apply.enums import InterviewLevel, ListingKind, PayLevel
from careerpilot.modules.apply.web import JobWeb
from tests.fakes import FakeSearch, FakeWeb

SKILLS = ["python", "fastapi", "postgresql", "docker"]


def skills_of(text: str) -> set[str]:
    return {
        s
        for s in ("python", "fastapi", "postgresql", "docker", "java", "spring")
        if s in text.lower()
    }


def facts(**changes: object) -> JobFacts:
    base: dict[str, object] = {
        "title": "Python Backend Developer",
        "company": "Acme Technologies Pvt Ltd",
        "region": "India",
        "salary_text": None,
        "est_ctc_lpa": None,
        "jd_text": "We build APIs with Python and FastAPI.",
        "jd_url": "https://acme.example/jobs/1",
        "own_urls": frozenset({"https://acme.example/jobs/1"}),
        "skills": SKILLS,
    }
    return JobFacts(**{**base, **changes})  # pyright: ignore[reportArgumentType]


def web_for(search: FakeSearch | None, web: FakeWeb | None = None, pages: int = 3) -> JobWeb:
    return JobWeb(search, (web or FakeWeb()).fetcher(), max_pages=pages)


# --- company names and titles -------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Acme Technologies Pvt. Ltd", "acme"),
        ("Zoho Corporation", "zoho"),
        ("Big Data Labs", "big data"),
        ("X", ""),
        ("Ltd", ""),
    ],
)
def test_company_key(name: str, key: str) -> None:
    assert chain.company_key(name) == key


def test_mentions_company_matches_whole_words_only() -> None:
    assert chain.mentions_company("Acme Pvt Ltd", "Python Developer - Acme | Naukri")
    assert not chain.mentions_company("Acme", "Pacmeter hiring")  # inside another word
    assert not chain.mentions_company("X", "x marks the spot")  # too short to match safely


@pytest.mark.parametrize(
    ("overlap", "a", "b", "kind"),
    [
        (0.8, "Python Developer", "Backend Developer", ListingKind.SAME_JOB),
        (0.2, "Python Developer", "Python Developer", ListingKind.SIMILAR_ROLE),
        (None, "Senior Python Developer", "Python Developer II", ListingKind.SAME_JOB),
        (None, "Python Developer", "Java Developer", ListingKind.SIMILAR_ROLE),
    ],
)
def test_listing_kind(overlap: float | None, a: str, b: str, kind: ListingKind) -> None:
    assert chain.listing_kind(a, b, overlap) is kind


# --- interview sentences -------------------------------------------------------------------


def test_interview_sentences_are_copied_and_ranked() -> None:
    text = (
        "Acme was founded in 2012 and loves coffee. "
        "The interview process has three rounds: a coding test, a technical round on system design, "
        "and an HR round. "
        "We also like hiring good people for this team and we hope you apply today. "
        "There is one screening call first."
    )
    got = chain.interview_sentences(text)
    assert got[0].startswith("The interview process has three rounds")
    assert all(sentence in " ".join(text.split()) for sentence in got)  # copied, never rewritten
    assert not any("coffee" in sentence for sentence in got)


def test_interview_sentences_ignore_nothing_relevant_and_empty() -> None:
    assert chain.interview_sentences("") == []
    assert chain.interview_sentences("Our office has a pantry and a gym for everyone here.") == []


# --- pay ladder -----------------------------------------------------------------------------


async def test_level_1_the_post_states_the_pay_and_nothing_else_is_searched() -> None:
    search = FakeSearch()
    web = web_for(search)
    got = await enrich(facts(salary_text="12-18 LPA"), [], web, skills_of)
    assert got.pay.level is PayLevel.POSTED
    assert (got.pay.low, got.pay.high) == (1_200_000, 1_800_000)
    assert got.pay.evidence[0].title == "This post (salary field)"
    assert [s.found for s in got.pay.tried] == [True]
    assert not any("salary" in q for q in search.queries)  # no search spent on pay


async def test_your_own_estimate_is_labelled_as_yours() -> None:
    got = await enrich(facts(est_ctc_lpa=15.0), [], web_for(None), skills_of)
    assert got.pay.level is PayLevel.POSTED
    assert "your own estimate" in got.pay.label.lower()
    assert got.pay.evidence[0].url is None  # from the tracker, no page


async def test_level_2_the_same_job_on_another_site() -> None:
    hits = [
        SearchHit(
            "Python Backend Developer - Acme Technologies",
            "https://jobs.example.net/acme/python-backend",
            "Acme is hiring. Compensation: 14-20 LPA.",
        ),
        SearchHit("Acme page", "https://acme.example/jobs/1", "this very post"),  # the post itself
        SearchHit("Cooking blog", "https://food.example/acme", "Acme pasta recipes"),  # not a job
    ]
    got = await enrich(facts(), [], web_for(FakeSearch(hits)), skills_of)
    assert got.pay.level is PayLevel.SAME_JOB_ELSEWHERE
    assert (got.pay.low, got.pay.high) == (1_400_000, 2_000_000)
    assert [x.host for x in got.also_listed] == ["jobs.example.net"]  # only the real listing
    assert got.also_listed[0].kind is ListingKind.SAME_JOB
    steps = {s.label: s.found for s in got.pay.tried}
    assert steps == {"This post": False, "The same job on other sites": True}


async def test_the_overlap_of_skills_decides_same_job_versus_similar_role() -> None:
    web = FakeWeb(
        {
            "jobs.example.net/a": "Python FastAPI PostgreSQL Docker. Pay 10 LPA.",
            "jobs.example.net/b": "Java Spring. Pay 30 LPA.",
        }
    )
    hits = [
        SearchHit("Python Backend Developer - Acme", "https://jobs.example.net/a", ""),
        SearchHit("Python Backend Developer II - Acme", "https://jobs.example.net/b", ""),
    ]
    got = await enrich(facts(), [], web_for(FakeSearch(hits), web), skills_of)
    kinds = {x.url: (x.kind, x.overlap, x.opened) for x in got.also_listed}
    assert kinds["https://jobs.example.net/a"] == (ListingKind.SAME_JOB, 1.0, True)
    assert kinds["https://jobs.example.net/b"][0] is ListingKind.SIMILAR_ROLE
    assert got.pay.level is PayLevel.SAME_JOB_ELSEWHERE  # only the same job's figure is used
    assert got.pay.low == 1_000_000


async def test_level_3_an_earlier_post_in_your_tracker() -> None:
    pool = [
        PoolEntry("Acme Technologies", "Senior Python Developer", 16.0, "https://x.example/1"),
        PoolEntry("Acme Technologies", "Marketing Manager", 40.0, None),  # different kind of role
        PoolEntry("Other Co", "Python Developer", 25.0, None),  # another company
    ]
    got = await enrich(facts(), pool, web_for(None), skills_of)
    assert got.pay.level is PayLevel.PREVIOUS_POST
    assert (got.pay.low, got.pay.high, got.pay.n) == (1_600_000, 1_600_000, 1)
    assert "tracker" in got.pay.evidence[0].title


async def test_level_3_from_a_web_page_about_the_company() -> None:
    search = FakeSearch(
        answers={
            "salary": [
                SearchHit(
                    "Python Developer salary at Acme",
                    "https://pay.example.org/acme",
                    "Acme Python developers earn 9 to 12 LPA on average.",
                )
            ]
        }
    )
    got = await enrich(facts(), [], web_for(search), skills_of)
    assert got.pay.level is PayLevel.PREVIOUS_POST
    assert got.pay.evidence[0].url == "https://pay.example.org/acme"
    assert "9 to 12 LPA" in got.pay.evidence[0].quote  # the words it was read from


async def test_level_4_a_market_range_is_labelled_as_not_this_company() -> None:
    pool = [
        PoolEntry(f"Co{i}", "Python Developer", float(lpa), None)
        for i, lpa in enumerate([8, 10, 12, 14, 16])
    ]
    got = await enrich(facts(), pool, web_for(None), skills_of)
    assert got.pay.level is PayLevel.SIMILAR_ROLES
    assert got.pay.n == 5
    assert (got.pay.low, got.pay.mid, got.pay.high) == (1_000_000, 1_200_000, 1_400_000)
    assert "not this company" in got.pay.label
    assert [s.found for s in got.pay.tried] == [False, False, False, True]


async def test_nothing_found_says_what_was_tried() -> None:
    got = await enrich(facts(), [], web_for(FakeSearch([])), skills_of)
    assert got.pay.level is None and got.pay.low is None
    assert len(got.pay.tried) == 4 and not any(s.found for s in got.pay.tried)
    assert got.interview.level is None and len(got.interview.tried) == 3


async def test_without_a_search_service_the_steps_say_the_web_was_not_searched() -> None:
    got = await enrich(facts(), [], web_for(None), skills_of)
    assert got.pay.level is None
    assert any("not searched" in s.note for s in got.pay.tried)


async def test_currencies_are_never_mixed_or_converted() -> None:
    hits = [
        SearchHit(
            "Python Backend Developer - Acme", "https://jobs.example.net/a", "$90,000 - $120,000"
        ),
        SearchHit("Python Backend Developer - Acme", "https://jobs.example.net/b", "INR 12-18 LPA"),
    ]
    got = await enrich(facts(), [], web_for(FakeSearch(hits)), skills_of)
    assert got.pay.currency == "INR"  # rupees win when present; dollars are left out, not converted
    assert got.pay.low == 1_200_000


# --- sites that forbid automation -------------------------------------------------------------


async def test_a_blocked_site_is_listed_but_never_opened_or_used_as_evidence() -> None:
    web = FakeWeb({"www.linkedin.com/jobs/view/1": "Pay 99 LPA"})
    hits = [
        SearchHit(
            "Python Backend Developer - Acme | LinkedIn",
            "https://www.linkedin.com/jobs/view/1",
            "Acme pays 99 LPA",
        )
    ]
    got = await enrich(facts(), [], web_for(FakeSearch(hits), web), skills_of)
    assert [x.host for x in got.also_listed] == ["linkedin.com"]
    assert got.also_listed[0].opened is False and got.also_listed[0].overlap is None
    assert got.pay.level is None  # its snippet was not used
    assert web.requests == []  # and the page was never requested


# --- budgets ----------------------------------------------------------------------------------


async def test_a_job_never_spends_more_than_five_searches() -> None:
    search = FakeSearch([])
    await enrich(facts(), [], web_for(search), skills_of)
    assert len(search.queries) == 5


async def test_the_page_budget_is_respected() -> None:
    hits = [
        SearchHit(f"Python Backend Developer - Acme {i}", f"https://jobs.example.net/{i}", "")
        for i in range(6)
    ]
    web = FakeWeb({f"jobs.example.net/{i}": "Python FastAPI. Pay 10 LPA." for i in range(6)})
    job_web = web_for(FakeSearch(hits), web, pages=1)
    await enrich(facts(), [], job_web, skills_of)
    assert len(web.requests) <= 1 and job_web.pages_used <= 1


async def test_a_failing_search_service_does_not_fail_the_job() -> None:
    job_web = web_for(FakeSearch(fail_after=0))
    got = await enrich(facts(), [], job_web, skills_of)
    assert got.pay.level is None
    assert any("Web search stopped" in n for n in job_web.notes)


# --- interview ladder -----------------------------------------------------------------------


async def test_interview_level_1_the_post_describes_the_process() -> None:
    jd = "Our interview process has two rounds: a coding test and a technical discussion with the team."
    got = await enrich(facts(jd_text=jd), [], web_for(FakeSearch([])), skills_of)
    assert got.interview.level is InterviewLevel.POSTED
    assert got.interview.points[0].quote in jd


async def test_interview_level_2_the_company_process_from_a_page() -> None:
    page = "Acme interviews are friendly. The Acme interview has three rounds: coding, system design and HR."
    search = FakeSearch(
        answers={
            "interview process Python": [
                SearchHit("Acme interview process", "https://glassdoor-like.example.org/acme", "")
            ]
        }
    )
    web = FakeWeb({"glassdoor-like.example.org/acme": page})
    got = await enrich(facts(), [], web_for(search, web), skills_of)
    assert got.interview.level is InterviewLevel.THIS_COMPANY
    point = got.interview.points[0]
    assert str(point.url) == "https://glassdoor-like.example.org/acme"
    assert point.quote in page


async def test_interview_level_3_typical_for_the_role_is_labelled_as_not_this_company() -> None:
    page = "A typical Python Developer interview has a screening call, a coding round and a design round."
    search = FakeSearch(
        answers={
            "rounds questions": [
                SearchHit("Python Developer interview guide", "https://guide.example.org/py", "")
            ]
        }
    )
    web = FakeWeb({"guide.example.org/py": page})
    got = await enrich(facts(), [], web_for(search, web), skills_of)
    assert got.interview.level is InterviewLevel.SIMILAR_ROLES
    assert "not this company" in got.interview.label


def test_titles_and_marketing_lines_are_not_interview_descriptions() -> None:
    """Found in the first real run: search results gave page titles as "interview information"."""
    for line in (
        "Databricks Interview Questions and Answers: 2026 Edition | DataCamp.",
        "Clear Interview Process and Insider Insights - Databricks.",
        "Take a mock interview with a real engineer from our team today.",
        "The interview process is something that every candidate wonders about a lot.",  # no detail
    ):
        assert chain.interview_sentences(line) == [], line
    good = (
        "The stages: a recruiter screen, one or two technical coding screens, then a virtual "
        "onsite with four interviews covering algorithms and system design."
    )
    assert chain.interview_sentences(good) == [good]


async def test_the_search_result_title_is_never_used_as_interview_evidence() -> None:
    search = FakeSearch(
        answers={
            "interview process Python": [
                SearchHit(
                    "Acme interview process: three rounds, coding and system design",
                    "https://guide.example.org/acme",
                    "Great place.",
                )
            ]
        }
    )
    got = await enrich(facts(), [], web_for(search), skills_of)
    assert got.interview.level is None  # the title mentions rounds, but only the snippet counts
