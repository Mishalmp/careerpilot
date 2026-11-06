"""Backups: encryption, retention, and a real dump restored into a fresh database."""

import asyncio
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from careerpilot.core import backup
from careerpilot.core.backup import (
    BackupError,
    Tools,
    create_backup,
    decrypt,
    drop_database,
    encrypt,
    generate_key,
    parse_url,
    prune,
    restore_backup,
)


def _find_tools() -> Tools | None:
    """Tools that match the test database: its Docker container, else same-version host tools."""
    container = os.environ.get("CAREERPILOT_PG_CONTAINER", "careerpilot-postgres-1")
    docker = shutil.which("docker")
    if docker:
        running = subprocess.run(  # noqa: S603
            [docker, "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=False
        ).stdout.split()
        if container in running:
            return Tools(container=container)
    if shutil.which("pg_dump") and shutil.which("pg_restore"):
        return Tools()  # check_tools() refuses if these are newer than the server
    return None


TOOLS = _find_tools()
NEEDS_POSTGRES_TOOLS = pytest.mark.skipif(
    TOOLS is None, reason="no PostgreSQL client tools and no Postgres container were found"
)
RESTORED = "careerpilot_restore_test"


# --- encryption ----------------------------------------------------------------------------


def test_a_backup_round_trips_and_is_not_readable_without_the_key() -> None:
    key = generate_key()
    secret = b"PGDMP custom format bytes " * 1000
    blob = encrypt(secret, key)
    assert secret[:20] not in blob and blob.startswith(backup.MAGIC)
    assert decrypt(blob, key) == secret


def test_two_encryptions_of_the_same_data_differ() -> None:
    key = generate_key()
    assert encrypt(b"same", key) != encrypt(b"same", key)  # a fresh nonce each time


def test_the_wrong_key_or_a_changed_file_is_rejected() -> None:
    key = generate_key()
    blob = encrypt(b"data" * 50, key)
    with pytest.raises(BackupError, match="Wrong key"):
        decrypt(blob, generate_key())
    flipped = bytearray(blob)
    flipped[-5] ^= 1
    with pytest.raises(BackupError, match="Wrong key, or the file was changed"):
        decrypt(bytes(flipped), key)
    with pytest.raises(BackupError, match="not a CareerPilot backup"):
        decrypt(b"hello", key)
    with pytest.raises(BackupError, match="not a CareerPilot backup"):
        decrypt(b"X" * 100, key)


@pytest.mark.parametrize("bad", ["", "not base64!!", "c2hvcnQ="])
def test_a_bad_key_is_refused_with_advice(bad: str) -> None:
    with pytest.raises(BackupError, match=r"key"):
        encrypt(b"x", bad)


def test_generated_keys_are_unique() -> None:
    assert generate_key() != generate_key()


# --- connection details --------------------------------------------------------------------


def test_the_password_goes_in_the_environment_not_the_command_line() -> None:
    connection = parse_url(
        "postgresql+asyncpg://careerpilot:p%40ss%3Aword@db.example:5433/careerpilot"
    )
    assert (connection.user, connection.password, connection.host, connection.port) == (
        "careerpilot",
        "p@ss:word",
        "db.example",
        5433,
    )
    assert (
        "p@ss:word" not in " ".join(connection.args())
        and connection.env()["PGPASSWORD"] == "p@ss:word"
    )


def test_an_incomplete_url_is_refused() -> None:
    with pytest.raises(BackupError):
        parse_url("postgresql+asyncpg://localhost/")


# --- retention -----------------------------------------------------------------------------


def test_only_the_newest_backups_are_kept(tmp_path: Path) -> None:
    start = datetime(2026, 11, 1, 2, 0, tzinfo=UTC)
    for day in range(20):
        stamp = (start + timedelta(days=day)).strftime("%Y%m%d-%H%M%S")
        (tmp_path / f"careerpilot-{stamp}.cpbk").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("not a backup")
    removed = prune(tmp_path, keep=14)
    left = sorted(p.name for p in tmp_path.glob("*.cpbk"))
    assert len(removed) == 6 and len(left) == 14
    assert (
        left[0] == "careerpilot-20261107-020000.cpbk"
        and left[-1] == "careerpilot-20261120-020000.cpbk"
    )
    assert (tmp_path / "notes.txt").exists()  # only backups are ever deleted


# --- refusals that need no database --------------------------------------------------------


def test_restore_never_targets_the_live_database_or_a_bad_name(
    tmp_path: Path, settings: Any
) -> None:
    key = generate_key()
    file = tmp_path / "careerpilot-x.cpbk"
    file.write_bytes(encrypt(b"dump", key))
    live = parse_url(settings.database_url).database
    with pytest.raises(BackupError, match="never writes into the database the app is using"):
        restore_backup(settings.database_url, file, key, live)
    for bad in ("Drop Table", "x; drop database y", "../x", "", "1abc", "A" * 5):
        with pytest.raises(BackupError, match="lower-case"):
            restore_backup(settings.database_url, file, key, bad)
    with pytest.raises(BackupError, match="Refusing to drop"):
        drop_database(settings.database_url, live)


# --- a real backup and restore -------------------------------------------------------------


async def counts(url: str) -> dict[str, int]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            tables = (
                (
                    await conn.execute(
                        text(
                            "select tablename from pg_tables where schemaname = 'public' order by 1"
                        )
                    )
                )
                .scalars()
                .all()
            )
            result: dict[str, int] = {}
            for table in tables:  # names come from pg_tables, not from input
                query = text(f'select count(*) from "{table}"')  # noqa: S608
                result[table] = int((await conn.execute(query)).scalar_one())
            return result
    finally:
        await engine.dispose()


@NEEDS_POSTGRES_TOOLS
async def test_a_backup_restores_into_a_fresh_database_with_the_same_data(
    app: FastAPI, api: AsyncClient, settings: Any, tmp_path: Path
) -> None:
    # Some real data: a job with a contact and a note-like record.
    job = (
        await api.post(
            "/api/v1/jobs",
            json={
                "company_name": "Backup Test Co",
                "title": "Backend Engineer",
                "jd_text": "Python.",
            },
        )
    ).json()
    await api.post(
        f"/api/v1/jobs/{job['id']}/contacts",
        json={"name": "Careers", "email": "careers@example.com", "kind": "referral"},
    )
    key = generate_key()

    file = await asyncio.to_thread(
        create_backup, settings.database_url, tmp_path, key, tools=TOOLS or Tools()
    )
    assert file.suffix == ".cpbk" and await asyncio.to_thread(lambda: file.stat().st_size) > 1000
    assert not await asyncio.to_thread(lambda: list(tmp_path.glob("*.tmp")))  # nothing half-written
    assert b"Backup Test Co" not in await asyncio.to_thread(file.read_bytes)  # it is encrypted

    await asyncio.to_thread(drop_database, settings.database_url, RESTORED)
    try:
        restored = await asyncio.to_thread(
            restore_backup, settings.database_url, file, key, RESTORED, tools=TOOLS or Tools()
        )
        assert restored == RESTORED
        live = parse_url(settings.database_url)
        restored_url = settings.database_url.replace(f"/{live.database}", f"/{RESTORED}")

        before, after = await counts(settings.database_url), await counts(restored_url)
        assert after == before and after["jobs"] == 1 and after["contacts"] == 1 and len(after) > 20

        engine = create_async_engine(restored_url)
        try:
            async with engine.connect() as conn:
                title = (await conn.execute(text("select title from jobs"))).scalar_one()
                extension = (
                    await conn.execute(
                        text("select count(*) from pg_extension where extname = 'vector'")
                    )
                ).scalar_one()
                version = (
                    await conn.execute(text("select version_num from alembic_version"))
                ).scalar_one()
        finally:
            await engine.dispose()
        assert (
            title == "Backend Engineer" and extension == 1 and version
        )  # schema and vectors came along

        # A second restore into the same name is refused; the first copy is untouched.
        with pytest.raises(BackupError, match="already exists"):
            await asyncio.to_thread(
                restore_backup, settings.database_url, file, key, RESTORED, tools=TOOLS or Tools()
            )
        assert await counts(restored_url) == before
    finally:
        await asyncio.to_thread(drop_database, settings.database_url, RESTORED)


@NEEDS_POSTGRES_TOOLS
def test_restoring_with_the_wrong_key_creates_nothing(
    app: FastAPI, settings: Any, tmp_path: Path
) -> None:
    file = create_backup(settings.database_url, tmp_path, generate_key(), tools=TOOLS or Tools())
    with pytest.raises(BackupError, match="Wrong key"):
        restore_backup(
            settings.database_url, file, generate_key(), RESTORED, tools=TOOLS or Tools()
        )
    drop_database(
        settings.database_url, RESTORED
    )  # would be a no-op; the point is it did not exist


def test_a_missing_dump_tool_is_explained(settings: Any, tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="was not found"):
        create_backup(
            settings.database_url, tmp_path, generate_key(), tools=Tools(dump="no-such-pg-dump")
        )


@pytest.mark.parametrize(
    ("output", "major"),
    [
        ("pg_dump (PostgreSQL) 16.15 (Debian 16.15-1.pgdg13+2)", 16),
        ("pg_dump (PostgreSQL) 17.1", 17),
        ("pg_dump (PostgreSQL) 17beta1", 17),
        ("pg_dump (PostgreSQL) 15.4 (Ubuntu 15.4-0ubuntu0.23.04.1)", 15),
        ("pg_dump (PostgreSQL) 14.9 (Homebrew)", 14),
    ],
)
def test_the_client_version_is_read_whatever_the_packager_adds(output: str, major: int) -> None:
    assert backup.parse_client_major(output) == major


def test_an_unreadable_version_is_an_error() -> None:
    with pytest.raises(BackupError, match="Could not read the version"):
        backup.parse_client_major("something else entirely")
