import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

_hasher = PasswordHasher()
# Used to keep login timing similar whether or not the email exists.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-Aa!")

PASSWORD_MIN_LENGTH = 9  # problem statement: "more than 8 characters"
_SPECIAL_CHAR = re.compile(r"[^A-Za-z0-9]")


def password_policy_errors(password: str) -> list[str]:
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append("must be longer than 8 characters")
    if len(password) > 128:
        errors.append("must be at most 128 characters")
    if not re.search(r"[a-z]", password):
        errors.append("must contain a lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("must contain an uppercase letter")
    if not _SPECIAL_CHAR.search(password):
        errors.append("must contain a special character")
    return errors


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str, token_version: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "ver": token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "ver"]},
        )
    except jwt.PyJWTError:
        return None


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_reset_token() -> tuple[str, str]:
    """Returns (raw token for the user, hash to store)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
