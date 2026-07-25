"""Integration tests for the complete deterministic recommendation tool."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.agent import tools as tools_mod
from app.agent.tools import (
    _get_or_create_active_farm,
    build_crop_recommendation_tool,
    build_research_tools,
)
from app.models import User
from app.rag import ingest_document


async def _user_and_farm(db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    farm = await _get_or_create_active_farm(db_session, user)
    return user, farm


async def _complete_farm(db_session):
    user, farm = await _user_and_farm(db_session)
    farm.area_decimal = 99.0
    farm.original_area_value = 3
    farm.original_area_unit = "bigha"
    farm.irrigation_available = True
    farm.water_source = "shallow tubewell"
    farm.budget_bdt = 180_000
    farm.season = "rabi"
    farm.phase = "ready_for_planning"
    await db_session.commit()
    return user, farm


@pytest.mark.asyncio
async def test_research_tools_are_banned_until_profile_is_complete(
    auth_client, db_session, monkeypatch
):
    """web_search / search_wikipedia refuse while intake is incomplete."""
    called = {"web": False, "wiki": False}

    async def fake_web(query, max_results):
        called["web"] = True
        return {"source": "DuckDuckGo search", "results": []}

    async def fake_wiki(query, **kwargs):
        called["wiki"] = True
        return {"source": "Wikipedia (en)", "results": []}

    monkeypatch.setattr(tools_mod.research_mod, "search_web", fake_web)
    monkeypatch.setattr(tools_mod.research_mod, "search_wikipedia", fake_wiki)

    user, _farm = await _user_and_farm(db_session)  # incomplete by default
    web_search, search_wikipedia = build_research_tools(user)

    web = json.loads(await web_search.ainvoke({"query": "urea price"}))
    wiki = json.loads(await search_wikipedia.ainvoke({"query": "wheat"}))
    assert web["status"] == "PROFILE_INCOMPLETE"
    assert wiki["status"] == "PROFILE_INCOMPLETE"
    # The external providers were never actually called.
    assert called == {"web": False, "wiki": False}

    # Once the six fields are locked, the searches run.
    await _complete_farm(db_session)
    web2 = json.loads(await web_search.ainvoke({"query": "urea price"}))
    assert web2["status"] == "ok"
    assert called["web"] is True


@pytest.mark.asyncio
async def test_recommendation_tool_hard_gates_incomplete_profile(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _user_and_farm(db_session)

    async def forbidden(*args, **kwargs):
        pytest.fail("external services must not run before profile completion")

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", forbidden)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod, "get_point_suitability", forbidden
    )
    payload = json.loads(
        await build_crop_recommendation_tool(user).ainvoke({"limit": 5})
    )

    assert payload["status"] == "PROFILE_INCOMPLETE"
    assert set(payload["missing_required_fields"]) == {
        "farm_size",
        "water_availability",
        "budget",
        "season",
    }


@pytest.mark.asyncio
async def test_recommendation_tool_returns_three_weather_and_czis_grounded_crops(
    auth_client, db_session, monkeypatch
):
    user, farm = await _complete_farm(db_session)
    await ingest_document(
        db_session,
        "<!-- Page 72 (embedded) -->\n\n"
        "Rabi crop selection should account for soil drainage, irrigation "
        "access, and the locally appropriate sowing window.",
        source="FRG 2024",
        topic="crop selection",
    )

    async def fake_weather(lat, lon, days, **kwargs):
        assert (lat, lon) == (farm.latitude, farm.longitude)
        assert days == 7
        return {
            "source": "Open-Meteo forecast API",
            "fetched_at": "2026-07-24T12:00:00+00:00",
            "request_params": {"latitude": lat, "longitude": lon},
            "days": [{"date": "2026-07-25", "rain_mm": 2.0}],
            "summary": {
                "forecast_days": 7,
                "total_rain_mm": 8.0,
                "max_temp_c": 31.0,
                "min_temp_c": 18.0,
            },
        }

    async def fake_suitability(lat, lon, crop_ids, **kwargs):
        classes = ["VS", "S", "MS"]
        rows = [
            {
                "crop_id": crop_id,
                "suitability": (i % 3) + 1,
                "suite_code": classes[i % 3],
                "suite": {
                    "VS": "Very Suitable",
                    "S": "Suitable",
                    "MS": "Moderately Suitable",
                }[classes[i % 3]],
            }
            for i, crop_id in enumerate(crop_ids)
        ]
        return {
            "latitude": lat,
            "longitude": lon,
            "crops": rows,
            "missing_crop_ids": [],
            "evidence": {
                "source": "BARC CZIS GeoServer",
                "request_params": {"crop_ids": crop_ids},
            },
        }

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", fake_weather)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod,
        "get_point_suitability",
        fake_suitability,
    )

    payload = json.loads(
        await build_crop_recommendation_tool(user).ainvoke({"limit": 5})
    )

    assert payload["status"] == "ok"
    assert len(payload["candidates"]) >= 3
    assert payload["farm_inputs"]["area_decimal"] == 99.0
    assert payload["weather"]["source"] == "Open-Meteo forecast API"
    assert payload["land_suitability"]["evidence"]["source"] == "BARC CZIS GeoServer"
    assert payload["knowledge_status"] == "ok"
    assert payload["knowledge_evidence"][0]["source"] == "FRG 2024"
    assert payload["knowledge_usage"].startswith("Retrieved passages are supplied")
    assert payload["sources"]["economics"].startswith("https://czis.cropzoning.gov.bd")
    for candidate in payload["candidates"]:
        assert {
            "rank",
            "crop_name",
            "suitability",
            "water_need",
            "risk",
            "rough_profit",
        } <= candidate.keys()
        assert candidate["rough_profit"]["gross_revenue_tk"] - candidate[
            "rough_profit"
        ]["total_cost_tk"] == pytest.approx(
            candidate["rough_profit"]["estimate_tk"], abs=1
        )


@pytest.mark.asyncio
async def test_recommendation_tool_degrades_honestly_on_live_source_outages(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _complete_farm(db_session)

    async def no_weather(*args, **kwargs):
        raise tools_mod.weather_mod.WeatherError("offline")

    async def no_suitability(*args, **kwargs):
        raise tools_mod.czis_suitability_mod.CzisSuitabilityError("offline")

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", no_weather)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod,
        "get_point_suitability",
        no_suitability,
    )
    payload = json.loads(
        await build_crop_recommendation_tool(user).ainvoke({"limit": 3})
    )

    assert payload["status"] == "degraded"
    assert set(payload["unavailable_sources"]) == {"weather", "land_suitability"}
    assert len(payload["candidates"]) == 3
    assert all(c["suitability"]["class"] == "Unknown" for c in payload["candidates"])
    assert all(c["score_components"]["weather"] == 5.0 for c in payload["candidates"])


@pytest.mark.asyncio
async def test_recommendation_tool_marks_partial_suitability_coverage_degraded(
    auth_client, db_session, monkeypatch
):
    user, _farm = await _complete_farm(db_session)

    async def fake_weather(*args, **kwargs):
        return {
            "source": "Open-Meteo forecast API",
            "summary": {"total_rain_mm": 0, "max_temp_c": 29, "min_temp_c": 17},
            "days": [],
        }

    async def partial_suitability(lat, lon, crop_ids, **kwargs):
        first = crop_ids[0]
        return {
            "latitude": lat,
            "longitude": lon,
            "crops": [
                {"crop_id": first, "suite_code": "VS", "suite": "Very Suitable"}
            ],
            "missing_crop_ids": crop_ids[1:],
            "evidence": {"source": "BARC CZIS GeoServer"},
        }

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", fake_weather)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod,
        "get_point_suitability",
        partial_suitability,
    )
    payload = json.loads(
        await build_crop_recommendation_tool(user).ainvoke({"limit": 3})
    )

    assert payload["status"] == "degraded"
    assert payload["unavailable_sources"] == ["land_suitability_partial"]
    assert any(c["suitability"]["class"] == "Unknown" for c in payload["candidates"])


@pytest.mark.asyncio
async def test_recommendation_tool_rejects_unsupported_season_before_external_calls(
    auth_client, db_session, monkeypatch
):
    user, farm = await _complete_farm(db_session)
    farm.season = "summer-2027"
    await db_session.commit()

    async def forbidden(*args, **kwargs):
        pytest.fail("external sources must not run for an unsupported season")

    monkeypatch.setattr(tools_mod.weather_mod, "fetch_forecast", forbidden)
    monkeypatch.setattr(
        tools_mod.czis_suitability_mod, "get_point_suitability", forbidden
    )
    payload = json.loads(
        await build_crop_recommendation_tool(user).ainvoke({"limit": 3})
    )

    assert payload["status"] == "UNSUPPORTED_SEASON"
    assert payload["supported_seasons"] == ["rabi", "kharif-1", "kharif-2"]
