"""Gold tests for the market-price analysis + sell/store/wait engine (Tier 2)."""
from __future__ import annotations

from app.engines import market_price as mp


def test_resolve_crop_by_alias_and_language():
    assert mp.resolve_crop("potato") == "potato"
    assert mp.resolve_crop("alu") == "potato"
    assert mp.resolve_crop("আলু") == "potato"
    assert mp.resolve_crop("boro dhan") == "boro paddy"
    assert mp.resolve_crop("unobtanium") is None


def test_analyze_series_exposes_trend_and_history():
    out = mp.analyze_crop("potato")["analysis"]
    assert set(out) >= {
        "current_price", "current_date", "history", "trend",
        "trend_bdt_per_kg_per_month", "trend_pct_per_month", "volatility_pct",
    }
    assert out["current_price"] == 30.0
    assert out["history"]["min"] == 15.0
    assert out["history"]["max"] == 30.0


def test_rising_storable_crop_recommends_store():
    res = mp.analyze_crop("potato")
    assert res["analysis"]["trend"] == "rising"
    assert res["recommendation"]["action"] == "store"
    # net benefit = trend gain - storage cost, and it is positive here
    assert res["recommendation"]["net_monthly_benefit_bdt_per_kg"] > 0


def test_perishable_crop_always_sells_now():
    res = mp.analyze_crop("tomato")
    assert res["storable"] is False
    assert res["recommendation"]["action"] == "sell_now"
    assert "perishable" in res["recommendation"]["reason"].lower()


def test_falling_price_recommends_sell_now():
    res = mp.analyze_crop("onion")
    assert res["analysis"]["trend"] == "falling"
    assert res["recommendation"]["action"] == "sell_now"


def test_mild_uptrend_recommends_wait():
    res = mp.analyze_crop("mustard")
    assert res["analysis"]["trend"] == "rising"
    assert res["recommendation"]["action"] == "wait"


def test_stable_price_recommends_sell_now():
    res = mp.analyze_crop("wheat")
    assert res["analysis"]["trend"] == "stable"
    assert res["recommendation"]["action"] == "sell_now"
