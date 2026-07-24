"""Unit tests for the Open-Meteo weather adapter + get_weather tool.

Fully offline: HTTP goes through httpx.MockTransport; the tool tests
monkeypatch the adapter functions. No network, ever.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.adapters import weather as weather_mod
from app.agent.tools import build_weather_tool

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# MockTransport helpers
# --------------------------------------------------------------------------- #
def _geocode_payload():
    return {
        "results": [
            {
                "name": "Tanore",
                "latitude": 24.588,
                "longitude": 88.581,
                "country_code": "BD",
                "admin1": "Rajshahi Division",
                "admin2": "Rajshahi",
            },
            {
                "name": "Tanore Somewhere Else",
                "latitude": 10.0,
                "longitude": 10.0,
                "country_code": "IN",
            },
        ]
    }


def _forecast_payload():
    return {
        "timezone": "Asia/Dhaka",
        "daily": {
            "time": ["2026-07-24", "2026-07-25", "2026-07-26"],
            "temperature_2m_max": [33.1, 34.0, 31.2],
            "temperature_2m_min": [26.4, 26.9, 25.8],
            "precipitation_sum": [0.0, 12.5, 2.1],
            "precipitation_probability_max": [10, 85, 40],
            "et0_fao_evapotranspiration": [4.2, 3.1, 3.8],
            "wind_speed_10m_max": [12.0, 18.5, 9.9],
        },
    }


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# geocode_place
# --------------------------------------------------------------------------- #
async def test_geocode_filters_to_bd_and_prefers_district():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "geocoding-api.open-meteo.com"
        return httpx.Response(200, json=_geocode_payload())

    async with make_client(handler) as client:
        geo = await weather_mod.geocode_place(
            "Tanore", district="Rajshahi", client=client
        )
    assert geo["latitude"] == 24.588
    assert geo["geocode_source"] == "open-meteo-geocoding"


async def test_geocode_falls_back_to_bundled_centroid_when_api_down():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with make_client(handler) as client:
        geo = await weather_mod.geocode_place("Tanore", client=client)
    assert geo["geocode_source"] == "bundled_fallback"
    assert geo["latitude"] == pytest.approx(24.588)


async def test_geocode_unknown_place_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    async with make_client(handler) as client:
        with pytest.raises(weather_mod.WeatherError):
            await weather_mod.geocode_place("Nowhereville", client=client)


async def test_geocode_empty_name_raises():
    with pytest.raises(weather_mod.WeatherError):
        await weather_mod.geocode_place("   ")


# --------------------------------------------------------------------------- #
# fetch_forecast
# --------------------------------------------------------------------------- #
async def test_forecast_normalizes_days_and_summary():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_forecast_payload())

    async with make_client(handler) as client:
        result = await weather_mod.fetch_forecast(24.588, 88.581, 3, client=client)

    assert seen_params["timezone"] == "Asia/Dhaka"
    assert seen_params["forecast_days"] == "3"

    assert result["source"] == "Open-Meteo forecast API"
    assert len(result["days"]) == 3
    day2 = result["days"][1]
    assert day2 == {
        "date": "2026-07-25",
        "t_min_c": 26.9,
        "t_max_c": 34.0,
        "rain_mm": 12.5,
        "rain_prob_pct": 85,
        "et0_mm": 3.1,
        "wind_max_kmh": 18.5,
    }
    summary = result["summary"]
    assert summary["total_rain_mm"] == pytest.approx(14.6)
    assert summary["rainy_day_count"] == 2
    assert summary["first_rainy_date"] == "2026-07-25"
    assert summary["max_temp_c"] == 34.0
    assert summary["min_temp_c"] == 25.8
    # Evidence metadata present.
    assert result["request_params"]["latitude"] == pytest.approx(24.588)
    assert result["fetched_at"]


async def test_forecast_clamps_days_to_16():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_forecast_payload())

    async with make_client(handler) as client:
        await weather_mod.fetch_forecast(24.5, 88.5, 60, client=client)
    assert seen_params["forecast_days"] == "16"


async def test_forecast_persistent_500_raises_after_retries():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    async with make_client(handler) as client:
        with pytest.raises(weather_mod.WeatherError):
            await weather_mod.fetch_forecast(24.5, 88.5, 3, client=client)
    assert calls["n"] == weather_mod.RETRIES


async def test_forecast_empty_daily_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"daily": {"time": []}})

    async with make_client(handler) as client:
        with pytest.raises(weather_mod.WeatherError):
            await weather_mod.fetch_forecast(24.5, 88.5, 3, client=client)


# --------------------------------------------------------------------------- #
# get_weather tool (adapter + farm lookup monkeypatched)
# --------------------------------------------------------------------------- #
def _fake_user():
    return SimpleNamespace(
        upazila_name="Tanore",
        upazila_code="508194",
        district_name="Rajshahi",
        district_code="5081",
        division_name="Rajshahi",
        union_name="Badhair",
        union_code="50819427",
    )


def _fake_farm(**overrides):
    base = dict(
        union_name="Badhair",
        union_geocode="50819427",
        upazila_name="Tanore",
        upazila_code="508194",
        district_name="Rajshahi",
        district_code="5081",
        division_name="Rajshahi",
        latitude=24.62968,
        longitude=88.44103,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_farm(monkeypatch, farm):
    import app.agent.tools as tools_mod

    async def fake_get_farm(session, user):
        return farm

    monkeypatch.setattr(tools_mod, "_get_or_create_active_farm", fake_get_farm)


def _forecast_stub(captured):
    async def fake_forecast(lat, lon, days, past_days=0, client=None):
        captured["lat"], captured["lon"], captured["days"] = lat, lon, days
        captured["past_days"] = past_days
        return {
            "source": "Open-Meteo forecast API",
            "fetched_at": "2026-07-24T00:00:00+00:00",
            "request_params": {"latitude": lat, "longitude": lon},
            "timezone": "Asia/Dhaka",
            "days": [],
            "summary": {"total_rain_mm": 0.0},
            "note": "",
        }

    return fake_forecast


async def test_tool_default_uses_farm_coordinates_no_geocoding(monkeypatch):
    # The farmer's own field already has union-centroid lat/lon — the flaky
    # geocoder must NOT be involved at all.
    captured = {}

    async def fail_geocode(name, district=None, client=None):
        raise AssertionError("geocoder must not be called for the default farm")

    monkeypatch.setattr(weather_mod, "geocode_place", fail_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))
    _patch_farm(monkeypatch, _fake_farm())

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "", "days": 5})
    payload = json.loads(raw)

    assert captured["lat"] == 24.62968
    assert captured["lon"] == 88.44103
    assert captured["days"] == 5
    assert payload["location"]["name"] == "Badhair"
    assert payload["location"]["geocode_source"] == "farm_profile"


async def test_tool_default_falls_back_to_gazetteer_centroid(monkeypatch):
    # Farm without stored coords -> bundled gazetteer resolves the union code.
    captured = {}
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))
    _patch_farm(monkeypatch, _fake_farm(latitude=None, longitude=None))

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "", "days": 3})
    payload = json.loads(raw)

    assert payload["location"]["geocode_source"] == "gazetteer_union_centroid"
    assert captured["lat"] == pytest.approx(24.62968)


async def test_tool_named_admin_place_resolves_offline(monkeypatch):
    # "Manda" is an upazila in the bundle -> offline centroid, no geocoder.
    captured = {}

    async def fail_geocode(name, district=None, client=None):
        raise AssertionError("geocoder must not be called for gazetteer names")

    monkeypatch.setattr(weather_mod, "geocode_place", fail_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "Manda", "days": 7})
    payload = json.loads(raw)
    assert payload["location"]["geocode_source"].startswith("gazetteer_")
    assert payload["location"]["name"] == "Manda"


async def test_tool_unknown_place_uses_geocoder_without_district_bias(monkeypatch):
    captured = {}

    async def fake_geocode(name, district=None, client=None):
        captured["name"], captured["district"] = name, district
        return {
            "name": name,
            "latitude": 24.7,
            "longitude": 88.7,
            "admin1": "",
            "admin2": "",
            "geocode_source": "open-meteo-geocoding",
        }

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))

    tool_obj = build_weather_tool(_fake_user())
    await tool_obj.ainvoke({"location": "Some Village Bazar", "days": 7})
    assert captured["name"] == "Some Village Bazar"
    # Explicit location -> registered district must NOT bias the geocoder.
    assert captured["district"] is None


async def test_tool_explicit_coordinates_skip_all_lookup(monkeypatch):
    captured = {}

    async def fail_geocode(name, district=None, client=None):
        raise AssertionError("geocoder must not be called with explicit coords")

    monkeypatch.setattr(weather_mod, "geocode_place", fail_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke(
        {"location": "", "days": 2, "latitude": 23.9, "longitude": 90.1}
    )
    payload = json.loads(raw)
    assert captured["lat"] == 23.9
    assert captured["lon"] == 90.1
    assert payload["location"]["geocode_source"] == "explicit_coordinates"


async def test_tool_failure_returns_unavailable_not_invented(monkeypatch):
    async def fake_geocode(name, district=None, client=None):
        raise weather_mod.WeatherError("network down")

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "Nowhere Bazar", "days": 7})
    assert raw.startswith("WEATHER_UNAVAILABLE")
    assert "network down" in raw


# --------------------------------------------------------------------------- #
# past weather (past_days)
# --------------------------------------------------------------------------- #
def _past_forecast_payload():
    """2 past days + 2 forecast days in one series (Open-Meteo shape).

    Past rows have null precipitation probability, as the live API returns.
    """
    return {
        "timezone": "Asia/Dhaka",
        "daily": {
            "time": ["2026-07-22", "2026-07-23", "2026-07-24", "2026-07-25"],
            "temperature_2m_max": [30.0, 35.5, 33.1, 34.0],
            "temperature_2m_min": [25.0, 26.0, 26.4, 26.9],
            "precipitation_sum": [8.4, 0.0, 0.0, 12.5],
            "precipitation_probability_max": [None, None, 10, 85],
            "et0_fao_evapotranspiration": [3.9, 4.4, 4.2, 3.1],
            "wind_speed_10m_max": [10.0, 11.0, 12.0, 18.5],
        },
    }


async def test_forecast_past_days_marks_rows_and_splits_summaries():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_past_forecast_payload())

    async with make_client(handler) as client:
        result = await weather_mod.fetch_forecast(
            24.588, 88.581, 2, past_days=2, client=client
        )

    assert seen_params["past_days"] == "2"
    assert seen_params["forecast_days"] == "2"

    kinds = [r["kind"] for r in result["days"]]
    assert kinds == ["past", "past", "forecast", "forecast"]

    past = result["past_summary"]
    assert past["past_days"] == 2
    assert past["total_rain_mm"] == pytest.approx(8.4)
    assert past["rainy_day_count"] == 1
    assert past["max_temp_c"] == 35.5

    # Forecast summary must EXCLUDE past rows.
    summary = result["summary"]
    assert summary["forecast_days"] == 2
    assert summary["total_rain_mm"] == pytest.approx(12.5)
    assert summary["first_rainy_date"] == "2026-07-25"
    assert "kind=past" in result["note"]


async def test_forecast_without_past_days_is_unchanged_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "past_days" not in dict(request.url.params)
        return httpx.Response(200, json=_forecast_payload())

    async with make_client(handler) as client:
        result = await weather_mod.fetch_forecast(24.588, 88.581, 3, client=client)

    assert "past_summary" not in result
    assert all("kind" not in r for r in result["days"])


async def test_forecast_clamps_past_days_to_92_and_allows_zero_forecast():
    seen_params = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json=_past_forecast_payload())

    async with make_client(handler) as client:
        await weather_mod.fetch_forecast(24.5, 88.5, 0, past_days=500, client=client)
    assert seen_params["past_days"] == "92"
    assert seen_params["forecast_days"] == "0"


async def test_tool_passes_past_days_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))

    tool_obj = build_weather_tool(_fake_user())
    await tool_obj.ainvoke(
        {"location": "", "days": 7, "past_days": 10,
         "latitude": 23.9, "longitude": 90.1}
    )
    assert captured["days"] == 7
    assert captured["past_days"] == 10


async def test_tool_negative_days_means_past_only(monkeypatch):
    """The -N convention: days=-7 -> past 7 days, zero forecast days."""
    captured = {}
    monkeypatch.setattr(weather_mod, "fetch_forecast", _forecast_stub(captured))

    tool_obj = build_weather_tool(_fake_user())
    await tool_obj.ainvoke(
        {"location": "", "days": -7, "latitude": 23.9, "longitude": 90.1}
    )
    assert captured["days"] == 0
    assert captured["past_days"] == 7
