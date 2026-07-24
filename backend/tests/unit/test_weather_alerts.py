"""Gold-number tests for the deterministic proactive weather-alert engine."""
from __future__ import annotations

from datetime import date

from app.engines.weather_alerts import (
    GENERIC_COLD_C,
    GENERIC_HEAT_C,
    GENERIC_HEAVY_RAIN_MM,
    MAX_SMS_CHARS,
    evaluate_generic_alerts,
    evaluate_plan_alerts,
    render_sms,
)

TODAY = date(2026, 11, 10)


def _days(spec):
    """spec: {iso_date: rain_mm or (rain, tmax, tmin)}"""
    out = []
    for iso, value in spec.items():
        if isinstance(value, tuple):
            rain, tmax, tmin = value
        else:
            rain, tmax, tmin = value, 25.0, 15.0
        out.append(
            {"date": iso, "rain_mm": rain, "t_max_c": tmax, "t_min_c": tmin}
        )
    return out


def test_heavy_rain_on_fertilizer_day_yields_exact_delay_decision():
    # Wheat BAMIS threshold is 50 mm/day. 55 mm on the top-dress day; the
    # first day back under the 5 mm floor is Nov 16 -> a 4-day delay.
    events = [
        {"date": "2026-11-12", "category": "fertilizer", "title": "Urea top-dress"}
    ]
    forecast = _days(
        {
            "2026-11-10": 0,
            "2026-11-11": 2,
            "2026-11-12": 55,
            "2026-11-13": 30,
            "2026-11-14": 12,
            "2026-11-15": 8,
            "2026-11-16": 1,
        }
    )
    decisions = evaluate_plan_alerts(events, forecast, "Wheat", TODAY)
    assert len(decisions) == 1
    d = decisions[0]
    assert d.alert_type == "delay_fertilizer"
    assert d.event_date == date(2026, 11, 12)
    assert d.trigger_date == date(2026, 11, 12)
    assert d.suggested_date == date(2026, 11, 16)
    assert d.delay_days == 4
    assert d.rain_mm == 55
    assert d.threshold == 50
    assert "BAMIS Wheat" in d.threshold_source


def test_rain_on_neighbour_day_also_triggers_and_potato_threshold_is_lower():
    # Potato's BAMIS threshold is 25 mm/day; 30 mm the day BEFORE the
    # side-dressing still triggers (runoff window is date +/- 1).
    events = [{"date": "2026-11-13", "category": "fertilizer", "title": "Side-dress"}]
    forecast = _days(
        {"2026-11-12": 30, "2026-11-13": 0, "2026-11-14": 0}
    )
    decisions = evaluate_plan_alerts(events, forecast, "Potato", TODAY)
    assert len(decisions) == 1
    assert decisions[0].trigger_date == date(2026, 11, 12)
    assert decisions[0].suggested_date == date(2026, 11, 14)


def test_no_dry_day_in_window_leaves_suggested_date_open():
    events = [{"date": "2026-11-12", "category": "fertilizer", "title": "Top-dress"}]
    forecast = _days({"2026-11-12": 60, "2026-11-13": 40, "2026-11-14": 25})
    decisions = evaluate_plan_alerts(events, forecast, "Wheat", TODAY)
    assert len(decisions) == 1
    assert decisions[0].suggested_date is None
    assert decisions[0].delay_days is None
    text = render_sms(decisions[0], "Paba", "Wheat")
    assert "re-check" in text.lower()


def test_below_threshold_rain_and_past_or_far_events_are_silent():
    events = [
        {"date": "2026-11-12", "category": "fertilizer", "title": "Top-dress"},
        {"date": "2026-11-01", "category": "fertilizer", "title": "Past basal"},
        {"date": "2027-01-20", "category": "fertilizer", "title": "Beyond window"},
    ]
    forecast = _days({"2026-11-11": 10, "2026-11-12": 49, "2026-11-13": 3})
    assert evaluate_plan_alerts(events, forecast, "Wheat", TODAY) == []


def test_rainy_irrigation_checkpoint_becomes_skip_advice():
    events = [
        {"date": "2026-11-12", "category": "irrigation", "title": "First irrigation"}
    ]
    forecast = _days({"2026-11-12": 15})
    decisions = evaluate_plan_alerts(events, forecast, "Wheat", TODAY)
    assert len(decisions) == 1
    assert decisions[0].alert_type == "skip_irrigation"
    assert decisions[0].rain_mm == 15


def test_missing_forecast_values_never_trigger():
    events = [{"date": "2026-11-12", "category": "fertilizer", "title": "Top-dress"}]
    forecast = [{"date": "2026-11-12", "rain_mm": None}]
    assert evaluate_plan_alerts(events, forecast, "Wheat", TODAY) == []
    assert evaluate_generic_alerts(forecast, TODAY) == []


def test_generic_alerts_fire_once_per_type_inside_three_day_horizon():
    forecast = _days(
        {
            "2026-11-10": (60, 41, 6),   # trips all three
            "2026-11-11": (70, 42, 5),   # duplicates suppressed
            "2026-11-15": (90, 45, 2),   # beyond the 3-day horizon
        }
    )
    decisions = evaluate_generic_alerts(forecast, TODAY)
    types = [d.alert_type for d in decisions]
    assert sorted(types) == ["cold_stress", "heat_stress", "heavy_rain_generic"]
    by_type = {d.alert_type: d for d in decisions}
    assert by_type["heavy_rain_generic"].rain_mm == 60
    assert by_type["heavy_rain_generic"].threshold == GENERIC_HEAVY_RAIN_MM
    assert by_type["heat_stress"].temp_c == 41
    assert by_type["heat_stress"].threshold == GENERIC_HEAT_C
    assert by_type["cold_stress"].temp_c == 6
    assert by_type["cold_stress"].threshold == GENERIC_COLD_C


def test_render_sms_is_specific_and_capped():
    events = [{"date": "2026-11-12", "category": "fertilizer", "title": "Top-dress"}]
    forecast = _days(
        {"2026-11-12": 55, "2026-11-13": 30, "2026-11-14": 12, "2026-11-15": 8, "2026-11-16": 1}
    )
    decision = evaluate_plan_alerts(events, forecast, "Wheat", TODAY)[0]
    text = render_sms(decision, "Paba", "Wheat")
    assert text == (
        "AgriSense: Heavy rain (~55mm) expected 12 Nov at Paba. Delay your "
        "Wheat fertilizer application from 12 Nov to 16 Nov (4 days) to cut "
        "runoff loss."
    )
    assert len(text) <= MAX_SMS_CHARS
