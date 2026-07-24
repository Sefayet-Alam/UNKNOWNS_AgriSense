"""Deterministic crop ranking for the PDF Tier-0 recommendation contract.

The engine contains no network or LLM calls.  It combines already-retrieved
official suitability, live weather, farm constraints and recorded local
rotation economics into inspectable scores.  The LLM may explain this output;
it must not replace the arithmetic.
"""
from __future__ import annotations

from typing import Any, Optional


# Qualitative water demand and conservative weather limits for the focused
# Bangladesh Rabi path.  These are agronomic profile metadata, not irrigation
# quantities.  Farmer-facing quantities are produced only by later scheduler
# tools.  Source references are carried into every candidate.
CROP_TRAITS: dict[str, dict[str, Any]] = {
    "boro dhan": {"water": "high", "max_temp_c": 35, "heavy_rain_mm": 60},
    "wheat": {"water": "medium", "max_temp_c": 32, "heavy_rain_mm": 40},
    "maize": {"water": "medium", "max_temp_c": 35, "heavy_rain_mm": 50},
    "mustard": {"water": "low", "max_temp_c": 32, "heavy_rain_mm": 35},
    "potato": {"water": "medium", "max_temp_c": 30, "heavy_rain_mm": 35},
    "lentil": {"water": "low", "max_temp_c": 32, "heavy_rain_mm": 35},
    "tomato": {"water": "medium", "max_temp_c": 32, "heavy_rain_mm": 35},
    "onion": {"water": "medium", "max_temp_c": 32, "heavy_rain_mm": 35},
    "garlic": {"water": "medium", "max_temp_c": 32, "heavy_rain_mm": 35},
    "brinjal": {"water": "medium", "max_temp_c": 35, "heavy_rain_mm": 40},
}

TRAITS_SOURCE = {
    "source": "BARC Fertilizer Recommendation Guide 2024 + BAMIS crop calendars",
    "usage": "qualitative water-demand and weather-risk classification",
    "note": "No irrigation quantity is inferred from these qualitative classes.",
}

_SUITABILITY_POINTS = {
    "VS": 100.0,
    "S": 80.0,
    "MS": 60.0,
    "MNS": 35.0,
    "NS": 0.0,
    "N": 0.0,
    "UNKNOWN": 40.0,
}

_SEASON_FIELD = {"rabi": "rabi", "kharif-1": "kharif1", "kharif-2": "kharif2"}


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_tk(value: float) -> int:
    return int(round(value))


def estimate_rotation_economics(
    *,
    gm_tk_per_decimal: float,
    bcr_vc: float,
    bcr_tc: float,
    area_decimal: float,
) -> dict[str, int]:
    """Reconstruct inspectable rotation economics from CZIS reference fields.

    CZIS defines gross margin = gross revenue - variable cost, BCR(VC) = gross
    revenue / variable cost, and BCR(TC) = gross revenue / total cost.  Those
    identities uniquely determine all five returned values when BCR(VC) > 1.
    """
    gm = float(gm_tk_per_decimal)
    vc_ratio = float(bcr_vc)
    tc_ratio = float(bcr_tc)
    area = float(area_decimal)
    if gm < 0 or area <= 0 or vc_ratio <= 1.0 or tc_ratio <= 0:
        raise ValueError("invalid CZIS economics inputs")
    revenue_per_decimal = gm * vc_ratio / (vc_ratio - 1.0)
    variable_cost_per_decimal = revenue_per_decimal / vc_ratio
    total_cost_per_decimal = revenue_per_decimal / tc_ratio
    gross_revenue = _round_tk(revenue_per_decimal * area)
    total_cost = _round_tk(total_cost_per_decimal * area)
    return {
        "gross_revenue_tk": gross_revenue,
        "variable_cost_tk": _round_tk(variable_cost_per_decimal * area),
        "total_cost_tk": total_cost,
        # Derive displayed net from displayed rounded operands so the identity
        # is exactly reproducible down to one Taka.
        "net_return_tk": gross_revenue - total_cost,
        "gross_margin_tk": _round_tk(gm * area),
    }


