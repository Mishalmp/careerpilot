"""Account setup: answers, links, CV files (PDF, Word, text, scans), GitHub, and scoring from them.
# covers: REQ-28 (nothing about one person is hard-coded; account setup tells the app who you are)
"""

import io
import zipfile
from typing import Any, get_args

from fastapi import FastAPI
from httpx import AsyncClient
from PIL import Image

from careerpilot.modules.profile import cvfile, github, rules
from careerpilot.modules.profile.schemas import RegionName, WorkModeName
from careerpilot.modules.tracker.enums import Region, WorkMode
from tests.fakes import FakeWeb

BASE = "/api/v1/profile"
CV_TEXT = (
    "Priya Sharma\nSenior Python Backend Developer at Acme (2021 - present). 5 years of experience.\n"
    "Built REST APIs with FastAPI and Django on PostgreSQL and Docker. React and TypeScript front ends.\n"
)


def minimal_pdf(text: str) -> bytes:
    """A one-page PDF with a text layer, written by hand (no PDF library needed to make it)."""
    stream = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def scanned_pdf() -> bytes:
    """A PDF whose only content is a picture: it has no text layer, like a scan."""
    buffer = io.BytesIO()
    Image.new("RGB", (200, 100), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def docx(text: str) -> bytes:
    paragraphs = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
    xml = f'<?xml version="1.0"?><w:document xmlns:w="x"><w:body>{paragraphs}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


async def upload(
    api: AsyncClient, data: bytes, name: str = "cv.pdf", type_: str = "application/pdf"
) -> Any:
    return await api.post(f"{BASE}/cv/file", files={"file": (name, data, type_)})


def no_ocr() -> None:
    return None


def fake_ocr() -> cvfile.OcrEngine:
    def read(_image: bytes) -> str:
        return CV_TEXT

    return read


# --- the answers -----------------------------------------------------------------------------


def test_the_typed_choices_equal_the_tracker_enums() -> None:
    assert set(get_args(RegionName)) == {r.value for r in Region}
    assert set(get_args(WorkModeName)) == {m.value for m in WorkMode}


async def test_setup_answers_are_saved_and_completion_says_what_is_missing(
    api: AsyncClient,
) -> None:
    early = await api.post(f"{BASE}/setup/complete")
    assert early.status_code == 422 and "your name" in early.json()["detail"]

    body = (
        await api.patch(
            BASE,
            json={
                "full_name": "  Priya Sharma ",
                "current_role": "Backend Developer",
                "location": "Pune",
                "target_roles": ["Python Developer", "python developer", "SDE"],
                "target_levels": ["mid", "senior"],
                "regions": ["India", "Remote (Global)"],
                "work_modes": ["Remote", "Hybrid"],
                "needs_visa": True,
                "salary_floor_lpa": 18,
                "salary_target_lpa": "30.5",
                "skills": ["Python", "SQL"],
            },
        )
    ).json()
    assert body["full_name"] == "Priya Sharma"
    assert body["target_roles"] == ["Python Developer", "SDE"]  # duplicates ignoring case dropped
    assert body["regions"] == ["India", "Remote (Global)"] and body["needs_visa"] is True
    assert body["salary_floor_lpa"] == 18 and body["salary_target_lpa"] == 30.5
    assert body["setup"] == {"complete": False, "completed_at": None, "missing": []}

    done = (await api.post(f"{BASE}/setup/complete")).json()
    assert done["setup"]["complete"] is True and done["setup"]["completed_at"]


async def test_bad_answers_are_refused_with_the_field(api: AsyncClient) -> None:
    for payload in (
        {"regions": ["Atlantis"]},
        {"work_modes": ["Underwater"]},
        {"target_levels": ["wizard"]},
        {"salary_floor_lpa": 40, "salary_target_lpa": 20},
        {"salary_floor_lpa": -1},
        {"target_roles": [""]},
        {"links": [{"kind": "github", "url": "https://example.com/me"}]},
        {"links": [{"kind": "other", "url": "javascript:alert(1)"}]},
    ):
        response = await api.patch(BASE, json=payload)
        assert response.status_code == 422, payload


async def test_links_are_kept_and_must_be_on_the_site_they_claim(api: AsyncClient) -> None:
    links = [
        {"kind": "github", "url": "https://github.com/octocat"},
        {"kind": "linkedin", "url": "https://www.linkedin.com/in/priya"},
        {"kind": "leetcode", "url": "https://leetcode.com/u/priya"},
        {"kind": "naukri", "url": "https://www.naukri.com/mnjuser/profile"},
        {"kind": "portfolio", "url": "https://priya.dev"},
    ]
    body = (await api.patch(BASE, json={"links": links})).json()
    assert body["links"] == links
    lookalike = [{"kind": "github", "url": "https://github.com.evil.example/octocat"}]
    assert (await api.patch(BASE, json={"links": lookalike})).status_code == 422


async def test_one_user_cannot_see_anothers_profile(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    await api.patch(BASE, json={"full_name": "Priya Sharma"})
    assert (await other_api.get(BASE)).json()["full_name"] is None
    assert (await other_api.post(f"{BASE}/setup/complete")).status_code == 422


# --- CV files --------------------------------------------------------------------------------


async def test_a_text_pdf_is_read_and_fills_the_profile_and_the_empty_name(
    api: AsyncClient,
) -> None:
    response = await upload(
        api, minimal_pdf("Senior Python Developer with 6 years of experience on FastAPI and Docker")
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["profile"]["cv"] == {
        "has_cv": True,
        "source": "pdf",
        "filename": "cv.pdf",
        "chars": body["profile"]["cv"]["chars"],
    }
    assert {"python", "fastapi", "docker"} <= set(body["profile"]["skills"])
    assert body["profile"]["years_experience"] == 6


async def test_a_word_file_is_read_and_the_name_is_guessed_only_when_empty(
    api: AsyncClient,
) -> None:
    response = await upload(api, docx(CV_TEXT), "Priya CV.docx", "application/octet-stream")
    body = response.json()
    assert body["profile"]["cv"]["source"] == "docx"
    assert body["profile"]["full_name"] == "Priya Sharma"
    assert any("name" in n for n in body["notes"])
    assert body["profile"]["current_role"] == "Python Backend Developer"

    await api.patch(BASE, json={"full_name": "P. Sharma"})
    again = (await upload(api, docx(CV_TEXT), "cv.docx", "application/octet-stream")).json()
    assert again["profile"]["full_name"] == "P. Sharma"  # a name you typed is never overwritten


async def test_a_text_file_works_and_a_wrong_type_is_refused_by_its_bytes(
    api: AsyncClient,
) -> None:
    ok = await upload(api, CV_TEXT.encode(), "cv.txt", "text/plain")
    assert ok.status_code == 200 and ok.json()["profile"]["cv"]["source"] == "text"
    binary = await upload(api, bytes(range(256)) * 20, "cv.pdf", "application/pdf")
    assert binary.status_code == 422  # named .pdf, but it is not one
    assert (await upload(api, b"", "cv.txt", "text/plain")).status_code == 422


async def test_a_scanned_pdf_says_ocr_is_needed_when_it_is_not_installed(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.ocr = no_ocr
    response = await upload(api, scanned_pdf())
    assert response.status_code == 422
    assert "OCR" in response.json()["detail"] and "paste" in response.json()["detail"]


async def test_a_scanned_pdf_and_a_picture_are_read_with_ocr_when_it_is_there(
    app: FastAPI, api: AsyncClient
) -> None:
    app.state.ocr = fake_ocr  # a stand-in engine that "reads" the text
    scan = (await upload(api, scanned_pdf())).json()
    assert scan["profile"]["cv"]["source"] == "ocr"
    assert any("OCR" in n for n in scan["notes"]) and "python" in scan["profile"]["skills"]
    buffer = io.BytesIO()
    Image.new("RGB", (50, 50), "white").save(buffer, format="PNG")
    picture = (await upload(api, buffer.getvalue(), "cv.png", "image/png")).json()
    assert picture["profile"]["cv"]["source"] == "ocr"


async def test_a_hostile_word_file_is_refused_not_unpacked(api: AsyncClient) -> None:
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"A" * 25_000_000)  # tiny when compressed
    response = await upload(api, bomb.getvalue(), "cv.docx", "application/octet-stream")
    assert response.status_code == 422 and "too large" in response.json()["detail"]
    assert (await upload(api, docx("x\n" * 3), "cv.docx", "x")).status_code == 422  # too short
    not_word = io.BytesIO()
    with zipfile.ZipFile(not_word, "w") as archive:
        archive.writestr("hello.txt", "hi")
    assert (await upload(api, not_word.getvalue(), "cv.docx", "x")).status_code == 422


async def test_a_file_over_the_size_limit_is_refused(api: AsyncClient) -> None:
    response = await upload(api, b"%PDF-" + b"0" * (cvfile.MAX_BYTES + 10))
    assert response.status_code == 413


async def test_an_upload_needs_a_session_and_the_file_is_not_stored(
    client: AsyncClient, api: AsyncClient
) -> None:
    anonymous = await client.post(f"{BASE}/cv/file", files={"file": ("a.txt", b"x", "text/plain")})
    assert anonymous.status_code == 401
    await upload(api, CV_TEXT.encode(), "cv.txt", "text/plain")
    assert "cv_text" not in (await api.get(BASE)).text  # the CV text is never returned


def test_the_file_name_is_reduced_to_a_name() -> None:
    assert cvfile.safe_filename("C:\\Users\\me\\cv.pdf") == "cv.pdf"
    assert cvfile.safe_filename("../../etc/passwd") == "passwd"
    assert cvfile.safe_filename("a\x00b\x07.pdf") == "ab.pdf"
    assert cvfile.safe_filename(None) is None and cvfile.safe_filename("///") is None


def test_name_guessing_is_careful() -> None:
    assert rules.guess_name("Priya Sharma\nPython developer") == "Priya Sharma"
    assert rules.guess_name("PRIYA SHARMA\nx") == "Priya Sharma"
    assert rules.guess_name("Curriculum Vitae\nPriya Sharma") is None
    assert rules.guess_name("Senior Python Developer\n") is None
    assert rules.guess_name("priya@example.com") is None
    assert rules.guess_name("") is None


# --- GitHub ----------------------------------------------------------------------------------

REPOS = (
    '[{"name":"shop-api","language":"Python","fork":false,"description":"FastAPI and PostgreSQL shop"},'
    '{"name":"dots","language":"Shell","fork":false,"description":null},'
    '{"name":"forked-lib","language":"Rust","fork":true,"description":"not mine"},'
    '{"name":"ui","language":"TypeScript","fork":false,"description":"React dashboard"}]'
)
GITHUB_URL = "api.github.com/users/octocat/repos?per_page=100&sort=pushed&type=owner"


def test_github_usernames_come_only_from_profile_links() -> None:
    assert github.username("https://github.com/octocat") == "octocat"
    assert github.username("https://www.github.com/octocat/repo") == "octocat"
    assert github.username("https://github.com/") is None
    assert github.username("https://github.com/orgs/x") is None
    assert github.username("https://gitlab.com/octocat") is None


async def test_github_languages_become_suggestions_not_saved_changes(
    app: FastAPI, api: AsyncClient, content: Any
) -> None:
    app.state.fetcher = FakeWeb({GITHUB_URL: (REPOS, "application/json")}).fetcher()
    assert (await api.post(f"{BASE}/github/read")).status_code == 409  # no link yet
    await api.patch(
        BASE,
        json={
            "links": [{"kind": "github", "url": "https://github.com/octocat"}],
            "skills": ["python"],
        },
    )
    body = (await api.post(f"{BASE}/github/read")).json()
    assert body["username"] == "octocat" and body["repos_read"] == 3  # the fork is not counted
    assert {"name": "Python", "repos": 1} in body["languages"]
    assert "Rust" not in [x["name"] for x in body["languages"]]
    assert {"typescript", "react", "fastapi", "postgresql"} <= set(body["suggested_skills"])
    assert "python" not in body["suggested_skills"]  # already yours
    assert (await api.get(BASE)).json()["skills"] == ["python"]  # nothing was saved


async def test_github_problems_are_explained(app: FastAPI, api: AsyncClient) -> None:
    await api.patch(BASE, json={"links": [{"kind": "github", "url": "https://github.com/octocat"}]})
    app.state.fetcher = FakeWeb(
        {GITHUB_URL: ('{"message":"API rate limit exceeded"}', "application/json", 403)}
    ).fetcher()
    response = await api.post(f"{BASE}/github/read")
    assert response.status_code == 502 and "60 requests an hour" in response.json()["detail"]
    app.state.fetcher = FakeWeb(
        {GITHUB_URL: ('{"message":"Not Found"}', "application/json")}
    ).fetcher()
    assert (await api.post(f"{BASE}/github/read")).json()["detail"] == "Not Found"


# --- scoring reads the account setup ----------------------------------------------------------


async def test_scoring_uses_the_profile_you_set_up_instead_of_a_file(
    app: FastAPI, api: AsyncClient, tmp_path: Any
) -> None:
    import shutil

    from careerpilot.core.config import REPO_ROOT

    shutil.copy(REPO_ROOT / "content" / "skills.yaml", tmp_path / "skills.yaml")  # no profile.yaml
    app.state.settings = app.state.settings.model_copy(update={"content_dir": tmp_path})
    created = await api.post(
        "/api/v1/jobs",
        json={"company_name": "Acme", "title": "Python Developer", "jd_text": "Python FastAPI SQL"},
    )
    job = created.json()["job"]["id"] if "job" in created.json() else created.json()["id"]
    refused = await api.post(f"/api/v1/jobs/{job}/score?ai=false")
    assert refused.status_code == 409 and "skills, regions, years" in refused.json()["detail"]

    await api.patch(
        BASE,
        json={
            "skills": ["python", "fastapi", "sql"],
            "regions": ["India"],
            "years_experience": 3,
            "target_levels": ["mid"],
        },
    )
    scored = await api.post(f"/api/v1/jobs/{job}/score?ai=false")
    assert scored.status_code == 200, scored.text
    skills = next(c for c in scored.json()["components"] if c["key"] == "skills")
    assert skills["score"] == 100  # all three skills are in the profile
    await api.patch(BASE, json={"skills": ["java"]})  # editing the profile makes the score stale
    assert (await api.get(f"/api/v1/jobs/{job}/score")).json()["stale"] is True


# --- OCR ---------------------------------------------------------------------------------------


def test_ocr_slips_are_repaired_but_ordinary_words_are_left_alone() -> None:
    assert cvfile.fix_ocr("REST APls with FastAPl and APl") == "REST APIs with FastAPI and API"
    assert (
        cvfile.fix_ocr("Built tools in Excel and HTML, then PLC")
        == "Built tools in Excel and HTML, then PLC"
    )
    assert cvfile.fix_ocr("a Local team") == "a Local team"


def test_a_name_glued_together_by_ocr_is_split() -> None:
    assert rules.guess_name("PriyaSharma\nPython developer") == "Priya Sharma"
    assert rules.guess_name("JavaScript\nx") is None  # a technology, not a name... one word only


def test_a_small_picture_is_enlarged_before_it_is_read() -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 100), "white").save(buffer, format="PNG")
    with Image.open(io.BytesIO(cvfile._enlarge(buffer.getvalue()))) as bigger:  # pyright: ignore[reportPrivateUsage]
        assert bigger.size == (800, 200)
    wide = io.BytesIO()
    Image.new("RGB", (cvfile.OCR_MAX_WIDTH, 10), "white").save(wide, format="PNG")
    with Image.open(io.BytesIO(cvfile._enlarge(wide.getvalue()))) as same:  # pyright: ignore[reportPrivateUsage]
        assert same.size == (cvfile.OCR_MAX_WIDTH, 10)  # never made larger than the limit


def test_the_real_ocr_engine_reads_a_scanned_cv_when_the_extra_is_installed() -> None:
    """Skipped unless `uv sync --extra ocr` was run. Draws text as a picture, wraps it in a PDF with
    no text layer, and checks the whole chain: scan -> OCR -> skills, title and years."""
    import pytest

    pytest.importorskip("rapidocr_onnxruntime")
    from PIL import ImageDraw, ImageFont

    from careerpilot.core.config import REPO_ROOT
    from careerpilot.modules.scoring.skills import load_vocabulary, skills_in

    try:
        font = ImageFont.truetype("arial.ttf", 30)
    except OSError:
        pytest.skip("no TrueType font to draw the test page with")
    page = Image.new("RGB", (1000, 340), "white")
    draw = ImageDraw.Draw(page)
    lines = [
        "Priya Sharma",
        "Senior Python Backend Developer",
        "6 years of professional experience",
        "Built REST APIs with FastAPI and PostgreSQL on AWS.",
        "Deployed with Docker and Terraform.",
    ]
    for i, line in enumerate(lines):
        draw.text((40, 30 + i * 60), line, fill="black", font=font)
    pdf = io.BytesIO()
    page.save(pdf, format="PDF")
    read = cvfile.read_cv(pdf.getvalue(), cvfile.default_ocr)
    assert read.source == "ocr"
    found = skills_in(read.text, load_vocabulary(REPO_ROOT / "content"))
    assert {"python", "fastapi", "postgresql", "aws", "docker", "terraform"} <= found
    assert rules.role_titles(read.text) == ["Python Backend Developer"]
    assert rules.years_experience(read.text) == 6
