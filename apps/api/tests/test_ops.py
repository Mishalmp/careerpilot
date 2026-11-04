from httpx import AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_checks_database_and_migrations(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_responses_carry_request_id_and_safe_headers(client: AsyncClient) -> None:
    first = await client.get("/healthz")
    second = await client.get("/healthz")
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
    assert first.headers["x-content-type-options"] == "nosniff"
    assert first.headers["cache-control"] == "no-store"


async def test_unknown_host_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"Host": "evil.example"})
    assert response.status_code == 400


async def test_errors_are_problem_json(client: AsyncClient) -> None:
    response = await client.get("/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Not Found"
