"""SSE matrix for every crop on the deliberately focused Tier-0 path."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.agent import tools as tools_mod
from app.agent.tools import _get_or_create_active_farm
from app.models import User
from app.rag import ingest_document
from tests.fakes import stream_turn

pytestmark = pytest.mark.streaming


CASES = [
    ("wheat", "Wheat", 3, "2026-11-15", 119, 4.5, 42.0, 0.0),
    ("mustard", "Mustard", 22, "2026-11-15", 90, 1.6, 78.0, 5.0),
    ("potato", "Potato", 12, "2026-10-20", 105, 25.0, 24.0, 10.0),
    ("maize", "Maize", 6, "2026-11-10", 112, 9.5, 31.0, -5.0),
    ("boro", "Boro dhan", 1, "2026-12-01", 153, 5.5, 29.0, 15.0),
]


async def _complete_farm(db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    farm = await _get_or_create_active_farm(db_session, user)
    farm.area_decimal = 40.0
    farm.irrigation_available = True
    farm.water_source = "shallow tubewell"
    farm.budget_bdt = 100_000
    farm.season = "rabi"
    farm.phase = "ready_for_planning"
    await db_session.commit()
    return farm


def _completed_tool(events, name):
    return next(
        json.loads(trace["result"])
        for event in events
        if event["type"] == "message_update"
        for trace in event["message"].get("tool_trace") or []
        if trace.get("tool") == name and trace.get("result")
    )


@pytest.mark.parametrize(
    "fake_llm,slug,crop,crop_id,planting,duration,expected_yield,price,adjustment",
    [
        (f"matrix_plan_{slug}", slug, crop, crop_id, planting, duration, expected_yield, price, adjustment)
        for slug, crop, crop_id, planting, duration, expected_yield, price, adjustment in CASES
    ],
    indirect=["fake_llm"],
)
async def test_each_focused_crop_returns_a_complete_costed_plan_over_sse(
    auth_client,
    fake_llm,
    slug,
    crop,
    crop_id,
    planting,
    duration,
    expected_yield,
    price,
    adjustment,
    db_session,
    monkeypatch,
):
    farm = await _complete_farm(db_session)
    await ingest_document(
        db_session,
        f"{crop} fertilizer timing irrigation and season reference.",
        source="FRG 2024",
        crop=crop.lower(),
    )

    async def weather(lat, lon, days, **kwargs):
        assert (lat, lon) == (farm.latitude, farm.longitude)
        return {
            "source": "Open-Meteo forecast API",
            "summary": {"forecast_days": days, "total_rain_mm": 2},
            "days": [{"date": planting, "rain_mm": 0}],
        }

    async def context(requested_crop_id, lat, lon, **kwargs):
        assert requested_crop_id == crop_id
        return {
            "crop_id": crop_id,
            "crop_name": crop,
            "varieties": [{"variety_id": 1000 + crop_id, "name": f"{crop} Test Variety"}],
            "evidence": {"source": "CZIS crop context"},
        }

    async def fertilizer(requested_crop_id, lat, lon, variety_id, area, **kwargs):
        assert (requested_crop_id, variety_id, area) == (
            crop_id,
            1000 + crop_id,
            40.0,
        )
        return {
            "products": [
                {
                    "product": "Urea",
                    "element": "N",
                    "amount": {"value": 10, "unit": "kg"},
                    "is_alternative": False,
                }
            ],
            "evidence": {"source": "CZIS", "computed_by": "CZIS server"},
        }

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", weather)
    monkeypatch.setattr(tools_mod.czis_mod, "get_crop_context", context)
    monkeypatch.setattr(
        tools_mod.czis_mod, "get_fertilizer_recommendation", fertilizer
    )
    events = await stream_turn(auth_client, f"Make a costed season plan for {crop}")

    routing = [
        event["detail"]
        for event in events
        if event["type"] == "progress" and event.get("stage") == "routing"
    ]
    assert routing and "specialist: planner" in routing[0]
    assert events[-1]["type"] == "done"
    plan = _completed_tool(events, "generate_season_plan")
    assert plan["status"] == "ok"
    assert plan["selected_crop"] == {"crop_id": crop_id, "name": crop}
    assert plan["calendar"]["planting_date"] == planting
    assert plan["calendar"]["harvest_date"] == (
        date.fromisoformat(planting) + timedelta(days=duration)
    ).isoformat()
    categories = {item["category"] for item in plan["calendar"]["events"]}
    assert {"land_preparation", "sowing", "fertilizer", "irrigation", "weed", "pest", "harvest"} <= categories
    assert plan["knowledge_evidence"][0]["source"] == "FRG 2024"
    projection = plan["financial_projection"]
    assert projection["expected"]["yield_t_ha"] == expected_yield
    assert projection["expected"]["price_bdt_per_kg"] == price
    assert projection["math_checks"] == {
        "cost_items_sum_to_total": True,
        "profit_equals_revenue_minus_cost": True,
    }
    assert not any(
        trace.get("tool") == "calculate_crop_financials"
        for event in events
        if event["type"] == "message_update"
        for trace in event["message"].get("tool_trace") or []
    )


@pytest.mark.parametrize(
    "fake_llm,slug,crop,crop_id,planting,duration,expected_yield,price,adjustment",
    [
        (f"matrix_finance_{slug}", slug, crop, crop_id, planting, duration, expected_yield, price, adjustment)
        for slug, crop, crop_id, planting, duration, expected_yield, price, adjustment in CASES
    ],
    indirect=["fake_llm"],
)
async def test_each_crop_financial_what_if_flows_through_specialist_and_trace(
    auth_client,
    fake_llm,
    slug,
    crop,
    crop_id,
    planting,
    duration,
    expected_yield,
    price,
    adjustment,
    db_session,
):
    await _complete_farm(db_session)
    events = await stream_turn(
        auth_client, f"Calculate ROI and break-even for {crop} with changed costs"
    )
    routing = [
        event["detail"]
        for event in events
        if event["type"] == "progress" and event.get("stage") == "routing"
    ]
    assert routing and "specialist: finance" in routing[0]
    raw = _completed_tool(events, "calculate_crop_financials")
    assert raw["status"] == "ok"
    projection = raw["financial_projection"]
    assert projection["crop_name"] == crop
    assert projection["yield_assumption"]["source"]["source_type"] == "farmer_estimate"
    assert projection["price_assumption"]["source_type"] == "farmer_estimate"
    assert projection["assumptions"]["cost_adjustment_percent"] == adjustment
    assert projection["expected"]["revenue_bdt"] - projection["total_cost_bdt"] == pytest.approx(
        projection["expected"]["net_profit_bdt"], abs=0.01
    )
    assert projection["break_even"]["yield_kg"] > 0
    assert projection["break_even"]["price_bdt_per_kg"] > 0


@pytest.mark.parametrize(
    "fake_llm,slug,crop,crop_id,planting,duration,expected_yield,price,adjustment",
    [
        (f"matrix_gate_{slug}", slug, crop, crop_id, planting, duration, expected_yield, price, adjustment)
        for slug, crop, crop_id, planting, duration, expected_yield, price, adjustment in CASES
    ],
    indirect=["fake_llm"],
)
async def test_each_crop_plan_hard_gates_missing_profile_before_external_calls(
    auth_client,
    fake_llm,
    slug,
    crop,
    crop_id,
    planting,
    duration,
    expected_yield,
    price,
    adjustment,
    monkeypatch,
):
    async def forbidden(*args, **kwargs):
        pytest.fail("external data must not be called before intake is complete")

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", forbidden)
    monkeypatch.setattr(tools_mod.czis_mod, "get_crop_context", forbidden)
    events = await stream_turn(auth_client, f"Make a season plan for {crop}")
    assert events[-1]["type"] == "done"
    raw = _completed_tool(events, "generate_season_plan")
    assert raw["status"] == "PROFILE_INCOMPLETE"
    assert set(raw["missing_required_fields"]) == {
        "farm_size",
        "water_availability",
        "budget",
        "season",
    }
