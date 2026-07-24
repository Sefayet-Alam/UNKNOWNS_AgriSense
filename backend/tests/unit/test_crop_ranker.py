"""Gold-number tests for deterministic crop ranking."""
from __future__ import annotations

import pytest

from app.engines.crop_ranker import estimate_rotation_economics, rank_candidates


def test_rotation_economics_is_internally_consistent_and_area_sensitive():
    one = estimate_rotation_economics(
        gm_tk_per_decimal=500, bcr_vc=2.0, bcr_tc=1.25, area_decimal=10
    )
    two = estimate_rotation_economics(
        gm_tk_per_decimal=500, bcr_vc=2.0, bcr_tc=1.25, area_decimal=20
    )

    assert one == {
        "gross_revenue_tk": 10000,
        "variable_cost_tk": 5000,
        "total_cost_tk": 8000,
        "net_return_tk": 2000,
        "gross_margin_tk": 5000,
    }
    assert two["total_cost_tk"] == 16000
    assert two["net_return_tk"] == 4000
    assert two["gross_revenue_tk"] - two["total_cost_tk"] == two["net_return_tk"]


def _inputs(*, irrigation=True, budget=100_000):
    return {
        "profile": {
            "area_decimal": 50,
            "budget_bdt": budget,
            "irrigation_available": irrigation,
            "season": "rabi",
            "soil_texture": "Clay Loam",
            "excluded_crops": [],
            "preferred_crops": [],
        },
        "catalog": [
            {"crop_id": 3, "name": "Wheat", "season": "Rabi"},
            {"crop_id": 12, "name": "Potato", "season": "Rabi"},
            {"crop_id": 22, "name": "Mustard", "season": "Rabi"},
            {"crop_id": 1, "name": "Boro dhan", "season": "Rabi"},
        ],
        "suitability": [
            {"crop_id": 3, "suite": "Very Suitable", "suite_code": "VS"},
            {"crop_id": 12, "suite": "Very Suitable", "suite_code": "VS"},
            {"crop_id": 22, "suite": "Suitable", "suite_code": "S"},
            {"crop_id": 1, "suite": "Moderately Suitable", "suite_code": "MS"},
        ],
        "patterns": [
            {"pattern": "Potato-Mungbean-T. Aman dhan", "rabi": "Potato", "bcr_vc": "1.5", "bcr_tc": "1.2", "gm_tk_per_decimal": "500"},
            {"pattern": "Wheat-Fallow-T. Aman dhan", "rabi": "Wheat", "bcr_vc": "1.4", "bcr_tc": "1.15", "gm_tk_per_decimal": "350"},
            {"pattern": "Mustard-Fallow-T. Aman dhan", "rabi": "Mustard", "bcr_vc": "1.6", "bcr_tc": "1.3", "gm_tk_per_decimal": "300"},
            {"pattern": "Boro dhan-Fallow-Fallow", "rabi": "Boro dhan", "bcr_vc": "1.3", "bcr_tc": "1.1", "gm_tk_per_decimal": "150"},
        ],
        "weather": {
            "summary": {"total_rain_mm": 8.0, "max_temp_c": 31.0, "min_temp_c": 17.0}
        },
    }


def test_ranker_returns_pdf_required_fields_and_three_candidates():
    ranked = rank_candidates(**_inputs())

    assert len(ranked) >= 3
    assert [c["rank"] for c in ranked] == list(range(1, len(ranked) + 1))
    for crop in ranked:
        assert crop["suitability"]["class"]
        assert crop["water_need"]["level"] in {"low", "medium", "high"}
        assert crop["risk"]["level"] in {"low", "medium", "high"}
        assert isinstance(crop["rough_profit"]["estimate_tk"], int)
        assert crop["rough_profit"]["basis"] == "recorded_full_rotation_net_return"
        assert crop["score"] == pytest.approx(sum(crop["score_components"].values()))


def test_ranker_penalizes_high_water_crop_without_irrigation_and_honors_exclusion():
    inputs = _inputs(irrigation=False)
    inputs["profile"]["excluded_crops"] = ["potato"]
    ranked = rank_candidates(**inputs)

    assert "Potato" not in {c["crop_name"] for c in ranked}
    boro = next(c for c in ranked if c["crop_name"] == "Boro dhan")
    mustard = next(c for c in ranked if c["crop_name"] == "Mustard")
    assert boro["risk"]["level"] == "high"
    assert boro["score_components"]["water"] < mustard["score_components"]["water"]


def test_ranker_marks_over_budget_candidate_and_changes_when_budget_changes():
    roomy = rank_candidates(**_inputs(budget=100_000))
    tight = rank_candidates(**_inputs(budget=10_000))

    roomy_potato = next(c for c in roomy if c["crop_name"] == "Potato")
    tight_potato = next(c for c in tight if c["crop_name"] == "Potato")
    assert tight_potato["score"] < roomy_potato["score"]
    assert tight_potato["budget_fit"]["within_budget"] is False
    assert "budget" in " ".join(tight_potato["risk"]["reasons"]).lower()


def test_ranker_treats_missing_weather_as_visible_uncertainty_not_safe_weather():
    inputs = _inputs()
    inputs["weather"] = {"status": "WEATHER_UNAVAILABLE", "summary": {}}
    ranked = rank_candidates(**inputs)

    assert ranked
    assert all(c["score_components"]["weather"] == 5.0 for c in ranked)
    assert all(c["risk"]["level"] != "low" for c in ranked)
    assert all(
        "forecast" in " ".join(c["risk"]["reasons"]).lower() for c in ranked
    )