def _best_pattern_by_crop(patterns: list[dict], season: str) -> dict[str, dict]:
    field = _SEASON_FIELD.get(season, "rabi")
    out: dict[str, dict] = {}
    for row in patterns:
        crop = str(row.get(field) or "").strip()
        if not crop or crop.lower() == "fallow":
            continue
        key = crop.lower()
        gm = _number(row.get("gm_tk_per_decimal"))
        previous = _number(out.get(key, {}).get("gm_tk_per_decimal"))
        if gm is not None and (previous is None or gm > previous):
            out[key] = row
    return out


def _weather_component(traits: dict, weather: dict) -> tuple[float, list[str]]:
    summary = weather.get("summary") or {}
    warnings: list[str] = []
    max_temp = _number(summary.get("max_temp_c"))
    total_rain = _number(summary.get("total_rain_mm"))
    if max_temp is None and total_rain is None:
        # Unknown is neither safe nor catastrophic: keep a neutral half-score
        # and make the uncertainty visible in the candidate risk reasons.
        return 5.0, ["live forecast values unavailable"]
    score = 10.0
    if max_temp is not None and max_temp > traits["max_temp_c"]:
        warnings.append(
            f"forecast maximum {max_temp:g}°C exceeds {traits['max_temp_c']}°C risk threshold"
        )
        score -= 5.0
    if total_rain is not None and total_rain > traits["heavy_rain_mm"]:
        warnings.append(
            f"forecast rain {total_rain:g} mm exceeds {traits['heavy_rain_mm']} mm risk threshold"
        )
        score -= 5.0
    return max(score, 0.0), warnings


