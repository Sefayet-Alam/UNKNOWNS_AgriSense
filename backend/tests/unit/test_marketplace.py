"""Gold-number tests for the supplier marketplace engine (Tier 2)."""
from __future__ import annotations

from app.engines import marketplace as mk

# A farm at Paba, Rajshahi (matches sup-001's coordinates closely).
FARM = (24.46, 88.65)


def test_haversine_known_distances():
    assert mk.haversine_km(24.46, 88.65, 24.46, 88.65) == 0.0
    # Rajshahi city -> Dhaka is ~185-200 km.
    d = mk.haversine_km(24.3745, 88.6042, 23.7639, 90.4074)
    assert 180 <= d <= 205


def test_rank_urea_default_score_is_bounded_and_explained():
    out = mk.rank_suppliers("Urea", *FARM)
    assert out["status"] == "ok"
    assert out["results"], "expected urea suppliers"
    for r in out["results"]:
        assert 0.0 <= r["score"] <= 1.0
        assert set(r["score_components"]) == {"price", "distance", "delivery", "rating"}
    # sorted by score descending
    scores = [r["score"] for r in out["results"]]
    assert scores == sorted(scores, reverse=True)


def test_sort_by_price_returns_cheapest_first():
    out = mk.rank_suppliers("Urea", *FARM, sort_by="price", max_results=10)
    prices = [r["price_bdt"] for r in out["results"]]
    assert prices == sorted(prices)
    # National Agro (Dhaka) has the cheapest urea at 25.0.
    assert out["results"][0]["price_bdt"] == 25.0


def test_sort_by_distance_returns_nearest_first():
    out = mk.rank_suppliers("Urea", *FARM, sort_by="distance", max_results=10)
    dists = [r["distance_km"] for r in out["results"]]
    assert dists == sorted(dists)
    # sup-001 sits essentially on the farm point.
    assert out["results"][0]["id"] == "sup-001"


def test_category_query_matches_seed_products():
    out = mk.rank_suppliers("seed", *FARM)
    assert out["status"] == "ok"
    assert all(r["category"] == "seed" for r in out["results"])


def test_unmatched_query_returns_no_match():
    out = mk.rank_suppliers("spaceship parts", *FARM)
    assert out["status"] == "NO_SUPPLIER_MATCH"
    assert out["results"] == []


def test_weights_are_overridable():
    # Pure price weighting should rank the cheapest offer first.
    out = mk.rank_suppliers(
        "Urea", *FARM, weights={"price": 1.0, "distance": 0.0, "delivery": 0.0, "rating": 0.0}
    )
    assert out["results"][0]["price_bdt"] == min(r["price_bdt"] for r in out["results"])
