"""Pasted job links: read from the address alone, never opened."""

import pytest
from httpx import AsyncClient

from careerpilot.modules.tracker.enums import Portal
from careerpilot.modules.tracker.links import UNKNOWN_COMPANY, guess_link

JOBS = "/api/v1/jobs"


@pytest.mark.parametrize(
    ("url", "portal", "title", "company", "clean"),
    [
        (
            "https://www.linkedin.com/jobs/view/senior-python-developer-at-acme-corp-3812345678/"
            "?refId=abc&trackingId=xyz",
            Portal.LINKEDIN,
            "Senior Python Developer",
            "Acme Corp",
            "https://www.linkedin.com/jobs/view/3812345678/",
        ),
        (
            "https://in.linkedin.com/jobs/view/3812345678",
            Portal.LINKEDIN,
            "Job on LinkedIn (3812345678)",
            UNKNOWN_COMPANY,
            "https://www.linkedin.com/jobs/view/3812345678/",
        ),
        (
            "https://www.linkedin.com/jobs/collections/recommended/?currentJobId=3999999999",
            Portal.LINKEDIN,
            "Job on LinkedIn (3999999999)",
            UNKNOWN_COMPANY,
            "https://www.linkedin.com/jobs/view/3999999999/",
        ),
        (
            "https://in.indeed.com/viewjob?jk=abcdef1234567890&from=serp&vjs=3",
            Portal.INDEED,
            "Job on Indeed (abcdef12)",
            UNKNOWN_COMPANY,
            "https://in.indeed.com/viewjob?jk=abcdef1234567890",
        ),
        (
            "https://www.naukri.com/job-listings-python-developer-acme-technologies-bengaluru-"
            "2-to-5-years-120924001234?src=x",
            Portal.NAUKRI,
            "Python Developer Acme Technologies Bengaluru",
            UNKNOWN_COMPANY,
            "https://www.naukri.com/job-listings-python-developer-acme-technologies-bengaluru-"
            "2-to-5-years-120924001234",
        ),
        (
            "https://boards.greenhouse.io/razorpay/jobs/4567890",
            Portal.OTHER,
            "Job on Other",
            "Razorpay",
            "https://boards.greenhouse.io/razorpay/jobs/4567890",
        ),
        (
            "https://careers.acme.com/jobs/backend-engineer",
            Portal.OTHER,
            "Backend Engineer",
            "Acme",
            "https://careers.acme.com/jobs/backend-engineer",
        ),
        (
            "https://weworkremotely.com/remote-jobs/acme-python-dev",
            Portal.WE_WORK_REMOTELY,
            "Job on We Work Remotely",
            UNKNOWN_COMPANY,
            "https://weworkremotely.com/remote-jobs/acme-python-dev",
        ),
    ],
)
def test_the_address_alone_gives_portal_clean_link_and_what_it_spells(
    url: str, portal: Portal, title: str, company: str, clean: str
) -> None:
    guess = guess_link(url)
    assert (guess.portal, guess.title, guess.company, guess.url) == (portal, title, company, clean)


def test_a_look_alike_host_is_not_taken_for_the_portal() -> None:
    assert guess_link("https://notlinkedin.com/jobs/view/3812345678").portal is Portal.OTHER
    assert (
        guess_link("https://linkedin.com.evil.example/jobs/view/3812345678").portal is Portal.OTHER
    )


async def test_links_become_jobs_with_the_portal_and_the_link_to_click(api: AsyncClient) -> None:
    body = {
        "links": [
            "https://www.linkedin.com/jobs/view/backend-engineer-at-zeta-3700000001/?trk=1",
            "https://in.indeed.com/viewjob?jk=0123456789abcdef",
            "https://www.linkedin.com/jobs/view/backend-engineer-at-zeta-3700000001/",  # same job
            "not a link",
            "javascript:alert(1)",
            "",
        ]
    }
    first = await api.post(f"{JOBS}/links", json=body)
    assert first.status_code == 200
    results = first.json()["results"]
    assert [r["status"] for r in results] == ["added", "added", "rejected", "rejected"]
    assert results[0]["title"] == "Backend Engineer" and results[0]["company"] == "Zeta"
    assert results[0]["needs_details"] is False and results[1]["needs_details"] is True

    job = (await api.get(f"{JOBS}/{results[0]['job_id']}")).json()
    assert job["source"] == "LinkedIn"
    assert job["apply_url"] == job["jd_url"] == "https://www.linkedin.com/jobs/view/3700000001/"

    again = await api.post(f"{JOBS}/links", json={"links": [body["links"][0]]})
    assert again.json()["results"][0]["status"] == "already_saved"
    assert again.json()["results"][0]["job_id"] == results[0]["job_id"]


async def test_at_most_fifty_links_at_once(api: AsyncClient) -> None:
    many = [f"https://careers.example.com/jobs/{n}" for n in range(51)]
    assert (await api.post(f"{JOBS}/links", json={"links": many})).status_code == 422


async def test_saved_links_belong_to_their_owner(api: AsyncClient, other_api: AsyncClient) -> None:
    link = "https://www.linkedin.com/jobs/view/backend-engineer-at-zeta-3700000002/"
    mine = (await api.post(f"{JOBS}/links", json={"links": [link]})).json()["results"][0]
    theirs = (await other_api.post(f"{JOBS}/links", json={"links": [link]})).json()["results"][0]
    assert theirs["status"] == "added" and theirs["job_id"] != mine["job_id"]
    assert (await other_api.get(f"{JOBS}/{mine['job_id']}")).status_code == 404


async def test_the_route_needs_a_session() -> None:
    from httpx import ASGITransport

    from careerpilot.main import create_app

    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://localhost"
    ) as anonymous:
        assert (await anonymous.post(f"{JOBS}/links", json={"links": []})).status_code == 401
