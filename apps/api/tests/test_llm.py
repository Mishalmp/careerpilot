"""The Claude adapter, checked against a mock HTTP server: no key and no network needed."""

import json
from typing import Any

import httpx2
import pytest

from careerpilot.core.llm import AnthropicClient, LlmError


def message(content: list[dict[str, Any]], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }


def client_for(handler: Any) -> AnthropicClient:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return AnthropicClient("sk-test-key", "claude-sonnet-5-5", max_retries=0, http_client=http)


async def test_sends_the_expected_request_and_returns_only_the_text() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        content = [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": "A closure reads the variable late [1]."},
        ]
        return httpx2.Response(200, json=message(content))

    reply = await client_for(handler).complete(system="Be brief.", user="Question?", max_tokens=300)

    assert seen["path"] == "/v1/messages"
    assert (
        "sk-test-key" in seen["headers"]["authorization"] and "anthropic-version" in seen["headers"]
    )
    body = seen["body"]
    assert body["model"] == "claude-sonnet-5-5" and body["max_tokens"] == 300
    assert body["system"] == "Be brief."
    assert body["messages"] == [{"role": "user", "content": "Question?"}]
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body and "top_p" not in body  # removed on current models
    assert reply.text == "A closure reads the variable late [1]."
    assert (reply.input_tokens, reply.output_tokens, reply.refused) == (12, 7, False)


async def test_a_refusal_is_flagged() -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json=message([], stop_reason="refusal"))

    reply = await client_for(handler).complete(system="s", user="u", max_tokens=10)
    assert reply.refused is True and reply.text == ""


@pytest.mark.parametrize(
    ("status", "expected_status", "words"),
    [
        (401, 502, "key was rejected"),
        (429, 429, "rate limiting"),
        (500, 502, "(500)"),
        (400, 502, "(400)"),
    ],
)
async def test_http_errors_become_readable_llm_errors(
    status: int, expected_status: int, words: str
) -> None:
    def handler(_: httpx2.Request) -> httpx2.Response:
        body = {"type": "error", "error": {"type": "api_error", "message": "secret internals"}}
        return httpx2.Response(status, json=body)

    with pytest.raises(LlmError) as error:
        await client_for(handler).complete(system="s", user="u", max_tokens=10)
    assert error.value.status == expected_status and words in error.value.message
    assert (
        "secret internals" not in error.value.message
    )  # provider detail is not passed to the user


async def test_a_network_failure_is_reported() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("no route", request=request)

    with pytest.raises(LlmError) as error:
        await client_for(handler).complete(system="s", user="u", max_tokens=10)
    assert error.value.status == 502 and "Could not reach" in error.value.message


async def test_a_per_call_model_overrides_the_default_and_nothing_else_changes() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json=message([{"type": "text", "text": "ok"}]))

    client = client_for(handler)
    await client.complete(system="s", user="u", max_tokens=10)
    await client.complete(system="s", user="u", max_tokens=10, model="claude-haiku-5-5")
    assert [b["model"] for b in seen] == ["claude-sonnet-5-5", "claude-haiku-5-5"]
    # Same safe request shape on both models: no thinking, temperature or prefill fields (those return
    # errors on some models); depth is controlled only with effort.
    for body in seen:
        assert body["output_config"] == {"effort": "low"}
        assert not {"thinking", "temperature", "top_p", "top_k"} & set(body)
        assert body["messages"][-1]["role"] == "user"


async def test_an_empty_credit_balance_is_named_and_not_asked_again_for_a_while() -> None:
    calls = 0

    def handler(_: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        body = {
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "message": "Your credit balance is too low to access the Anthropic API.",
            },
        }
        return httpx2.Response(400, json=body)

    client = client_for(handler)
    for _ in range(3):
        with pytest.raises(LlmError) as error:
            await client.complete(system="s", user="u", max_tokens=10)
        assert error.value.status == 402 and "no credit left" in error.value.message
        assert "Everything that does not use the model" in error.value.message
    assert calls == 1  # the second and third did not reach the network
