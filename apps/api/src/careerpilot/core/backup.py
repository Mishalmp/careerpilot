"""Encrypted database backups and a restore that can never overwrite live data.

A backup is `pg_dump` (custom format) encrypted with AES-256-GCM using a key you hold. The key is
in the environment (`CAREERPILOT_BACKUP_KEY`), never next to the backups, so a stolen backup folder
is unreadable. Restore always goes into a NEW database; to go live you point `database_url` at it
(or rename it). Nothing here drops or changes the database the app is using.

The whole dump is held in memory while it is encrypted: fine for a personal database (megabytes).
"""

import asyncio
import base64
import os
import re
import secrets
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import URL, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from careerpilot.core.config import Settings

MAGIC = b"CPBK1"  # file format marker and version
NONCE_BYTES = 12
SUFFIX = ".cpbk"
KEEP_DEFAULT = 14
_DB_NAME = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


class BackupError(Exception):
    """A backup or restore failed. The message is safe to show."""


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    user: str
    password: str
    database: str

    def env(self) -> dict[str, str]:
        """The password goes in the environment, not on the command line (where `ps` shows it)."""
        return {**os.environ, "PGPASSWORD": self.password}

    def args(self, database: str | None = None, *, inside_container: bool = False) -> list[str]:
        host, port = ("localhost", 5432) if inside_container else (self.host, self.port)
        return [
            "--host", host, "--port", str(port), "--username", self.user,
            "--dbname", database or self.database,
        ]  # fmt: skip


def parse_url(database_url: str) -> Connection:
    parts = urlsplit(database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    if not parts.hostname or not parts.username or not parts.path.strip("/"):
        raise BackupError("database_url needs a host, user and database name.")
    return Connection(
        host=parts.hostname,
        port=parts.port or 5432,
        user=unquote(parts.username),
        password=unquote(parts.password or ""),
        database=parts.path.strip("/"),
    )


# --- encryption ----------------------------------------------------------------------------


def generate_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def _aes(key: str) -> AESGCM:
    try:
        raw = base64.urlsafe_b64decode(key.encode())
    except ValueError as exc:
        raise BackupError("The backup key is not valid base64.") from exc
    if len(raw) != 32:
        raise BackupError(
            "The backup key must be 32 bytes. Make one with `careerpilot backup-key`."
        )
    return AESGCM(raw)


def encrypt(data: bytes, key: str) -> bytes:
    nonce = secrets.token_bytes(NONCE_BYTES)
    return MAGIC + nonce + _aes(key).encrypt(nonce, data, MAGIC)


def decrypt(blob: bytes, key: str) -> bytes:
    if not blob.startswith(MAGIC) or len(blob) < len(MAGIC) + NONCE_BYTES + 16:
        raise BackupError("This is not a CareerPilot backup file.")
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_BYTES]
    try:
        return _aes(key).decrypt(nonce, blob[len(MAGIC) + NONCE_BYTES :], MAGIC)
    except InvalidTag as exc:
        raise BackupError("Wrong key, or the file was changed or damaged.") from exc


# --- backups -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Tools:
    """How to run pg_dump and pg_restore.

    Either the tools on this computer, or (`container` set) the ones inside the Docker container
    that runs Postgres, which are always the right version for that server.
    """

    dump: str = "pg_dump"
    restore: str = "pg_restore"
    container: str | None = None

    def command(
        self, tool: str, connection: Connection, database: str | None, *options: str
    ) -> list[str]:
        if self.container:
            # `-e PGPASSWORD` with no value copies it from our environment, so it is not in argv.
            return [
                "docker", "exec", "-i", "-e", "PGPASSWORD", self.container,
                Path(tool).name, *connection.args(database, inside_container=True), *options,
            ]  # fmt: skip
        return [tool, *connection.args(database), *options]


def backup_tools(settings: Settings) -> Tools:
    return Tools(settings.pg_dump_path, settings.pg_restore_path, settings.pg_container or None)


def _client_major(command: str, connection: Connection) -> int:
    out = _run([command, "--version"], connection).decode(errors="replace")
    match = re.search(r"(\d+)(?:\.\d+)*", out.split(")")[-1])
    if match is None:
        raise BackupError(f"Could not read the version of {command}.")
    return int(match.group(1))


async def _server_major(connection: Connection) -> int:
    engine = _admin_engine(connection)
    try:
        async with engine.connect() as conn:
            return int(
                await conn.scalar(text("select current_setting('server_version_num')::int / 10000"))
                or 0
            )
    finally:
        await engine.dispose()


