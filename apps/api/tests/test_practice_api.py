from typing import Any

import pytest
from httpx import AsyncClient

PRACTICE = "/api/v1/practice"


async def problem(api: AsyncClient, slug: str) -> dict[str, Any]:
    response = await api.get(f"{PRACTICE}/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()


def submission(
    detail: dict[str, Any], language: str, passed: int | None = None, code: str = "x"
) -> dict[str, Any]:
    count = len(detail["sql_tests"] if detail["kind"] == "sql" else detail["function_tests"])
    passed = count if passed is None else passed
    names = [t["name"] for t in (detail["sql_tests"] or detail["function_tests"])]
    return {
        "language": language,
        "code": code,
        "passed": passed,
        "total": count,
        "runtime_ms": 12,
        "results": [
            {"name": n, "status": "pass" if i < passed else "fail"} for i, n in enumerate(names)
        ],
    }


async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(f"{PRACTICE}/problems")).status_code == 401
    assert (await client.get(f"{PRACTICE}/problems/two-sum")).status_code == 401
    assert (
        await client.post(f"{PRACTICE}/problems/two-sum/submissions", json={})
    ).status_code == 401


async def test_list_and_filters(api: AsyncClient) -> None:
    everything = (await api.get(f"{PRACTICE}/problems")).json()
    assert len(everything) >= 25
    assert {p["status"] for p in everything} == {"unsolved"}
    # easy first, then by title
    order = {"Easy": 0, "Medium": 1, "Hard": 2}
    assert [order[p["difficulty"]] for p in everything] == sorted(
        order[p["difficulty"]] for p in everything
    )

    async def slugs(**params: Any) -> set[str]:
        response = await api.get(f"{PRACTICE}/problems", params=params)
        assert response.status_code == 200
        return {p["slug"] for p in response.json()}

    assert "longest-login-streak" in await slugs(kind="sql")
    assert "two-sum" not in await slugs(kind="sql")
    assert await slugs(difficulty="Hard") >= {"merge-k-sorted-lists", "longest-login-streak"}
    assert "two-sum" in await slugs(tag="hashing")
    assert await slugs(q="islands") == {"number-of-islands"}
    assert "rate-limit-decisions" in await slugs(topic="system-design-design-rate-limiter")
    assert await slugs(progress="solved") == set()


async def test_function_problem_detail_has_starters_and_tests(api: AsyncClient) -> None:
    detail = await problem(api, "two-sum")
    specs = {s["language"]: s for s in detail["specs"]}
    assert set(specs) == {"python", "javascript", "typescript"}
    assert specs["python"]["entry"] == "two_sum" and specs["javascript"]["entry"] == "twoSum"
    assert "def two_sum(nums: list[int], target: int)" in specs["python"]["starter"]
    assert "twoSum(nums: number[], target: number): number[]" in specs["typescript"]["starter"]
    assert detail["sql_ddl"] is None and detail["sql_tests"] == []
    tests = detail["function_tests"]
    assert any(t["hidden"] for t in tests) and any(not t["hidden"] for t in tests)
    assert tests[0]["args"] == [[2, 7, 11, 15], 9] and tests[0]["expected"] == [0, 1]


async def test_sql_problem_detail(api: AsyncClient) -> None:
    detail = await problem(api, "second-highest-salary")
    assert [s["language"] for s in detail["specs"]] == ["sql"]
    assert detail["specs"][0]["entry"] is None
    assert "CREATE TABLE employees" in detail["sql_ddl"]
    assert detail["function_tests"] == []
    assert detail["sql_tests"][1]["expected"] == {
        "columns": ["second_highest"],
        "rows": [[None]],
        "ordered": False,
    }


@pytest.mark.parametrize("slug", ["nope", "..", "two-sum.yaml", "Two-Sum"])
async def test_unknown_problem_is_404(api: AsyncClient, slug: str) -> None:
    assert (await api.get(f"{PRACTICE}/problems/{slug}")).status_code in (404,)


