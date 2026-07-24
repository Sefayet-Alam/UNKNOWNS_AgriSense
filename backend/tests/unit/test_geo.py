"""Unit tests for the bundled BD admin gazetteer (app.geo).

The bundle itself (app/data/bd_admin.json) is committed data — these tests
pin the invariants the rest of the app relies on: full 4-level hierarchy,
BBS/CZIS geocode joins, and coordinate resolution with level fallback.
"""
from __future__ import annotations

import pytest

from app import geo

pytestmark = pytest.mark.unit


def test_hierarchy_counts():
    assert len(geo.divisions()) == 8
    assert len(geo.districts()) == 64
    assert len(geo.upazilas()) >= 490
    # Unions were harvested per-upazila from CZIS; every upazila got rows.
    total_unions = sum(len(geo.unions(u["code"])) for u in geo.upazilas())
    assert total_unions >= 4500


def test_codes_nest_correctly():
    # BBS geocodes nest by prefix: division(2) < district(4) < upazila(6).
    tanore = geo.get("upazila", "508194")
    assert tanore is not None
    assert tanore["district_code"] == "5081"
    assert tanore["division_code"] == "50"
    badhair = geo.get("union", "50819427")
    assert badhair is not None
    assert badhair["upazila_code"] == "508194"


def test_union_valid():
    assert geo.union_valid("50819427", "508194")
    assert not geo.union_valid("50819427", "508110")  # wrong upazila
    assert not geo.union_valid("99999999", "508194")  # unknown union


def test_resolve_coords_most_specific_first():
    r = geo.resolve_coords(
        union_code="50819427", upazila_code="508194", district_code="5081"
    )
    assert r["level"] == "union"
    assert r["lat"] == pytest.approx(24.62968)


def test_resolve_coords_falls_back_up_the_hierarchy():
    r = geo.resolve_coords(union_code="99999999", upazila_code="508194")
    assert r["level"] == "upazila"
    r = geo.resolve_coords(district_code="5081")
    assert r["level"] == "district"
    assert geo.resolve_coords(union_code="99999999") is None


def test_every_district_has_coordinates():
    missing = [d["code"] for d in geo.districts() if d.get("lat") is None]
    assert missing == []


def test_every_upazila_resolves_to_coords_at_worst_district_level():
    # An upazila missing its own centroid (new city corps etc.) must still
    # resolve through its district — the "always send lat/lon" guarantee.
    unresolved = [
        u["code"]
        for u in geo.upazilas()
        if geo.resolve_coords(upazila_code=u["code"], district_code=u["district_code"])
        is None
    ]
    assert unresolved == []


def test_find_place_and_name_lookups():
    assert geo.find_place("tanore")["code"] == "508194"
    assert geo.find_place("Rajshahi") is not None
    assert geo.find_place("no such place") is None
    assert geo.find_upazila_by_name("Tanore")["code"] == "508194"
    assert geo.find_upazila_by_name("Tanore", "5081")["code"] == "508194"
    assert geo.find_upazila_by_name("Tanore", "1004") is None
    assert geo.find_union_by_name("Badhair", "508194")["code"] == "50819427"
    assert geo.find_union_by_name("Badhair", "508110") is None