def check_tools(connection: Connection, tools: Tools) -> None:
    """A dump from tools newer than the server may not load back into it, so refuse early."""
    if tools.container:
        return
    client, server = _client_major(tools.dump, connection), asyncio.run(_server_major(connection))
    if client > server:
        raise BackupError(
            f"pg_dump is version {client} but the database is version {server}; its backups might "
            "not restore. Set CAREERPILOT_PG_CONTAINER to the Docker container that runs Postgres "
            f"(for example careerpilot-postgres-1), or install PostgreSQL {server} client tools."
        )


def _run(command: list[str], connection: Connection, *, stdin: bytes | None = None) -> bytes:
    try:
        done = subprocess.run(  # noqa: S603 - fixed argument lists, no shell
            command,
            input=stdin,
            capture_output=True,
            env=connection.env(),
            check=False,
            timeout=600,
        )
    except FileNotFoundError as exc:
        raise BackupError(
            f"{command[0]} was not found. Install the PostgreSQL client tools."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BackupError(f"{command[0]} took longer than 10 minutes.") from exc
    if done.returncode != 0:
        detail = done.stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no details"]
        raise BackupError(f"{Path(command[0]).name} failed: {detail[0][:300]}")
    return done.stdout


def create_backup(
    database_url: str,
    directory: Path,
    key: str,
    *,
    tools: Tools = Tools(),  # noqa: B008 - an immutable value
    now: datetime | None = None,
) -> Path:
    """Dump the database, encrypt it, and write it to `directory`. Returns the file."""
    connection = parse_url(database_url)
    _aes(key)  # fail on a bad key before doing any work
    check_tools(connection, tools)
    dump = _run(
        tools.command(tools.dump, connection, None, "--format=custom", "--no-owner"), connection
    )
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"careerpilot-{stamp}{SUFFIX}"
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(encrypt(dump, key))
    temporary.replace(target)  # never leave a half-written backup under the final name
    return target


def prune(directory: Path, keep: int = KEEP_DEFAULT) -> list[Path]:
    """Delete all but the newest `keep` backups. Returns what was deleted."""
    files = sorted(directory.glob(f"careerpilot-*{SUFFIX}"), reverse=True)
    removed = files[keep:]
    for path in removed:
        path.unlink()
    return removed


# --- restore -------------------------------------------------------------------------------


def _admin_engine(connection: Connection) -> AsyncEngine:
    """A connection to the server's maintenance database, outside any transaction."""
    url = URL.create(
        "postgresql+asyncpg",
        username=connection.user,
        password=connection.password,
        host=connection.host,
        port=connection.port,
        database="postgres",
    )
    return create_async_engine(url, isolation_level="AUTOCOMMIT")


async def _create_database(connection: Connection, name: str) -> None:
    engine = _admin_engine(connection)
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("select 1 from pg_database where datname = :name"), {"name": name}
            )
            if exists:
                raise BackupError(
                    f"A database named {name} already exists. Restore only creates new ones."
                )
            await conn.execute(text(f'create database "{name}"'))  # name is validated by _DB_NAME
    finally:
        await engine.dispose()


def restore_backup(
    database_url: str,
    file: Path,
    key: str,
    new_database: str,
    *,
    tools: Tools = Tools(),  # noqa: B008 - an immutable value
) -> str:
    """Create `new_database` and load the backup into it. Returns the new database's name."""
    if not _DB_NAME.match(new_database):
        raise BackupError(
            "The new database name must be lower-case letters, digits and underscores."
        )
    connection = parse_url(database_url)
    if new_database == connection.database:
        raise BackupError("Restore never writes into the database the app is using.")
    dump = decrypt(file.read_bytes(), key)  # a wrong key stops here, before anything is created
    check_tools(connection, tools)
    asyncio.run(_create_database(connection, new_database))
    try:
        _run(
            tools.command(tools.restore, connection, new_database, "--no-owner", "--exit-on-error"),
            connection,
            stdin=dump,
        )
    except BackupError:
        drop_database(database_url, new_database)  # do not leave a half-restored copy behind
        raise
    return new_database


def drop_database(database_url: str, name: str) -> None:
    """For tests and clean-up of a restored copy. Refuses to touch the app's own database."""
    connection = parse_url(database_url)
    if name == connection.database or not _DB_NAME.match(name):
        raise BackupError("Refusing to drop that database.")

    async def run() -> None:
        engine = _admin_engine(connection)
        try:
            async with engine.connect() as conn:
                await conn.execute(text(f'drop database if exists "{name}" with (force)'))
        finally:
            await engine.dispose()

    asyncio.run(run())
