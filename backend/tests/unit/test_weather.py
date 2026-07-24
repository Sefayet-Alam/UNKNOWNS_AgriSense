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
# get_weather tool (adapter monkeypatched)
# --------------------------------------------------------------------------- #
def _fake_user():
    return SimpleNamespace(
        upazila_name="Tanore", district_name="Rajshahi", division_name="Rajshahi"
    )


async def test_tool_defaults_to_registered_upazila(monkeypatch):
    captured = {}

    async def fake_geocode(name, district=None, client=None):
        captured["name"] = name
        captured["district"] = district
        return {
            "name": "Tanore",
            "latitude": 24.588,
            "longitude": 88.581,
            "admin1": "",
            "admin2": "",
            "geocode_source": "open-meteo-geocoding",
        }

    async def fake_forecast(lat, lon, days, client=None):
        captured["days"] = days
        return {
            "source": "Open-Meteo forecast API",
            "fetched_at": "2026-07-24T00:00:00+00:00",
            "request_params": {"latitude": lat, "longitude": lon},
            "timezone": "Asia/Dhaka",
            "days": [],
            "summary": {"total_rain_mm": 0.0},
            "note": "",
        }

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", fake_forecast)

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "", "days": 5})
    payload = json.loads(raw)

    assert captured["name"] == "Tanore"
    assert captured["district"] == "Rajshahi"  # registered district used
    assert captured["days"] == 5
    assert payload["location"]["name"] == "Tanore"
    assert payload["summary"]["total_rain_mm"] == 0.0


async def test_tool_explicit_location_overrides_default(monkeypatch):
    captured = {}

    async def fake_geocode(name, district=None, client=None):
        captured["name"] = name
        captured["district"] = district
        return {
            "name": name,
            "latitude": 24.7,
            "longitude": 88.7,
            "admin1": "",
            "admin2": "",
            "geocode_source": "open-meteo-geocoding",
        }

    async def fake_forecast(lat, lon, days, client=None):
        return {
            "source": "Open-Meteo forecast API",
            "fetched_at": "x",
            "request_params": {},
            "timezone": "Asia/Dhaka",
            "days": [],
            "summary": {},
            "note": "",
        }

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)
    monkeypatch.setattr(weather_mod, "fetch_forecast", fake_forecast)

    tool_obj = build_weather_tool(_fake_user())
    await tool_obj.ainvoke({"location": "Manda", "days": 7})
    assert captured["name"] == "Manda"
    # Explicit location -> registered district must NOT bias the geocoder.
    assert captured["district"] is None


async def test_tool_failure_returns_unavailable_not_invented(monkeypatch):
    async def fake_geocode(name, district=None, client=None):
        raise weather_mod.WeatherError("network down")

    monkeypatch.setattr(weather_mod, "geocode_place", fake_geocode)

    tool_obj = build_weather_tool(_fake_user())
    raw = await tool_obj.ainvoke({"location": "", "days": 7})
    assert raw.startswith("WEATHER_UNAVAILABLE")
    assert "network down" in raw
