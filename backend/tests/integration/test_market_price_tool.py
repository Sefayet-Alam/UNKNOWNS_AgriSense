"""Integration tests for the get_market_price tool (Tier 2)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent.tools import build_market_price_tool
from app.models import User


@pytest.mark.asyncio
async def test_market_price_returns_analysis_and_recommendation(auth_client, db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    payload = json.loads(
        await build_market_price_tool(user).ainvoke({"crop": "potato"})
    )
    assert payload["status"] == "ok"
    assert payload["crop"] == "Potato"
    assert payload["analysis"]["trend"] == "rising"
    assert payload["recommendation"]["action"] in {"store", "wait", "sell_now"}
    # No live source configured in tests -> honest degradation, not invention.
    assert payload["live_price"]["status"] == "LIVE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_alias_resolves(auth_client, db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    payload = json.loads(
        await build_market_price_tool(user).ainvoke({"crop": "alu"})
    )
    assert payload["status"] == "ok"
    assert payload["crop"] == "Potato"


@pytest.mark.asyncio
async def test_unknown_crop_lists_supported(auth_client, db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    payload = json.loads(
        await build_market_price_tool(user).ainvoke({"crop": "jackfruit"})
    )
    assert payload["status"] == "UNKNOWN_CROP"
    assert "potato" in payload["supported"]
