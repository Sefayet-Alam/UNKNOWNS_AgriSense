"""Integration tests for the find_suppliers marketplace tool (Tier 2)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent.tools import _get_or_create_active_farm, build_marketplace_tool
from app.models import User


async def _farm_with_coords(db_session, lat=24.46, lon=88.65):
    user = (await db_session.execute(select(User))).scalar_one()
    farm = await _get_or_create_active_farm(db_session, user)
    farm.latitude = lat
    farm.longitude = lon
    farm.upazila_name = "Paba"
    await db_session.commit()
    return user, farm


@pytest.mark.asyncio
async def test_find_suppliers_ranks_from_farm_coords(auth_client, db_session):
    user, _farm = await _farm_with_coords(db_session)
    payload = json.loads(
        await build_marketplace_tool(user).ainvoke({"product": "Urea"})
    )
    assert payload["status"] == "ok"
    assert payload["farm_location"]  # a resolved farm label
    assert payload["results"]
    top = payload["results"][0]
    assert {"price_bdt", "distance_km", "delivery_days", "rating", "score"} <= set(top)
    assert 0.0 <= top["score"] <= 1.0


@pytest.mark.asyncio
async def test_sort_by_price(auth_client, db_session):
    user, _farm = await _farm_with_coords(db_session)
    payload = json.loads(
        await build_marketplace_tool(user).ainvoke(
            {"product": "Urea", "sort_by": "price", "max_results": 10}
        )
    )
    prices = [r["price_bdt"] for r in payload["results"]]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_no_coords_is_gated(auth_client, db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    farm = await _get_or_create_active_farm(db_session, user)
    farm.latitude = None
    farm.longitude = None
    await db_session.commit()
    payload = json.loads(
        await build_marketplace_tool(user).ainvoke({"product": "Urea"})
    )
    assert payload["status"] == "LOCATION_UNRESOLVED"


@pytest.mark.asyncio
async def test_no_match(auth_client, db_session):
    user, _farm = await _farm_with_coords(db_session)
    payload = json.loads(
        await build_marketplace_tool(user).ainvoke({"product": "spaceship"})
    )
    assert payload["status"] == "NO_SUPPLIER_MATCH"
