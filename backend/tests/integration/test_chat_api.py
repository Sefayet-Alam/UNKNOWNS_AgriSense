"""Integration tests for chat session/message management + ownership."""
from __future__ import annotations

import pytest

from tests.fakes import auth_headers_for, stream_turn

pytestmark = pytest.mark.integration


async def test_sessions_empty_initially(auth_client):
    resp = await auth_client.get("/api/chat/sessions")
    assert resp.status_code == 200
    assert resp.json()["results"] == []


async def test_streamed_turn_creates_session_and_messages(auth_client, fake_llm):
    events = await stream_turn(auth_client, "How do I grow rice?")
    session_event = next(e for e in events if e["type"] == "session")
    session_id = session_event["session_id"]

    # Session now shows up in the list.
    sessions = (await auth_client.get("/api/chat/sessions")).json()["results"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["message_count"] >= 2  # user + assistant

    # Messages endpoint returns the persisted user + assistant bubbles.
    msgs = (
        await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    ).json()["results"]
    roles = [m["role"] for m in msgs]
    assert "user" in roles and "assistant" in roles
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert user_msg["content"] == "How do I grow rice?"


async def test_delete_session_then_404(auth_client, fake_llm):
    events = await stream_turn(auth_client, "hello")
    session_id = next(e for e in events if e["type"] == "session")["session_id"]

    delete = await auth_client.delete(f"/api/chat/sessions/{session_id}")
    assert delete.status_code == 204

    # Getting messages for the deleted session -> 404.
    gone = await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    assert gone.status_code == 404
    # Deleting again -> 404.
    assert (
        await auth_client.delete(f"/api/chat/sessions/{session_id}")
    ).status_code == 404


async def test_second_user_cannot_access_first_users_session(client, fake_llm):
    # First user creates a session.
    u1 = await auth_headers_for(client, "01712345678")
    events = await stream_turn(client, "first user chat", headers=u1)
    session_id = next(e for e in events if e["type"] == "session")["session_id"]

    # Second user must not see it.
    u2 = await auth_headers_for(client, "01812345678")
    get_resp = await client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=u2
    )
    assert get_resp.status_code == 404
    del_resp = await client.delete(
        f"/api/chat/sessions/{session_id}", headers=u2
    )
    assert del_resp.status_code == 404

    # Owner still can (sanity).
    owner_get = await client.get(
        f"/api/chat/sessions/{session_id}/messages", headers=u1
    )
    assert owner_get.status_code == 200
