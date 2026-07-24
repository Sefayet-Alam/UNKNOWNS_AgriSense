"""Deterministic proactive weather-alert decisions (Tier 1).

Pure functions, no I/O. The scan job feeds a saved season-plan calendar (or
nothing) plus a live Open-Meteo forecast; this module decides which
advisories are warranted and renders the exact SMS text. The LLM is never in
this path — same rule as every other engine: deterministic code computes,
numbers are traceable to the stored plan + the forecast.

Threshold provenance:
- Plan-aware rain thresholds come from the crop's BAMIS ``weather_warning``
  profile in ``season_planner.CROP_PLANS`` (e.g. wheat 50 mm/day, potato
  25 mm/day) — never invented here.
- Generic (no-plan) thresholds are conservative severe-weather constants,
  labelled below.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .season_planner import CROP_PLANS, canonical_crop_name

# A day this wet is not suitable for fertilizer application; the first
# following day BELOW this floor becomes the suggested new date.
LIGHT_RAIN_FLOOR_MM = 5.0
# Rain at/above this on an irrigation checkpoint day makes irrigation
# unnecessary (typical effective-rainfall rule of thumb).
SKIP_IRRIGATION_RAIN_MM = 10.0

# Generic severe-weather constants (no plan needed). Conservative values:
# 50 mm/day matches the most common BAMIS crop rain warning; 40°C / 8°C are
# broadly damaging for Rabi crops regardless of stage.
GENERIC_HEAVY_RAIN_MM = 50.0
GENERIC_HEAT_C = 40.0
GENERIC_COLD_C = 8.0
GENERIC_HORIZON_DAYS = 3


@dataclass
class AlertDecision:
    alert_type: str  # delay_fertilizer | skip_irrigation | heavy_rain_generic | heat_stress | cold_stress
    trigger_date: date  # forecast day that tripped the threshold
    event_date: Optional[date] = None  # affected plan event (None = generic)
    suggested_date: Optional[date] = None  # new date for delayed events
    delay_days: Optional[int] = None
    rain_mm: Optional[float] = None
    temp_c: Optional[float] = None
    threshold: Optional[float] = None
    threshold_source: str = ""
    event_title: str = ""


def _rain_by_date(forecast_days: list[dict]) -> dict[date, float]:
    out: dict[date, float] = {}
    for day in forecast_days or []:
        try:
            d = date.fromisoformat(str(day.get("date")))
        except (TypeError, ValueError):
            continue
        rain = day.get("rain_mm")
        if rain is not None:
            out[d] = float(rain)
    return out


def evaluate_plan_alerts(
    calendar_events: list[dict],
    forecast_days: list[dict],
    crop_name: str,
    today: date,
) -> list[AlertDecision]:
    """Check upcoming fertilizer/irrigation events against the forecast.

    Only decides for events inside the forecast window. Missing forecast
    values never trigger (no invention on unknown weather).
    """
    canonical = canonical_crop_name(crop_name)
    warning = CROP_PLANS[canonical.lower()].get("weather_warning") or {}
    rain_threshold = float(warning.get("rain_mm_day", GENERIC_HEAVY_RAIN_MM))
    rain = _rain_by_date(forecast_days)
    if not rain:
        return []
    window_end = max(rain)

    decisions: list[AlertDecision] = []
    for event in calendar_events or []:
        try:
            event_date = date.fromisoformat(str(event.get("date")))
        except (TypeError, ValueError):
            continue
        if event_date < today or event_date > window_end:
            continue
        category = str(event.get("category") or "")
        title = str(event.get("title") or category)

        if category == "fertilizer":
            # Rain on the application day or either neighbour washes
            # nutrients out (runoff/leaching) — BAMIS threshold per crop.
            nearby = {
                d: rain[d]
                for d in (
                    event_date - timedelta(days=1),
                    event_date,
                    event_date + timedelta(days=1),
                )
                if d in rain
            }
            if not nearby or max(nearby.values()) < rain_threshold:
                continue
            trigger = max(nearby, key=lambda d: nearby[d])
            suggested = None
            probe = max(trigger, event_date) + timedelta(days=1)
            while probe <= window_end:
                if rain.get(probe, None) is not None and rain[probe] < LIGHT_RAIN_FLOOR_MM:
                    suggested = probe
                    break
                probe += timedelta(days=1)
            decisions.append(
                AlertDecision(
                    alert_type="delay_fertilizer",
                    trigger_date=trigger,
                    event_date=event_date,
                    suggested_date=suggested,
                    delay_days=(suggested - event_date).days if suggested else None,
                    rain_mm=nearby[trigger],
                    threshold=rain_threshold,
                    threshold_source=f"BAMIS {canonical} rain warning {rain_threshold:g} mm/day",
                    event_title=title,
                )
            )
        elif category == "irrigation":
            day_rain = rain.get(event_date)
            if day_rain is None or day_rain < SKIP_IRRIGATION_RAIN_MM:
                continue
            decisions.append(
                AlertDecision(
                    alert_type="skip_irrigation",
                    trigger_date=event_date,
                    event_date=event_date,
                    rain_mm=day_rain,
                    threshold=SKIP_IRRIGATION_RAIN_MM,
                    threshold_source=f"effective-rainfall rule {SKIP_IRRIGATION_RAIN_MM:g} mm",
                    event_title=title,
                )
            )
    return decisions


def evaluate_generic_alerts(
    forecast_days: list[dict], today: date
) -> list[AlertDecision]:
    """Severe-weather warnings needing no plan — first hit per type only."""
    horizon = today + timedelta(days=GENERIC_HORIZON_DAYS)
    decisions: list[AlertDecision] = []
    seen: set[str] = set()
    for day in forecast_days or []:
        try:
            d = date.fromisoformat(str(day.get("date")))
        except (TypeError, ValueError):
            continue
        if d < today or d > horizon:
            continue
        rain = day.get("rain_mm")
        t_max = day.get("t_max_c")
        t_min = day.get("t_min_c")
        if (
            "heavy_rain_generic" not in seen
            and rain is not None
            and float(rain) >= GENERIC_HEAVY_RAIN_MM
        ):
            seen.add("heavy_rain_generic")
            decisions.append(
                AlertDecision(
                    alert_type="heavy_rain_generic",
                    trigger_date=d,
                    rain_mm=float(rain),
                    threshold=GENERIC_HEAVY_RAIN_MM,
                    threshold_source=f"generic severe-rain constant {GENERIC_HEAVY_RAIN_MM:g} mm/day",
                )
            )
        if (
            "heat_stress" not in seen
            and t_max is not None
            and float(t_max) >= GENERIC_HEAT_C
        ):
            seen.add("heat_stress")
            decisions.append(
                AlertDecision(
                    alert_type="heat_stress",
                    trigger_date=d,
                    temp_c=float(t_max),
                    threshold=GENERIC_HEAT_C,
                    threshold_source=f"generic heat-stress constant {GENERIC_HEAT_C:g} C",
                )
            )
        if (
            "cold_stress" not in seen
            and t_min is not None
            and float(t_min) <= GENERIC_COLD_C
        ):
            seen.add("cold_stress")
            decisions.append(
                AlertDecision(
                    alert_type="cold_stress",
                    trigger_date=d,
                    temp_c=float(t_min),
                    threshold=GENERIC_COLD_C,
                    threshold_source=f"generic cold-stress constant {GENERIC_COLD_C:g} C",
                )
            )
    return decisions


def _fmt(d: Optional[date]) -> str:
    return d.strftime("%d %b") if d else "?"


MAX_SMS_CHARS = 300


def render_sms(decision: AlertDecision, farm_label: str, crop_name: str = "") -> str:
    """Fixed English templates; every number comes from the decision."""
    where = farm_label or "your farm"
    crop = crop_name or "your crop"
    t = decision.alert_type
    if t == "delay_fertilizer":
        if decision.suggested_date:
            text = (
                f"AgriSense: Heavy rain (~{decision.rain_mm:.0f}mm) expected "
                f"{_fmt(decision.trigger_date)} at {where}. Delay your {crop} "
                f"fertilizer application from {_fmt(decision.event_date)} to "
                f"{_fmt(decision.suggested_date)} ({decision.delay_days} days) "
                f"to cut runoff loss."
            )
        else:
            text = (
                f"AgriSense: Heavy rain (~{decision.rain_mm:.0f}mm) expected "
                f"{_fmt(decision.trigger_date)} at {where}. Postpone your {crop} "
                f"fertilizer application of {_fmt(decision.event_date)} and "
                f"re-check the forecast after {_fmt(decision.trigger_date)}."
            )
    elif t == "skip_irrigation":
        text = (
            f"AgriSense: ~{decision.rain_mm:.0f}mm rain expected "
            f"{_fmt(decision.event_date)} at {where}. Skip the planned {crop} "
            f"irrigation that day; the rain should cover it."
        )
    elif t == "heavy_rain_generic":
        text = (
            f"AgriSense: Heavy rain (~{decision.rain_mm:.0f}mm) expected "
            f"{_fmt(decision.trigger_date)} at {where}. Secure drainage and "
            f"avoid fertilizer or pesticide application that day."
        )
    elif t == "heat_stress":
        text = (
            f"AgriSense: High heat (~{decision.temp_c:.0f}C) expected "
            f"{_fmt(decision.trigger_date)} at {where}. Irrigate early morning "
            f"or evening and watch crops for heat stress."
        )
    elif t == "cold_stress":
        text = (
            f"AgriSense: Cold spell (~{decision.temp_c:.0f}C) expected "
            f"{_fmt(decision.trigger_date)} at {where}. Protect seedbeds and "
            f"delay sowing/transplanting if possible."
        )
    else:  # defensive: unknown type still yields a safe generic message
        text = (
            f"AgriSense: Adverse weather expected {_fmt(decision.trigger_date)} "
            f"at {where}. Check the forecast before field work."
        )
    return text[:MAX_SMS_CHARS]
