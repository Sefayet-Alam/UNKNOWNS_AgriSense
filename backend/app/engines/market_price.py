"""Deterministic market-price analysis + sell/store/wait advice (Tier 2).

Reads a seeded historical price series (grounded in typical Bangladesh DAM/TCB
levels) and computes, for a crop: the current price, historical min/max/average,
a recent trend (linear fit → BDT/kg per month and %/month), volatility, and a
**sell-now / store / wait** recommendation whose reasoning is fully numeric —
the recent trend rate is weighed against the crop's storage cost and
perishability. The engine decides; the LLM only explains. Prices are labelled
seeded snapshot values, not a live quote.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "market_prices.json"

RISING_PCT = 1.5   # %/month above which the trend is "rising"
STRONG_PCT = 3.0   # %/month for a confident "store" vs a cautious "wait"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def supported_crops() -> list[str]:
    return sorted(_catalog()["crops"])


def resolve_crop(name: str) -> Optional[str]:
    """Map a crop name/alias (any language) to a catalog key, or None."""
    q = str(name or "").strip().lower()
    if not q:
        return None
    crops = _catalog()["crops"]
    if q in crops:
        return q
    for key, meta in crops.items():
        if q == key or q in [a.lower() for a in meta.get("aliases", [])]:
            return key
    # loose contains match as a fallback
    for key, meta in crops.items():
        if q in key or any(q in a.lower() for a in meta.get("aliases", [])):
            return key
    return None


def _linear_slope_per_day(points: list[tuple[int, float]]) -> float:
    """OLS slope (price per day) over (day_offset, price) points."""
    n = len(points)
    if n < 2:
        return 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = sum(xs) / n
    my = sum(ys) / n
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return 0.0
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / var


def analyze_series(series: list[dict], *, recent_points: int = 5) -> dict:
    """Current price, history stats, recent trend and volatility."""
    prices = [float(p["price"]) for p in series]
    dates = [date.fromisoformat(p["date"]) for p in series]
    current = prices[-1]

    recent = series[-recent_points:] if len(series) >= 2 else series
    base = date.fromisoformat(recent[0]["date"])
    pts = [((date.fromisoformat(p["date"]) - base).days, float(p["price"])) for p in recent]
    slope_day = _linear_slope_per_day(pts)
    per_month = slope_day * 30.0
    monthly_pct = (per_month / current * 100.0) if current else 0.0

    if monthly_pct > RISING_PCT:
        trend = "rising"
    elif monthly_pct < -RISING_PCT:
        trend = "falling"
    else:
        trend = "stable"

    mean = sum(prices) / len(prices)
    volatility_pct = (statistics.pstdev(prices) / mean * 100.0) if mean else 0.0

    return {
        "current_price": round(current, 2),
        "current_date": dates[-1].isoformat(),
        "history": {
            "start_date": dates[0].isoformat(),
            "end_date": dates[-1].isoformat(),
            "min": round(min(prices), 2),
            "max": round(max(prices), 2),
            "average": round(mean, 2),
            "points": len(prices),
        },
        "trend": trend,
        "trend_bdt_per_kg_per_month": round(per_month, 2),
        "trend_pct_per_month": round(monthly_pct, 2),
        "volatility_pct": round(volatility_pct, 1),
    }


def recommend(meta: dict, analysis: dict) -> dict:
    """Sell-now / store / wait, with numeric reasoning."""
    storable = bool(meta.get("storable"))
    storage_cost = float(meta.get("storage_cost_bdt_per_kg_per_month", 0.0))
    gain = analysis["trend_bdt_per_kg_per_month"]
    pct = analysis["trend_pct_per_month"]
    net = round(gain - storage_cost, 2)

    if not storable:
        return {
            "action": "sell_now",
            "reason": (
                f"{meta['display']} is perishable and cannot be stored — sell now "
                "rather than risk spoilage."
            ),
            "net_monthly_benefit_bdt_per_kg": None,
            "storage_cost_bdt_per_kg_per_month": storage_cost,
        }
    if analysis["trend"] == "falling":
        return {
            "action": "sell_now",
            "reason": (
                f"Prices are falling about {abs(pct):.1f}%/month "
                f"({gain:+.2f} BDT/kg/month) — sell now before they drop further."
            ),
            "net_monthly_benefit_bdt_per_kg": net,
            "storage_cost_bdt_per_kg_per_month": storage_cost,
        }
    if analysis["trend"] == "rising" and net > 0:
        action = "store" if pct >= STRONG_PCT else "wait"
        horizon = "hold in storage" if action == "store" else "hold briefly and re-check"
        return {
            "action": action,
            "reason": (
                f"Prices are rising about {pct:.1f}%/month ({gain:+.2f} BDT/kg/month), "
                f"above the {storage_cost:.2f} BDT/kg/month storage cost — {horizon}; "
                f"net expected benefit ~{net:+.2f} BDT/kg/month."
            ),
            "net_monthly_benefit_bdt_per_kg": net,
            "storage_cost_bdt_per_kg_per_month": storage_cost,
        }
    # rising-but-uneconomic, or stable
    detail = (
        f"the ~{pct:.1f}%/month rise ({gain:+.2f} BDT/kg) does not cover the "
        f"{storage_cost:.2f} BDT/kg/month storage cost"
        if analysis["trend"] == "rising"
        else "prices are flat, so storage would only add cost"
    )
    return {
        "action": "sell_now",
        "reason": f"Sell now: {detail}.",
        "net_monthly_benefit_bdt_per_kg": net,
        "storage_cost_bdt_per_kg_per_month": storage_cost,
    }


def analyze_crop(crop_key: str) -> dict:
    """Full result for a resolved crop key: history + analysis + recommendation."""
    meta = _catalog()["crops"][crop_key]
    analysis = analyze_series(meta["series"])
    advice = recommend(meta, analysis)
    return {
        "crop": meta["display"],
        "unit": f"{_catalog()['currency']}/{_catalog()['unit']}",
        "perishable": bool(meta.get("perishable")),
        "storable": bool(meta.get("storable")),
        "shelf_life_months": meta.get("shelf_life_months"),
        "analysis": analysis,
        "recommendation": advice,
        "series": meta["series"],
        "provenance": (
            "Seeded historical snapshot grounded in typical Bangladesh DAM/TCB "
            f"levels (catalog {_catalog()['version']}); not a live quote. The "
            "sell/store/wait decision is deterministic from the trend vs storage cost."
        ),
    }
