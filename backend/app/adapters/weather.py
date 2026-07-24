"""Open-Meteo adapter: keyless live weather + place geocoding for Bangladesh.

Grounding rules (Tier 0 #2, PLAN.md):
- Only real API values are returned. On failure a ``WeatherError`` is raised —
  callers surface the failure honestly and must never invent forecast numbers.
- Forecast horizon is capped at 16 days (Open-Meteo maximum). Anything beyond
  is a product question (climate normals), not this adapter's job.
- Every result carries evidence metadata: source, fetched_at, request params,
  and whether the location came from the live geocoder or the bundled
  fallback centroids.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

log = logging.getLogger("agrisense.adapters.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

TIMEOUT_S = 10.0
RETRIES = 2  # total attempts per HTTP call
MAX_FORECAST_DAYS = 16
MAX_PAST_DAYS = 92  # Open-Meteo forecast endpoint serves up to 92 past days

# Offline fallback centroids for demo-critical places (approximate upazila /
# district centers). Used only when the live geocoder is unreachable or has no
# match — the result is labelled ``geocode_source: "bundled_fallback"``.
FALLBACK_CENTROIDS: dict[str, tuple[float, float]] = {
    "tanore": (24.588, 88.581),
    "godagari": (24.468, 88.331),
    "rajshahi": (24.374, 88.601),
    "manda": (24.723, 88.694),
    "naogaon": (24.792, 88.947),
    "chapai nawabganj": (24.596, 88.277),
    "natore": (24.412, 88.986),
    "dhaka": (23.777, 90.399),
}

DAILY_VARS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "et0_fao_evapotranspiration",
    "wind_speed_10m_max",
]


class WeatherError(Exception):
    """Raised when live weather/geocoding could not be fetched."""


async def _get_json(
    url: str, params: dict, client: Optional[httpx.AsyncClient]
) -> dict:
    """GET with bounded retry; raises WeatherError on persistent failure."""
    owns_client = client is None
    cl = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        last_exc: Exception | None = None
        for attempt in range(RETRIES):
            try:
                resp = await cl.get(url, params=params)
                if resp.status_code >= 500:
                    raise WeatherError(f"upstream {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, WeatherError, ValueError) as exc:
                last_exc = exc
                log.warning(
                    "GET %s failed (attempt %d/%d): %s", url, attempt + 1, RETRIES, exc
                )
                if attempt + 1 < RETRIES:
                    await asyncio.sleep(0.4)
        log.error("GET %s exhausted retries: %s", url, last_exc)
        raise WeatherError(f"request to {url} failed: {last_exc}")
    finally:
        if owns_client:
            await cl.aclose()


async def geocode_place(
    name: str,
    district: Optional[str] = None,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Resolve a Bangladesh place name to coordinates.

    Tries the live Open-Meteo geocoder first (filtering to Bangladesh and, when
    given, preferring matches whose admin fields mention ``district``). Falls
    back to the bundled centroid table. Raises WeatherError if neither works.
    """
    query = (name or "").strip()
    if not query:
        raise WeatherError("empty location name")

    try:
        data = await _get_json(
            GEOCODE_URL,
            {"name": query, "count": 5, "language": "en", "format": "json"},
            client,
        )
        results = [
            r
            for r in data.get("results") or []
            if r.get("country_code", "").upper() == "BD"
        ]
        if results:
            chosen = results[0]
            if district:
                d = district.strip().lower()
                for r in results:
                    admin_blob = " ".join(
                        str(r.get(k, "")) for k in ("admin1", "admin2", "admin3")
                    ).lower()
                    if d and d in admin_blob:
                        chosen = r
                        break
            return {
                "name": chosen.get("name", query),
                "latitude": chosen["latitude"],
                "longitude": chosen["longitude"],
                "admin1": chosen.get("admin1", ""),
                "admin2": chosen.get("admin2", ""),
                "geocode_source": "open-meteo-geocoding",
            }
    except WeatherError:
        pass  # fall through to bundled centroids

    key = query.lower()
    if key in FALLBACK_CENTROIDS:
        lat, lon = FALLBACK_CENTROIDS[key]
        log.info("geocode fallback: %r -> bundled centroid (%s, %s)", query, lat, lon)
        return {
            "name": query,
            "latitude": lat,
            "longitude": lon,
            "admin1": "",
            "admin2": "",
            "geocode_source": "bundled_fallback",
        }
    raise WeatherError(f"could not geocode location: {query!r}")


