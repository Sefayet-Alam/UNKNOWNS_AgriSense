"""Proactive weather scan: the agent watches the forecast on its own.

Runs daily (lifespan loop in ``main.py``) and on demand
(``POST /api/alerts/scan-now``). For every farm with a complete six-field
profile it fetches ONE Open-Meteo forecast per distinct location (union
centroids rounded to ~1 km dedupe into a single call — "one call per
upazila"), evaluates the deterministic alert engine against the farm's most
recent saved season plan (plan-aware advice) or generic severe-weather
thresholds (no plan yet), dedups against the ``weather_alerts`` log, sends
the SMS (dry-run aware) and records every decision.

Failure discipline: a weather outage skips that location (counted in the
report, never invented); an SMS failure is recorded on the alert row; a
crash in one farm never aborts the rest of the scan.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..adapters import sms as sms_mod
from ..adapters import weather as weather_mod
from ..agent.tools import _missing_slots
from .. import database as db_module
from .. import geo as geo_mod
from ..engines import weather_alerts as alerts_engine
from ..models import Farm, SeasonPlan, User, WeatherAlert

log = logging.getLogger("agrisense.services.weather_scan")

FORECAST_DAYS = 7


def _farm_coords(farm: Farm) -> Optional[tuple[float, float]]:
    if farm.latitude is not None and farm.longitude is not None:
        return farm.latitude, farm.longitude
    resolved = geo_mod.resolve_coords(
        union_code=farm.union_geocode or "",
        upazila_code=farm.upazila_code or "",
        district_code=farm.district_code or "",
    )
    if resolved:
        return resolved["lat"], resolved["lon"]
    return None


async def run_weather_scan(
    *,
    session_factory=None,
    today: Optional[date] = None,
) -> dict:
    """One full scan pass. Returns an inspectable report dict."""
    # Resolved at call time so the test suite's per-test session factory
    # (patched onto the database module) is honored.
    factory = session_factory or db_module.AsyncSessionLocal
    today = today or datetime.now(ZoneInfo("Asia/Dhaka")).date()
    report = {
        "today": today.isoformat(),
        "farms_scanned": 0,
        "farms_skipped_incomplete": 0,
        "farms_skipped_no_coords": 0,
        "locations_fetched": 0,
        "locations_weather_unavailable": 0,
        "alerts_created": 0,
        "alerts_deduplicated": 0,
        "sms": {"sent": 0, "dry_run": 0, "failed": 0},
    }

    async with factory() as session:
        rows = (
            await session.execute(
                select(Farm, User).join(User, Farm.user_id == User.id)
            )
        ).all()

    # Group complete farms by rounded coordinates -> one forecast per spot.
    groups: dict[tuple[float, float], list[tuple[Farm, User]]] = {}
    for farm, user in rows:
        if _missing_slots(farm):
            report["farms_skipped_incomplete"] += 1
            continue
        coords = _farm_coords(farm)
        if coords is None:
            report["farms_skipped_no_coords"] += 1
            continue
        key = (round(coords[0], 2), round(coords[1], 2))
        groups.setdefault(key, []).append((farm, user))

    for (lat, lon), members in groups.items():
        try:
            forecast = await weather_mod.fetch_forecast(lat, lon, FORECAST_DAYS)
        except weather_mod.WeatherError as exc:
            log.warning("weather unavailable for (%s, %s): %s", lat, lon, exc)
            report["locations_weather_unavailable"] += 1
            continue
        report["locations_fetched"] += 1
        forecast_days = forecast.get("days") or []

        for farm, user in members:
            report["farms_scanned"] += 1
            try:
                await _scan_farm(
                    factory, farm, user, forecast_days, today, report
                )
            except Exception as exc:  # one farm must never abort the scan
                log.exception("scan failed for farm %s: %s", farm.id, exc)

    log.info("weather scan report: %s", report)
    return report


async def _scan_farm(
    factory, farm: Farm, user: User, forecast_days: list[dict], today: date, report: dict
) -> None:
    async with factory() as session:
        plan = (
            await session.execute(
                select(SeasonPlan)
                .where(
                    SeasonPlan.farm_id == farm.id,
                    SeasonPlan.harvest_date >= today,
                )
                .order_by(SeasonPlan.created_at.desc(), SeasonPlan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    if plan is not None:
        decisions = alerts_engine.evaluate_plan_alerts(
            (plan.calendar or {}).get("events") or [],
            forecast_days,
            plan.crop_name,
            today,
        )
        crop_name = plan.crop_name
        plan_id = plan.id
    else:
        decisions = alerts_engine.evaluate_generic_alerts(forecast_days, today)
        crop_name = ""
        plan_id = None

    farm_label = farm.union_name or farm.upazila_name or farm.district_name
    for decision in decisions:
        async with factory() as session:
            duplicate = (
                await session.execute(
                    select(WeatherAlert.id)
                    .where(
                        WeatherAlert.farm_id == farm.id,
                        WeatherAlert.alert_type == decision.alert_type,
                        WeatherAlert.event_date == decision.event_date,
                        WeatherAlert.trigger_date == decision.trigger_date,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                report["alerts_deduplicated"] += 1
                continue

            message = alerts_engine.render_sms(decision, farm_label, crop_name)
            try:
                sms_result = await sms_mod.send_sms(user.phone, message)
            except sms_mod.SmsError as exc:
                sms_result = {"status": "failed", "response": {"error": str(exc)}}
            report["sms"][sms_result["status"]] = (
                report["sms"].get(sms_result["status"], 0) + 1
            )

            session.add(
                WeatherAlert(
                    farm_id=farm.id,
                    user_id=user.id,
                    season_plan_id=plan_id,
                    alert_type=decision.alert_type,
                    event_date=decision.event_date,
                    trigger_date=decision.trigger_date,
                    message=message,
                    sms_status=sms_result["status"],
                    sms_response=sms_result.get("response"),
                )
            )
            await session.commit()
            report["alerts_created"] += 1
