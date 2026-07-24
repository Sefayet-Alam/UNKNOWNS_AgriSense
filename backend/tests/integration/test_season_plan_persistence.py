"""generate_season_plan must persist the calendar it returns (Tier 1)."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent import tools as tools_mod
from app.agent.tools import _get_or_create_active_farm, build_season_plan_tool
from app.models import SeasonPlan, User
from app.rag import ingest_document


async def _complete_farm(db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    farm = await _get_or_create_active_farm(db_session, user)
    farm.area_decimal = 50.0
    farm.irrigation_available = True
    farm.water_source = "shallow tubewell"
    farm.budget_bdt = 150_000
    farm.season = "rabi"
    farm.phase = "ready_for_planning"
    await db_session.commit()
    return user, farm


def _weather(days=None):
    return {
        "source": "Open-Meteo forecast API",
        "fetched_at": "2026-07-24T12:00:00+00:00",
        "summary": {"forecast_days": 16},
        "days": days or [],
    }


def _context(crop_id=3):
    return {
        "crop_id": crop_id,
        "crop_name": "Wheat",
        "varieties": [{"variety_id": 1001, "name": "BARI Gom 33"}],
        "evidence": {"source": "CZIS crop context"},
    }


def _fertilizer():
    return {
        "products": [
            {
                "product": "Urea",
                "element": "N",
                "amount": {"value": 30, "unit": "kg", "raw": "30 kg"},
                "is_alternative": False,
            }
        ],
        "notes": [],
        "evidence": {"source": "CZIS server", "computed_by": "CZIS server"},
    }


def _varieties(crop_id=3):
    return {
        "crop_id": crop_id,
        "varieties": [
            {
                "name": "BARI Gom 33",
                "yield_t_ha": "4.0-5.0",
                "duration_days": "115-120",
            }
        ],
        "evidence": {"source": "CZIS", "endpoint": f"/varieties/{crop_id}"},
    }


def _patch_live_sources(monkeypatch):
    async def weather(*args, **kwargs):
        return _weather([{"date": "2026-11-15", "rain_mm": 0}])

    async def context(*args, **kwargs):
        return _context()

    async def fertilizer(*args, **kwargs):
        return _fertilizer()

    async def varieties(*args, **kwargs):
        return _varieties()

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", weather)
    monkeypatch.setattr(tools_mod.czis_mod, "get_crop_context", context)
    monkeypatch.setattr(
        tools_mod.czis_mod, "get_fertilizer_recommendation", fertilizer
    )
    monkeypatch.setattr(tools_mod.czis_mod, "get_varieties", varieties)


@pytest.mark.asyncio
async def test_successful_plan_generation_persists_a_season_plan_row(
    auth_client, db_session, monkeypatch
):
    user, farm = await _complete_farm(db_session)
    await ingest_document(
        db_session, "Wheat nitrogen split timing.", source="FRG 2024", crop="wheat"
    )
    _patch_live_sources(monkeypatch)

    payload = json.loads(
        await build_season_plan_tool(user).ainvoke(
            {"crop_name": "Wheat", "planting_date": "2026-11-15"}
        )
    )

    assert payload["status"] == "ok"
    assert payload["season_plan_saved"] is True
    assert payload["season_plan_id"] is not None

    row = (
        await db_session.execute(
            select(SeasonPlan).where(SeasonPlan.id == payload["season_plan_id"])
        )
    ).scalar_one()
    assert row.farm_id == farm.id
    assert row.crop_name == "Wheat"
    assert row.status == "ok"
    assert row.planting_date.isoformat() == "2026-11-15"
    assert row.harvest_date.isoformat() == payload["calendar"]["harvest_date"]
    assert row.duration_days == payload["calendar"]["duration_days"]
    assert row.calendar["events"] == payload["calendar"]["events"]
    assert row.financial_projection == payload["financial_projection"]


@pytest.mark.asyncio
async def test_degraded_plan_is_persisted_with_degraded_status(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _complete_farm(db_session)
    await ingest_document(db_session, "Wheat reference", source="FRG")
    _patch_live_sources(monkeypatch)

    async def no_fertilizer(*args, **kwargs):
        raise tools_mod.czis_mod.CzisError("offline")

    monkeypatch.setattr(
        tools_mod.czis_mod, "get_fertilizer_recommendation", no_fertilizer
    )

    payload = json.loads(
        await build_season_plan_tool(user).ainvoke(
            {"crop_name": "Wheat", "planting_date": "2026-11-15"}
        )
    )
    assert payload["status"] == "degraded"
    assert payload["season_plan_saved"] is True
    row = (
        await db_session.execute(
            select(SeasonPlan).where(SeasonPlan.id == payload["season_plan_id"])
        )
    ).scalar_one()
    assert row.status == "degraded"


@pytest.mark.asyncio
async def test_hard_gate_failures_persist_nothing(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _complete_farm(db_session)

    async def forbidden(*args, **kwargs):
        pytest.fail("no network for a hard-gated request")

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", forbidden)
    payload = json.loads(
        await build_season_plan_tool(user).ainvoke({"crop_name": "Dragon fruit"})
    )
    assert payload["status"] == "UNSUPPORTED_CROP"
    count = len(
        (await db_session.execute(select(SeasonPlan))).scalars().all()
    )
    assert count == 0


@pytest.mark.asyncio
async def test_each_generation_appends_and_latest_wins_by_recency(
    auth_client, db_session, monkeypatch
):
    user, farm = await _complete_farm(db_session)
    await ingest_document(db_session, "Wheat reference", source="FRG")
    _patch_live_sources(monkeypatch)

    tool = build_season_plan_tool(user)
    first = json.loads(
        await tool.ainvoke({"crop_name": "Wheat", "planting_date": "2026-11-15"})
    )
    second = json.loads(
        await tool.ainvoke({"crop_name": "Wheat", "planting_date": "2026-11-20"})
    )
    assert first["season_plan_id"] != second["season_plan_id"]

    rows = (
        (
            await db_session.execute(
                select(SeasonPlan)
                .where(SeasonPlan.farm_id == farm.id)
                .order_by(SeasonPlan.created_at.desc(), SeasonPlan.id.desc())
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert rows[0].id == second["season_plan_id"]
    assert rows[0].planting_date.isoformat() == "2026-11-20"
