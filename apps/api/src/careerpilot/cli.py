import argparse
import asyncio
import sys
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError

from careerpilot.core.config import get_settings
from careerpilot.core.db import create_engine, create_sessionmaker
from careerpilot.modules.auth import service


async def _create_user(email: str, password: str) -> None:
    engine = create_engine(get_settings().database_url)
    try:
        async with create_sessionmaker(engine)() as db:
            await service.create_user(db, email, password)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="careerpilot")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create the single local user")
    create.add_argument("--email", required=True)
    args = parser.parse_args(argv)

    try:
        email = TypeAdapter(EmailStr).validate_python(args.email)
    except ValidationError:
        print("That is not a valid email address.", file=sys.stderr)
        return 2
    password = getpass("Password: ")
    if password != getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 2
    try:
        asyncio.run(_create_user(email, password))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    except service.UserExistsError:
        print("A user with that email already exists.", file=sys.stderr)
        return 1
    print(f"Created user {email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
