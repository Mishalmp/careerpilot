import hashlib
import secrets

from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# Verified against when the email is unknown, so response time does not reveal which emails exist.
DUMMY_HASH = _hasher.hash("not-a-real-password")


async def hash_password(password: str) -> str:
    return await to_thread.run_sync(_hasher.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    try:
        return await to_thread.run_sync(_hasher.verify, password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Only the hash of a session token is stored, so a database leak does not leak sessions."""
    return hashlib.sha256(token.encode()).hexdigest()
