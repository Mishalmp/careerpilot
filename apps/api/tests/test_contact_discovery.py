"""Published hiring addresses found on a company's own website: rules only, with their source.
# covers: contact discovery (docs/phase-7/14): role addresses on the company's domain only, each
# stored with the page it came from, nothing guessed, no model call
"""

from fastapi import FastAPI
from httpx import AsyncClient

from careerpilot.modules.outreach.contacts import role_addresses, site_domain
from tests.fakes import FakeLlm, FakeWeb

JOBS = "/api/v1/jobs"


def test_the_domain_is_the_host_without_www() -> None:
    assert site_domain("https://www.acme.co.in/about") == "acme.co.in"
    assert site_domain("acme.com") == "acme.com"
    assert site_domain("") is None


def test_only_role_addresses_on_the_companys_own_domain_are_taken() -> None:
    text = (
        "Write to careers@acme.com or Jobs@Acme.com. Our CEO jane.doe@acme.com is busy. "
        "Partner: hr@partner.com. Subdomain: talent@eu.acme.com. Fake: hr@notacme.com. "
        "careers@acme.com again."
    )
    assert role_addresses(text, "acme.com") == [
        "careers@acme.com",
        "jobs@acme.com",
        "talent@eu.acme.com",
    ]


async def job_with_site(
    api: AsyncClient, website: str | None = "https://acme.example", company: str = "Acme"
) -> str:
    created = await api.post(JOBS, json={"company_name": company, "title": "Backend Engineer"})
    assert created.status_code in (200, 201), created.text
    job = created.json()["id"]
    if website:
        patched = await api.patch(f"{JOBS}/{job}/company", json={"website": website})
        assert patched.status_code == 200, patched.text
    return job


async def test_addresses_are_kept_as_published_contacts_with_their_page(
    app: FastAPI, api: AsyncClient
) -> None:
    llm = FakeLlm("{}")
    app.state.llm = llm
    web = FakeWeb(
        {
            "acme.example/careers": (
                "<html><body>Join us. Mail careers@acme.example or ceo.name@acme.example</body></html>",
                "text/html",
            ),
            "acme.example/contact": (
                "<html><body>Hello: info@acme.example, spam@elsewhere.example</body></html>",
                "text/html",
            ),
        }
    )
    app.state.fetcher = web.fetcher()
    job = await job_with_site(api)

    result = (await api.post(f"{JOBS}/{job}/contacts/find")).json()
    got = {c["email"]: c for c in result["added"]}
    assert set(got) == {"careers@acme.example", "info@acme.example"}
    assert got["careers@acme.example"]["kind"] == "published_business"
    assert got["careers@acme.example"]["source_url"] == "https://acme.example/careers"
    assert result["pages_read"] == 2 and llm.calls == []

    again = (await api.post(f"{JOBS}/{job}/contacts/find")).json()
    assert again["added"] == [] and again["already_known"] == 2  # nothing duplicated

    detail = (await api.get(f"{JOBS}/{job}")).json()
    assert {c["email"] for c in detail["contacts"]} == set(got)


async def test_no_website_or_no_address_is_explained(app: FastAPI, api: AsyncClient) -> None:
    app.state.fetcher = FakeWeb({"acme.example/": ("<html>Hi</html>", "text/html")}).fetcher()
    bare = await job_with_site(api, website=None)
    refused = await api.post(f"{JOBS}/{bare}/contacts/find")
    assert refused.status_code == 422 and refused.json()["title"] == "No company website"

    other = await job_with_site(api, company="Globex", website="https://acme.example")
    result = (await api.post(f"{JOBS}/{other}/contacts/find")).json()
    assert result["added"] == [] and any("None of the pages" in n for n in result["notes"])


async def test_another_owners_job_is_not_found(
    app: FastAPI, api: AsyncClient, other_api: AsyncClient
) -> None:
    app.state.fetcher = FakeWeb({}).fetcher()
    job = await job_with_site(api)
    assert (await other_api.post(f"{JOBS}/{job}/contacts/find")).status_code == 404