async def test_submission_updates_progress(api: AsyncClient) -> None:
    detail = await problem(api, "two-sum")
    url = f"{PRACTICE}/problems/two-sum/submissions"

    partial = await api.post(url, json=submission(detail, "python", passed=2))
    assert partial.status_code == 201
    assert (await problem(api, "two-sum"))["status"] == "attempted"

    solved = await api.post(url, json=submission(detail, "javascript", code="function twoSum(){}"))
    assert solved.status_code == 201
    assert (await problem(api, "two-sum"))["status"] == "solved"
    listed = {p["slug"]: p["status"] for p in (await api.get(f"{PRACTICE}/problems")).json()}
    assert listed["two-sum"] == "solved" and listed["valid-parentheses"] == "unsolved"
    assert (await api.get(f"{PRACTICE}/problems", params={"progress": "solved"})).json()[0][
        "slug"
    ] == "two-sum"


async def test_history_is_newest_first_and_filters_by_language(api: AsyncClient) -> None:
    detail = await problem(api, "two-sum")
    url = f"{PRACTICE}/problems/two-sum/submissions"
    for code in ("one", "two", "three"):
        await api.post(url, json=submission(detail, "python", passed=1, code=code))
    await api.post(url, json=submission(detail, "typescript", passed=1, code="ts"))

    python_only = (await api.get(url, params={"language": "python"})).json()
    assert [s["code"] for s in python_only] == ["three", "two", "one"]
    assert (await api.get(url)).json()[0]["code"] == "ts"
    assert python_only[0]["results"][0] == {
        "name": detail["function_tests"][0]["name"],
        "status": "pass",
    }


async def test_old_submissions_are_pruned(api: AsyncClient) -> None:
    detail = await problem(api, "two-sum")
    url = f"{PRACTICE}/problems/two-sum/submissions"
    for n in range(35):
        assert (
            await api.post(url, json=submission(detail, "python", passed=0, code=f"v{n}"))
        ).status_code == 201
    history = (await api.get(url)).json()
    assert len(history) == 20  # the endpoint returns the 20 newest
    assert history[0]["code"] == "v34"


def broken(case: str, good: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, dict[str, Any]] = {
        "language not available here": {"language": "sql"},
        "total too high": {"total": good["total"] + 1},
        "passed does not match results": {"passed": good["passed"] - 1},
        "missing a result": {"results": good["results"][:-1]},
        "code too long": {"code": "x" * 50_001},
        "unknown language": {"language": "cobol"},
        "negative runtime": {"runtime_ms": -1},
    }
    return {**good, **changes[case]}


BAD_CASES = [
    "language not available here",
    "total too high",
    "passed does not match results",
    "missing a result",
    "code too long",
    "unknown language",
    "negative runtime",
]


@pytest.mark.parametrize("case", BAD_CASES)
async def test_bad_submissions_are_rejected(api: AsyncClient, case: str) -> None:
    detail = await problem(api, "two-sum")
    body = broken(case, submission(detail, "python"))
    response = await api.post(f"{PRACTICE}/problems/two-sum/submissions", json=body)
    assert response.status_code == 422
    assert (await api.get(f"{PRACTICE}/problems/two-sum/submissions")).json() == []


async def test_python_cannot_be_submitted_to_a_sql_problem(api: AsyncClient) -> None:
    detail = await problem(api, "second-highest-salary")
    response = await api.post(
        f"{PRACTICE}/problems/second-highest-salary/submissions", json=submission(detail, "python")
    )
    assert response.status_code == 422


async def test_another_owner_has_their_own_progress(
    api: AsyncClient, other_api: AsyncClient
) -> None:
    detail = await problem(api, "two-sum")
    await api.post(f"{PRACTICE}/problems/two-sum/submissions", json=submission(detail, "python"))
    assert (await problem(other_api, "two-sum"))["status"] == "unsolved"
    assert (await other_api.get(f"{PRACTICE}/problems/two-sum/submissions")).json() == []


async def test_submitting_needs_the_csrf_header(api: AsyncClient) -> None:
    detail = await problem(api, "two-sum")
    api.headers.pop("X-CSRF-Token")
    response = await api.post(
        f"{PRACTICE}/problems/two-sum/submissions", json=submission(detail, "python")
    )
    assert response.status_code == 403
