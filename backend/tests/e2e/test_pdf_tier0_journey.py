"""Whole-product journeys mapped directly to the hackathon PDF Tier 0."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent import tools as tools_mod
from app.models import Farm
from app.rag import ingest_document
from tests.fakes import stream_turn

pytestmark = pytest.mark.streaming


def _weather(lat, lon, days=16):
    return {
        "source": "Open-Meteo forecast API",
        "fetched_at": "2026-07-24T12:00:00+00:00",
        "request_params": {"latitude": lat, "longitude": lon, "days": days},
        "summary": {
            "forecast_days": days,
            "total_rain_mm": 8.0,
            "max_temp_c": 31.0,
            "min_temp_c": 18.0,
        },
        "days": [{"date": "2026-11-15", "rain_mm": 1.0}],
    }


def _varieties(crop_id):
    return {
        "crop_id": crop_id,
        "varieties": [
            {
                "name": "BARI Gom 33",
                "yield_t_ha": "4.0-5.0",
                "duration_days": "115-120",
                "characteristics": "reference",
            }
        ],
        "evidence": {"source": "CZIS", "endpoint": f"/varieties/{crop_id}"},
    }


def _completed_traces(events):
    # A parallel tool-call message is updated once per returned ToolMessage,
    # so later updates repeat already-filled entries. Keep each call/result
    # once when asserting the user-visible logical trace.
    unique = []
    seen = set()
    for event in events:
        if event["type"] != "message_update":
            continue
        for trace in event["message"].get("tool_trace") or []:
            if not trace.get("result"):
                continue
            marker = (
                trace.get("tool"),
                json.dumps(trace.get("args") or {}, sort_keys=True),
                trace.get("result"),
            )
            if marker not in seen:
                seen.add(marker)
                unique.append(trace)
    return unique


@pytest.mark.parametrize("fake_llm", ["full_pdf_journey"], indirect=True)
async def test_vague_opening_reaches_grounded_explained_costed_plan(
    auth_client, fake_llm, db_session, monkeypatch
):
    """PDF #1-#8 in one persisted five-turn farmer journey."""
    await ingest_document(
        db_session,
        "<!-- Page 90 (embedded) -->\n\nWheat nitrogen timing and soil management reference.",
        source="FRG 2024",
        crop="wheat",
    )

    async def weather(lat, lon, days, **kwargs):
        return _weather(lat, lon, days)

    async def suitability(lat, lon, crop_ids, **kwargs):
        return {
            "latitude": lat,
            "longitude": lon,
            "crops": [
                {
                    "crop_id": crop_id,
                    "suitability": 1,
                    "suite_code": "VS",
                    "suite": "Very Suitable",
                }
                for crop_id in crop_ids
            ],
            "missing_crop_ids": [],
            "evidence": {
                "source": "BARC CZIS GeoServer",
                "request_params": {"crop_ids": crop_ids},
            },
        }

    async def varieties(crop_id, **kwargs):
        return _varieties(crop_id)

    async def context(crop_id, lat, lon, **kwargs):
        return {
            "crop_id": crop_id,
            "crop_name": "Wheat",
            "varieties": [{"variety_id": 1001, "name": "BARI Gom 33"}],
            "evidence": {"source": "CZIS crop context"},
        }

    async def fertilizer(crop_id, lat, lon, variety_id, area, **kwargs):
        assert (crop_id, variety_id, area) == (3, 1001, 50.0)
        return {
            "crop_id": crop_id,
            "variety_id": variety_id,
            "area_decimal": area,
            "products": [
                {
                    "product": "Urea",
                    "element": "N",
                    "amount": {"value": 30, "unit": "kg"},
                    "is_alternative": False,
                },
                {
                    "product": "TSP",
                    "element": "P",
                    "amount": {"value": 12, "unit": "kg"},
                    "is_alternative": False,
                },
            ],
            "evidence": {"source": "CZIS", "computed_by": "CZIS server"},
        }

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", weather)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod, "get_point_suitability", suitability
    )
    monkeypatch.setattr(tools_mod.czis_mod, "get_varieties", varieties)
    monkeypatch.setattr(tools_mod.czis_mod, "get_crop_context", context)
    monkeypatch.setattr(
        tools_mod.czis_mod, "get_fertilizer_recommendation", fertilizer
    )

    all_events = []
    session_id = None
    messages = [
        "Can you help me plan my farm?",
        "amar 50 shotok jomi, shallow pump diye sech ache",
        "budget 150000 taka, rabi season",
        "এখন কোন ফসল লাগাব?",
        "গম বেছে নিলাম। ১৫ নভেম্বর থেকে costed season plan বানাও",
    ]
    for message in messages:
        events = await stream_turn(auth_client, message, session_id=session_id)
        assert events[-1]["type"] == "done"
        assert all(event["type"] != "error" for event in events)
        session_id = events[0]["session_id"]
        all_events.append(events)

    opening_tools = {trace["tool"] for trace in _completed_traces(all_events[0])}
    assert opening_tools <= {"get_farm_profile", "update_farm_profile", "resolve_season"}
    assert not opening_tools & {"web_search", "search_wikipedia"}

    # Intake is targeted and persisted; no recommendation happened early.
    opening_final = [
        event["message"]["content"]
        for event in all_events[0]
        if event["type"] == "message"
        and event["message"]["role"] == "assistant"
        and event["message"]["content"].strip()
    ][-1]
    assert "আকার" in opening_final and "সেচ" in opening_final
    assert "বাজেট" not in opening_final
    farm = (await db_session.execute(select(Farm))).scalar_one()
    assert farm.area_decimal == 50
    assert farm.irrigation_available is True
    assert farm.budget_bdt == 150000
    assert farm.season == "rabi"
    assert farm.soil_texture == "Clay Loam"
    assert farm.phase == "ready_for_planning"

    recommendation = next(
        json.loads(trace["result"])
        for trace in _completed_traces(all_events[3])
        if trace["tool"] == "rank_crop_candidates"
    )
    assert recommendation["status"] == "ok"
    assert len(recommendation["candidates"]) >= 3
    assert recommendation["weather"]["summary"]["total_rain_mm"] == 8
    assert recommendation["land_suitability"]["evidence"]["source"] == "BARC CZIS GeoServer"
    for candidate in recommendation["candidates"]:
        assert {"suitability", "water_need", "risk", "rough_profit"} <= candidate.keys()

    plan = next(
        json.loads(trace["result"])
        for trace in _completed_traces(all_events[4])
        if trace["tool"] == "generate_season_plan"
    )
    assert plan["status"] == "ok"
    categories = {event["category"] for event in plan["calendar"]["events"]}
    assert {
        "land_preparation",
        "sowing",
        "fertilizer",
        "irrigation",
        "weed",
        "pest",
        "harvest",
    } <= categories
    assert plan["knowledge_evidence"][0]["source"] == "FRG 2024"
    projection = plan["financial_projection"]
    assert projection["price_assumption"] == {
        "value_bdt_per_kg": 42.0,
        "source_type": "farmer_estimate",
    }
    assert projection["total_cost_bdt"] == sum(
        item["amount_bdt"] for item in projection["cost_items"]
    )
    assert projection["expected"]["revenue_bdt"] - projection["total_cost_bdt"] == pytest.approx(
        projection["expected"]["net_profit_bdt"], abs=0.01
    )

    # Visible trace: args and raw results survive every layer and persistence.
    traces = [trace for turn in all_events for trace in _completed_traces(turn)]
    tool_names = [trace["tool"] for trace in traces]
    assert {
        "get_farm_profile",
        "update_farm_profile",
        "rank_crop_candidates",
        "czis_crop_varieties",
        "search_knowledge_base",
        "generate_season_plan",
    } <= set(tool_names)
    assert tool_names.count("czis_crop_varieties") == 3
    assert all(isinstance(trace["args"], dict) and trace["result"] for trace in traces)

    stored = (
        await auth_client.get(f"/api/chat/sessions/{session_id}/messages")
    ).json()["results"]
    assert len([message for message in stored if message["role"] == "user"]) == 5
    stored_tools = {
        trace["tool"]
        for message in stored
        for trace in message.get("tool_trace") or []
        if trace.get("result")
    }
    assert {"rank_crop_candidates", "generate_season_plan"} <= stored_tools
