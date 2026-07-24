"""Password hashing (bcrypt, direct) and JWT helpers (PyJWT)."""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt

from .config import settings


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def _prepare(password: str) -> bytes:
    """Pre-hash to sidestep bcrypt's 72-byte input limit while keeping entropy.

    sha256 -> base64 yields a fixed 44-byte token, always < 72 bytes.
    """
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
class TokenError(Exception):
    """Raised when a token is invalid, malformed, or expired."""


def _create_token(user_id: int, token_type: str, expires_delta: timedelta):
    now = datetime.now(timezone.utc)
    exp = now + expires_delta
    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "type": token_type,
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token, jti, exp


def create_access_token(user_id: int):
    return _create_token(
        user_id,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int):
    return _create_token(
        user_id,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """Decode + verify signature/expiry. Raises TokenError on any failure."""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:  # covers expired, malformed, bad signature
        raise TokenError(str(exc)) from exc
