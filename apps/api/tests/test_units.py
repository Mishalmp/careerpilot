import pytest

from careerpilot.core.logging import redact_sensitive
from careerpilot.core.security import DUMMY_HASH, hash_password, hash_token, verify_password
from careerpilot.modules.auth.service import create_user


async def test_password_roundtrip_and_failures() -> None:
    hashed = await hash_password("a long enough password")
    assert hashed != "a long enough password"
    assert await verify_password(hashed, "a long enough password")
    assert not await verify_password(hashed, "something else")
    assert not await verify_password("not-a-hash", "anything")
    assert not await verify_password(DUMMY_HASH, "anything")


def test_token_hash_is_stable_and_not_the_token() -> None:
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != "abc"


def test_log_redaction_hides_sensitive_keys_only() -> None:
    event = {"event": "x", "Password": "p", "cookie": "c", "path": "/ok"}
    result = redact_sensitive(None, "info", event)
    assert result["Password"] == result["cookie"] == "[redacted]"
    assert result["path"] == "/ok"


async def test_short_passwords_are_refused() -> None:
    with pytest.raises(ValueError, match="at least"):
        await create_user(None, "a@example.com", "short")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    "argv",
    [
        ["create-user", "--email", "me@example.com"],
        ["seed-prep"],
        ["import-tracker", "tracker.xlsx"],
        ["ingest"],
        ["worker"],
        ["llm-check"],
        ["backup-key"],
        ["backup"],
        ["restore", "file.cpbk", "--into", "copy"],
        ["search", "closures"],
        ["eval-rag"],
    ],
)
def test_every_cli_command_is_wired_to_a_function(argv: list[str]) -> None:
    """A command registered without a handler only fails when someone runs it (one once did)."""
    from careerpilot.cli import build_parser

    assert callable(build_parser().parse_args(argv).run)
