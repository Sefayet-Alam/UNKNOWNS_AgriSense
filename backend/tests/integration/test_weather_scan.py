"""Integration tests for the proactive weather scan (Tier 1).

All external I/O is faked: Open-Meteo via a monkeypatched fetch_forecast,
SMS via the default dry-run mode (zero HTTP). Sessions run against the
isolated test database through the injected session factory.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.agent.tools import _get_or_create_active_farm, build_alerts_tool
from app.models import SeasonPlan, User, WeatherAlert
from app.services import weather_scan as scan_mod

TODAY = date(2026, 11, 10)


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


def _calendar(events):
    return {
        "crop_name": "Wheat",
        "planting_date": "2026-11-01",
        "harvest_date": "2027-02-28",
        "duration_days": 119,
        "events": events,
        "warnings": [],
    }


async def _seed_plan(db_session, farm, events):
    plan = SeasonPlan(
        farm_id=farm.id,
        crop_name="Wheat",
        crop_id=3,
        status="ok",
        planting_date=date(2026, 11, 1),
        harvest_date=date(2027, 2, 28),
        duration_days=119,
        selected_variety={"variety_id": 1001, "name": "BARI Gom 33"},
        calendar=_calendar(events),
        financial_projection=None,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


def _forecast(days):
    return {"source": "Open-Meteo forecast API", "days": days, "summary": {}}


HEAVY_RAIN_DAYS = [
    {"date": "2026-11-10", "rain_mm": 0, "t_max_c": 26, "t_min_c": 14},
    {"date": "2026-11-11", "rain_mm": 2, "t_max_c": 26, "t_min_c": 14},
    {"date": "2026-11-12", "rain_mm": 55, "t_max_c": 24, "t_min_c": 13},
    {"date": "2026-11-13", "rain_mm": 30, "t_max_c": 24, "t_min_c": 13},
    {"date": "2026-11-14", "rain_mm": 12, "t_max_c": 25, "t_min_c": 14},
    {"date": "2026-11-15", "rain_mm": 8, "t_max_c": 25, "t_min_c": 14},
    {"date": "2026-11-16", "rain_mm": 1, "t_max_c": 26, "t_min_c": 15},
]

FERTILIZER_EVENT = {
    "date": "2026-11-12",
    "category": "fertilizer",
    "title": "Urea top-dress",
    "action": "Apply remaining nitrogen",
}


@pytest.mark.asyncio
async def test_plan_aware_scan_creates_delay_alert_with_exact_sms(
    auth_client, db_session, session_factory, monkeypatch
):
    user, farm = await _complete_farm(db_session)
    plan = await _seed_plan(db_session, farm, [FERTILIZER_EVENT])
    calls = []

    async def fake_forecast(lat, lon, days, **kwargs):
        calls.append((lat, lon, days))
        return _forecast(HEAVY_RAIN_DAYS)

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", fake_forecast)
    report = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )

    assert report["farms_scanned"] == 1
    assert report["locations_fetched"] == 1
    assert report["alerts_created"] == 1
    assert report["sms"]["dry_run"] == 1
    assert len(calls) == 1

    alert = (
        await db_session.execute(select(WeatherAlert))
    ).scalar_one()
    assert alert.farm_id == farm.id
    assert alert.user_id == user.id
    assert alert.season_plan_id == plan.id
    assert alert.alert_type == "delay_fertilizer"
    assert alert.event_date == date(2026, 11, 12)
    assert alert.trigger_date == date(2026, 11, 12)
    assert alert.sms_status == "dry_run"
    assert "Delay your Wheat fertilizer application" in alert.message
    assert "12 Nov to 16 Nov (4 days)" in alert.message


@pytest.mark.asyncio
async def test_second_scan_is_idempotent(
    auth_client, db_session, session_factory, monkeypatch
):
    _user, farm = await _complete_farm(db_session)
    await _seed_plan(db_session, farm, [FERTILIZER_EVENT])

    async def fake_forecast(*args, **kwargs):
        return _forecast(HEAVY_RAIN_DAYS)

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", fake_forecast)
    first = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )
    second = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )

    assert first["alerts_created"] == 1
    assert second["alerts_created"] == 0
    assert second["alerts_deduplicated"] == 1
    rows = (await db_session.execute(select(WeatherAlert))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_farm_without_plan_gets_generic_severe_weather_alert(
    auth_client, db_session, session_factory, monkeypatch
):
    _user, _farm = await _complete_farm(db_session)

    async def fake_forecast(*args, **kwargs):
        return _forecast(HEAVY_RAIN_DAYS[:3])  # 55mm within 3-day horizon

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", fake_forecast)
    report = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )

    assert report["alerts_created"] == 1
    alert = (await db_session.execute(select(WeatherAlert))).scalar_one()
    assert alert.alert_type == "heavy_rain_generic"
    assert alert.season_plan_id is None
    assert "Secure drainage" in alert.message


@pytest.mark.asyncio
async def test_incomplete_profile_is_skipped_without_any_weather_call(
    auth_client, db_session, session_factory, monkeypatch
):
    # Create the farm from the registration address but leave the six
    # mandatory fields unfilled — the scan must skip it entirely.
    user = (await db_session.execute(select(User))).scalar_one()
    await _get_or_create_active_farm(db_session, user)

    async def forbidden(*args, **kwargs):
        pytest.fail("no forecast call for incomplete profiles")

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", forbidden)
    report = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )
    assert report["farms_skipped_incomplete"] >= 1
    assert report["farms_scanned"] == 0
    assert report["alerts_created"] == 0


@pytest.mark.asyncio
async def test_weather_outage_skips_location_and_reports_it(
    auth_client, db_session, session_factory, monkeypatch
):
    _user, farm = await _complete_farm(db_session)
    await _seed_plan(db_session, farm, [FERTILIZER_EVENT])

    async def broken(*args, **kwargs):
        raise scan_mod.weather_mod.WeatherError("open-meteo down")

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", broken)
    report = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )
    assert report["locations_weather_unavailable"] == 1
    assert report["alerts_created"] == 0
    rows = (await db_session.execute(select(WeatherAlert))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_quiet_forecast_creates_no_alerts(
    auth_client, db_session, session_factory, monkeypatch
):
    _user, farm = await _complete_farm(db_session)
    await _seed_plan(db_session, farm, [FERTILIZER_EVENT])

    async def calm(*args, **kwargs):
        return _forecast(
            [
                {"date": "2026-11-12", "rain_mm": 3, "t_max_c": 27, "t_min_c": 15}
            ]
        )

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", calm)
    report = await scan_mod.run_weather_scan(
        session_factory=session_factory, today=TODAY
    )
    assert report["alerts_created"] == 0


# --------------------------------------------------------------------------- #
# Agent tool + HTTP endpoints
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_agent_tool_relays_stored_alerts_exactly(
    auth_client, db_session, monkeypatch
):
    import json as json_mod

    user, farm = await _complete_farm(db_session)
    db_session.add(
        WeatherAlert(
            farm_id=farm.id,
            user_id=user.id,
            season_plan_id=None,
            alert_type="delay_fertilizer",
            event_date=date(2026, 11, 12),
            trigger_date=date(2026, 11, 12),
            message="AgriSense: test alert message",
            sms_status="dry_run",
            sms_response=None,
        )
    )
    await db_session.commit()

    payload = json_mod.loads(
        await build_alerts_tool(user).ainvoke({"days_back": 7})
    )
    assert payload["status"] == "ok"
    assert payload["alerts"][0]["alert_type"] == "delay_fertilizer"
    assert payload["alerts"][0]["message"] == "AgriSense: test alert message"
    assert payload["alerts"][0]["sms_status"] == "dry_run"

    empty = json_mod.loads(
        await build_alerts_tool(user).ainvoke({"days_back": 1})
    )
    assert empty["status"] == "ok"  # created moments ago — still inside 1 day


@pytest.mark.asyncio
async def test_scan_now_endpoint_runs_a_pass_and_returns_the_report(
    auth_client, db_session, monkeypatch
):
    user = (await db_session.execute(select(User))).scalar_one()
    await _get_or_create_active_farm(db_session, user)

    async def forbidden(*args, **kwargs):
        pytest.fail("incomplete profile must not fetch weather")

    monkeypatch.setattr(scan_mod.weather_mod, "fetch_forecast", forbidden)
    resp = await auth_client.post("/api/alerts/scan-now")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["report"]["farms_skipped_incomplete"] >= 1


@pytest.mark.asyncio
async def test_alert_history_endpoint_returns_user_scoped_rows(
    auth_client, db_session
):
    user, farm = await _complete_farm(db_session)
    db_session.add(
        WeatherAlert(
            farm_id=farm.id,
            user_id=user.id,
            alert_type="heat_stress",
            event_date=None,
            trigger_date=date(2026, 11, 11),
            message="AgriSense: heat warning",
            sms_status="dry_run",
        )
    )
    await db_session.commit()

    resp = await auth_client.get("/api/alerts")
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["alert_type"] == "heat_stress"
    assert results[0]["message"] == "AgriSense: heat warning"