def _round_or_none(value: Any, ndigits: int = 1):
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


async def fetch_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
    *,
    past_days: int = 0,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Fetch normalized daily weather from Open-Meteo.

    ``days`` is the forecast horizon (0-16; 0 = no forecast rows).
    ``past_days`` (0-92) prepends OBSERVED recent days to the same series —
    Open-Meteo serves both from one endpoint. Past rows are marked
    ``kind: "past"`` and summarized separately so callers can cite "rain in
    the last week" as recorded values, not forecasts.

    Returns a dict with per-day rows + computed summaries + evidence
    metadata. Raises WeatherError on failure.
    """
    past_days = max(0, min(int(past_days), MAX_PAST_DAYS))
    # days=0 is only meaningful when past rows were requested.
    floor = 0 if past_days > 0 else 1
    days = max(floor, min(int(days), MAX_FORECAST_DAYS))
    params = {
        "latitude": round(float(latitude), 4),
        "longitude": round(float(longitude), 4),
        "daily": ",".join(DAILY_VARS),
        "forecast_days": days,
        "timezone": "Asia/Dhaka",
    }
    if past_days:
        params["past_days"] = past_days
    raw = await _get_json(FORECAST_URL, params, client)

    daily = raw.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        raise WeatherError("forecast response contained no daily data")

    def col(key: str) -> list:
        vals = daily.get(key) or []
        return vals + [None] * (len(dates) - len(vals))

    t_max = col("temperature_2m_max")
    t_min = col("temperature_2m_min")
    rain = col("precipitation_sum")
    rain_prob = col("precipitation_probability_max")
    et0 = col("et0_fao_evapotranspiration")
    wind = col("wind_speed_10m_max")

    rows = []
    for i, date in enumerate(dates):
        row = {
            "date": date,
            "t_min_c": _round_or_none(t_min[i]),
            "t_max_c": _round_or_none(t_max[i]),
            "rain_mm": _round_or_none(rain[i]),
            "rain_prob_pct": _round_or_none(rain_prob[i], 0),
            "et0_mm": _round_or_none(et0[i]),
            "wind_max_kmh": _round_or_none(wind[i]),
        }
        if past_days:
            # The API returns exactly past_days rows before today, in order.
            row["kind"] = "past" if i < past_days else "forecast"
        rows.append(row)

    def _summarize(subset: list) -> dict:
        rain_vals = [
            (r["date"], r["rain_mm"]) for r in subset if r["rain_mm"] is not None
        ]
        rainy = [d for d, v in rain_vals if v >= 1.0]
        t_max_vals = [r["t_max_c"] for r in subset if r["t_max_c"] is not None]
        t_min_vals = [r["t_min_c"] for r in subset if r["t_min_c"] is not None]
        return {
            "total_rain_mm": round(sum(v for _, v in rain_vals), 1),
            "rainy_day_count": len(rainy),
            "first_rainy_date": rainy[0] if rainy else None,
            "max_temp_c": max(t_max_vals) if t_max_vals else None,
            "min_temp_c": min(t_min_vals) if t_min_vals else None,
        }

    forecast_rows = [r for r in rows if r.get("kind", "forecast") == "forecast"]
    past_rows = [r for r in rows if r.get("kind") == "past"]

    note = (
        "Model forecast values, not field measurements. Horizon is capped "
        f"at {MAX_FORECAST_DAYS} days — beyond that only climate patterns "
        "can be discussed, never specific daily forecasts."
    )
    result = {
        "source": "Open-Meteo forecast API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "request_params": params,
        "timezone": raw.get("timezone", "Asia/Dhaka"),
        "days": rows,
        "summary": {"forecast_days": len(forecast_rows), **_summarize(forecast_rows)},
        "note": note,
    }
    if past_rows:
        result["past_summary"] = {"past_days": len(past_rows), **_summarize(past_rows)}
        result["note"] = (
            "Rows marked kind=past are recorded recent weather (rain "
            "probability may be null there); rows marked kind=forecast are "
            "model predictions. " + note
        )
    return result
