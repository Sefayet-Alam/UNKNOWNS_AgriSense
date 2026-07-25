"""Deterministic supplier matching & ranking (Tier 2 marketplace).

Matches a farmer's input need (fertilizer, seed, pesticide) against a seeded
supplier catalog and ranks the offers by a transparent weighted score over
**price, delivery time, distance and rating**. Prices/delivery/ratings are
clearly-labelled seeded demo values; **distance is genuine** — haversine from
the farm's real coordinates to each supplier's real coordinates.

No I/O beyond loading the bundled catalog; the score math is pure and
gold-tested, and every result exposes its component breakdown so the ranking is
inspectable rather than a black box.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "suppliers.json"

# Weighted score over normalised dimensions (each mapped so 1.0 = best in the
# matched set). Documented + overridable so the ranking is not a black box.
DEFAULT_WEIGHTS = {"price": 0.40, "distance": 0.25, "delivery": 0.20, "rating": 0.15}
_SORT_DIMS = {"score", "price", "distance", "delivery", "rating"}


@lru_cache(maxsize=1)
def _catalog() -> dict:
    with open(_DATA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lon points."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _matches(query: str, product: dict) -> bool:
    q = query.strip().lower()
    if not q:
        return False
    return (
        q in str(product.get("product", "")).lower()
        or q in str(product.get("category", "")).lower()
    )


def _cheapest_match(query: str, supplier: dict) -> Optional[dict]:
    candidates = [p for p in supplier.get("products", []) if _matches(query, p)]
    if not candidates:
        return None
    return min(candidates, key=lambda p: float(p["price_bdt"]))


def _norm(value: float, lo: float, hi: float, *, higher_better: bool) -> float:
    if hi <= lo:
        return 1.0
    frac = (value - lo) / (hi - lo)
    return frac if higher_better else 1.0 - frac


def rank_suppliers(
    product_query: str,
    latitude: float,
    longitude: float,
    *,
    sort_by: str = "score",
    max_results: int = 5,
    weights: Optional[dict] = None,
) -> dict:
    """Rank suppliers offering ``product_query`` for a farm at (lat, lon).

    Returns ``{"status": "ok"|"NO_SUPPLIER_MATCH", "results": [...], ...}``.
    Each result carries the matched offer, real distance, rating, delivery and a
    0-1 score with its component breakdown.
    """
    if sort_by not in _SORT_DIMS:
        sort_by = "score"
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    offers = []
    for supplier in _catalog()["suppliers"]:
        match = _cheapest_match(product_query, supplier)
        if match is None:
            continue
        dist = haversine_km(
            latitude, longitude, supplier["latitude"], supplier["longitude"]
        )
        offers.append(
            {
                "id": supplier["id"],
                "name": supplier["name"],
                "district": supplier["district"],
                "upazila": supplier["upazila"],
                "distance_km": round(dist, 1),
                "product": match["product"],
                "category": match["category"],
                "price_bdt": float(match["price_bdt"]),
                "unit": match["unit"],
                "delivery_days": int(supplier["delivery_days"]),
                "rating": float(supplier["rating"]),
                "_dist": dist,
            }
        )

    if not offers:
        return {
            "status": "NO_SUPPLIER_MATCH",
            "query": product_query,
            "message": "No seeded supplier carries a product matching that need.",
            "results": [],
        }

    prices = [o["price_bdt"] for o in offers]
    dists = [o["_dist"] for o in offers]
    delivs = [o["delivery_days"] for o in offers]
    ratings = [o["rating"] for o in offers]
    p_lo, p_hi = min(prices), max(prices)
    d_lo, d_hi = min(dists), max(dists)
    v_lo, v_hi = min(delivs), max(delivs)
    r_lo, r_hi = min(ratings), max(ratings)

    for o in offers:
        comp = {
            "price": round(_norm(o["price_bdt"], p_lo, p_hi, higher_better=False), 4),
            "distance": round(_norm(o["_dist"], d_lo, d_hi, higher_better=False), 4),
            "delivery": round(_norm(o["delivery_days"], v_lo, v_hi, higher_better=False), 4),
            "rating": round(_norm(o["rating"], r_lo, r_hi, higher_better=True), 4),
        }
        o["score_components"] = comp
        o["score"] = round(
            w["price"] * comp["price"]
            + w["distance"] * comp["distance"]
            + w["delivery"] * comp["delivery"]
            + w["rating"] * comp["rating"],
            4,
        )
        del o["_dist"]

    if sort_by == "price":
        offers.sort(key=lambda o: o["price_bdt"])
    elif sort_by == "distance":
        offers.sort(key=lambda o: o["distance_km"])
    elif sort_by == "delivery":
        offers.sort(key=lambda o: o["delivery_days"])
    elif sort_by == "rating":
        offers.sort(key=lambda o: -o["rating"])
    else:
        offers.sort(key=lambda o: -o["score"])

    return {
        "status": "ok",
        "query": product_query,
        "sorted_by": sort_by,
        "weights": w,
        "results": offers[: max(1, max_results)],
        "provenance": (
            "Prices, delivery days and ratings are seeded demo values (catalog "
            f"{_catalog()['version']}); distance is real haversine from the farm "
            "coordinates. Confirm quotes with the supplier before purchase."
        ),
    }
