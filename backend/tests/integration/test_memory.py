"""Integration tests for user-scoped long-term (pgvector) memory.

Uses the offline deterministic ``fake`` embeddings (the app default), so no
network calls happen.
"""
from __future__ import annotations

import pytest

from app.agent import memory as memory_mod
from tests.fakes import register_user

pytestmark = pytest.mark.integration


async def _make_user(client, phone: str) -> int:
    resp = await register_user(client, phone)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_saved_memory_is_recalled_for_same_user(client, db_session):
    user_id = await _make_user(client, "01712345678")

    fact = "The farmer grows Boro rice in Tanore upazila."
    await memory_mod.save_memory(db_session, user_id, fact)

    recalled = await memory_mod.recall_memory(
        db_session, user_id, "what crop does the farmer cultivate", k=5
    )
    assert fact in recalled


async def test_memory_is_user_scoped(client, db_session):
    user_a = await _make_user(client, "01712345678")
    user_b = await _make_user(client, "01812345678")

    fact = "User A prefers organic fertilizer for tomatoes."
    await memory_mod.save_memory(db_session, user_a, fact)

    # User B must NOT recall User A's memory.
    recalled_b = await memory_mod.recall_memory(
        db_session, user_b, "fertilizer preference", k=5
    )
    assert fact not in recalled_b
    assert recalled_b == []  # User B has no memories at all.

    # User A still recalls it.
    recalled_a = await memory_mod.recall_memory(
        db_session, user_a, "fertilizer preference", k=5
    )
    assert fact in recalled_a


async def test_blank_content_is_ignored(client, db_session):
    user_id = await _make_user(client, "01712345678")
    await memory_mod.save_memory(db_session, user_id, "   ")
    recalled = await memory_mod.recall_memory(db_session, user_id, "anything", k=5)
    assert recalled == []