def rank_candidates(
    *,
    profile: dict,
    catalog: list[dict],
    suitability: list[dict],
    patterns: list[dict],
    weather: dict,
    limit: int = 5,
) -> list[dict]:
    """Rank eligible crops and return the PDF-required candidate fields."""
    season = str(profile.get("season") or "").strip().lower()
    area = _number(profile.get("area_decimal")) or 0.0
    budget = _number(profile.get("budget_bdt")) or 0.0
    irrigation = profile.get("irrigation_available") is True
    excluded = {str(c).strip().lower() for c in profile.get("excluded_crops") or []}
    preferred = {str(c).strip().lower() for c in profile.get("preferred_crops") or []}

    suite_by_id = {int(row["crop_id"]): row for row in suitability}
    pattern_by_crop = _best_pattern_by_crop(patterns, season)
    ranked: list[dict] = []

    ordered_catalog = sorted(
        catalog,
        key=lambda item: (
            str(item.get("variety_group") or "").lower()
            != "favourable environment",
            int(item.get("crop_id") or 0),
        ),
    )
    seen_names: set[str] = set()
    for item in ordered_catalog:
        name = str(item.get("name") or "").strip()
        key = name.lower()
        if not name or key in excluded or key not in CROP_TRAITS:
            continue
        if str(item.get("season") or "").strip().lower() != season:
            continue
        pattern = pattern_by_crop.get(key)
        if not pattern or key in seen_names:
            continue  # no defensible local profit number for this candidate
        seen_names.add(key)
        try:
            economics = estimate_rotation_economics(
                gm_tk_per_decimal=float(pattern["gm_tk_per_decimal"]),
                bcr_vc=float(pattern["bcr_vc"]),
                bcr_tc=float(pattern["bcr_tc"]),
                area_decimal=area,
            )
        except (KeyError, TypeError, ValueError):
            continue

        suite = suite_by_id.get(int(item["crop_id"]), {})
        suite_code = str(suite.get("suite_code") or "UNKNOWN").upper()
        suitability_score = _SUITABILITY_POINTS.get(suite_code, 40.0)
        suitability_component = round(suitability_score * 0.5, 2)

        water_level = CROP_TRAITS[key]["water"]
        water_raw = (
            {"low": 100.0, "medium": 90.0, "high": 75.0}[water_level]
            if irrigation
            else {"low": 100.0, "medium": 50.0, "high": 0.0}[water_level]
        )
        water_component = round(water_raw * 0.2, 2)

        required = economics["total_cost_tk"]
        fit_ratio = min(1.0, budget / required) if required > 0 else 0.0
        budget_component = round(fit_ratio * 20.0, 2)
        weather_component, weather_warnings = _weather_component(
            CROP_TRAITS[key], weather
        )

        reasons: list[str] = []
        high_risk = False
        medium_risk = False
        if suite_code in {"NS", "N"}:
            reasons.append("CZIS marks the field not suitable")
            high_risk = True
        elif suite_code in {"MS", "MNS", "UNKNOWN"}:
            reasons.append(f"CZIS suitability is {suite.get('suite') or 'unknown'}")
            medium_risk = True
        if water_level == "high" and not irrigation:
            reasons.append("high water need but irrigation is unavailable")
            high_risk = True
        elif water_level == "medium" and not irrigation:
            reasons.append("medium water need with no assured irrigation")
            medium_risk = True
        if required > budget:
            reasons.append(
                f"recorded rotation total cost {required} Tk exceeds budget {int(budget)} Tk"
            )
            high_risk = high_risk or fit_ratio < 0.5
            medium_risk = True
        if economics["net_return_tk"] < 0:
            reasons.append("recorded rotation has a negative net return over total cost")
            high_risk = True
        if weather_warnings:
            reasons.extend(weather_warnings)
            medium_risk = True
        if not reasons:
            reasons.append("no major constraint conflict detected from retrieved inputs")

        risk_level = "high" if high_risk else "medium" if medium_risk else "low"
        components = {
            "land_suitability": suitability_component,
            "water": water_component,
            "budget": budget_component,
            "weather": round(weather_component, 2),
        }
        score = round(sum(components.values()), 2)
        ranked.append(
            {
                "crop_id": int(item["crop_id"]),
                "crop_name": name,
                "score": score,
                "score_components": components,
                "suitability": {
                    "class": suite.get("suite") or "Unknown",
                    "code": suite_code,
                    "score_0_100": suitability_score,
                    "source": "BARC CZIS GeoServer point layer",
                },
                "water_need": {
                    "level": water_level,
                    "irrigation_available": irrigation,
                    "source": TRAITS_SOURCE,
                },
                "risk": {"level": risk_level, "reasons": reasons},
                "budget_fit": {
                    "farmer_budget_tk": int(budget),
                    "estimated_rotation_total_cost_tk": required,
                    "within_budget": required <= budget,
                },
                "rough_profit": {
                    "estimate_tk": economics["net_return_tk"],
                    "basis": "recorded_full_rotation_net_return",
                    "warning": (
                        "CZIS records economics for the full named annual rotation, "
                        "not this crop alone; use as a rough comparison only."
                    ),
                    "rotation": pattern.get("pattern"),
                    "gross_margin_tk": economics["gross_margin_tk"],
                    "gross_revenue_tk": economics["gross_revenue_tk"],
                    "total_cost_tk": economics["total_cost_tk"],
                    "bcr_vc": float(pattern["bcr_vc"]),
                    "bcr_tc": float(pattern["bcr_tc"]),
                },
                "preferred_by_farmer": key in preferred,
            }
        )

    ranked.sort(
        key=lambda crop: (
            crop["score"],
            crop["preferred_by_farmer"],
            crop["rough_profit"]["estimate_tk"],
        ),
        reverse=True,
    )
    for index, crop in enumerate(ranked[: max(3, min(int(limit), 5))], 1):
        crop["rank"] = index
    return ranked[: max(3, min(int(limit), 5))]
