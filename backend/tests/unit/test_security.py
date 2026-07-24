"""Unit tests for password hashing and JWT helpers."""
from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from app.config import settings
from app.security import (
    TokenError,
    _create_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

pytestmark = pytest.mark.unit


def test_hash_and_verify_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"  # not plaintext
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_wrong_password_is_false():
    hashed = hash_password("s3cret-password")
    assert verify_password("not-the-password", hashed) is False


def test_verify_handles_garbage_hash_gracefully():
    assert verify_password("whatever", "not-a-real-bcrypt-hash") is False


def test_long_password_over_72_bytes_supported():
    # bcrypt truncates at 72 bytes; our sha256 pre-hash sidesteps that.
    pw = "a" * 200
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    assert verify_password("a" * 199, hashed) is False


def test_access_and_refresh_have_correct_type_claim():
    access, _, _ = create_access_token(42)
    refresh, _, _ = create_refresh_token(42)

    access_claims = decode_token(access)
    refresh_claims = decode_token(refresh)

    assert access_claims["type"] == "access"
    assert refresh_claims["type"] == "refresh"
    assert access_claims["sub"] == "42"
    assert refresh_claims["sub"] == "42"
    # jti present and unique across tokens.
    assert access_claims["jti"] != refresh_claims["jti"]


def test_decode_valid_token_returns_claims():
    token, jti, _ = create_access_token(7)
    claims = decode_token(token)
    assert claims["jti"] == jti
    assert claims["sub"] == "7"


def test_decode_tampered_token_raises():
    token, _, _ = create_access_token(1)
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    with pytest.raises(TokenError):
        decode_token(tampered)


def test_decode_wrong_secret_raises():
    token = jwt.encode(
        {"sub": "1", "type": "access"}, "some-other-secret", algorithm="HS256"
    )
    with pytest.raises(TokenError):
        decode_token(token)


def test_decode_expired_token_raises():
    # Negative lifetime => already expired.
    token, _, _ = _create_token(9, "access", timedelta(seconds=-10))
    with pytest.raises(TokenError):
        decode_token(token)
