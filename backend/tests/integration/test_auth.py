"""Integration tests for the phone-auth contract."""
from __future__ import annotations

import pytest

from tests.fakes import (
    DEFAULT_PASSWORD,
    auth_headers_for,
    login_user,
    register_payload,
    register_user,
)

pytestmark = pytest.mark.integration


async def test_register_returns_profile_with_phone_and_address(client):
    resp = await register_user(client, "01712345678")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["phone"] == "01712345678"
    assert body["username"] == "Test Farmer"
    assert body["address"]["division_name"] == "Rajshahi"
    assert body["address"]["upazila_code"] == "508194"
    assert "id" in body


async def test_register_duplicate_phone_400(client):
    assert (await register_user(client, "01712345678")).status_code == 201
    # Same number, even via +880 form, is a duplicate after normalization.
    dup = await register_user(client, "+8801712345678")
    assert dup.status_code == 400


async def test_register_password_mismatch_400(client):
    payload = register_payload("01712345678")
    payload["password2"] = "different-password"
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 400


async def test_register_weak_password_400(client):
    payload = register_payload("01712345678", password="short")  # < 8 chars
    resp = await client.post("/api/auth/register", json=payload)
    # Pydantic min_length=8 -> 422, or the endpoint's own check -> 400.
    assert resp.status_code in (400, 422)


async def test_register_invalid_phone_400(client):
    payload = register_payload("01712345678")
    payload["phone"] = "0171234"  # invalid
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code in (400, 422)


async def test_login_by_phone_200(client):
    await register_user(client, "01712345678")
    resp = await login_user(client, "01712345678")
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"] and data["refresh_token"]


async def test_login_normalizes_plus880(client):
    await register_user(client, "01712345678")
    # Log in using the +880 form; normalization maps it to the same user.
    resp = await login_user(client, "+8801712345678")
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_bad_credentials_401(client):
    await register_user(client, "01712345678")
    resp = await client.post(
        "/api/auth/login",
        json={"phone": "01712345678", "password": "wrong-password"},
    )
    assert resp.status_code == 401


async def test_refresh_rotation_returns_new_pair(client):
    await register_user(client, "01712345678")
    login = (await login_user(client, "01712345678")).json()
    old_refresh = login["refresh_token"]

    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert resp.status_code == 200
    new_pair = resp.json()
    assert new_pair["refresh_token"] != old_refresh
    assert new_pair["access_token"] != login["access_token"]


async def test_reusing_old_refresh_after_rotation_401(client):
    await register_user(client, "01712345678")
    login = (await login_user(client, "01712345678")).json()
    old_refresh = login["refresh_token"]

    first = await client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert first.status_code == 200

    # Reuse the now-blacklisted old refresh token -> rejected.
    reuse = await client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert reuse.status_code == 401


async def test_logout_invalidates_both_tokens(client):
    await register_user(client, "01712345678")
    login = (await login_user(client, "01712345678")).json()
    access = login["access_token"]
    refresh = login["refresh_token"]
    headers = {"Authorization": f"Bearer {access}"}

    # /me works before logout.
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 200

    logout = await client.post(
        "/api/auth/logout", json={"refresh_token": refresh}, headers=headers
    )
    assert logout.status_code == 204

    # Old access token now rejected.
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401
    # Old refresh token now rejected.
    reuse = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh}
    )
    assert reuse.status_code == 401


async def test_me_requires_auth(client):
    await register_user(client, "01712345678")
    headers = await auth_headers_for(client, "01912345678")
    ok = await client.get("/api/auth/me", headers=headers)
    assert ok.status_code == 200
    assert ok.json()["phone"] == "01912345678"

    # No token -> 401.
    assert (await client.get("/api/auth/me")).status_code == 401
