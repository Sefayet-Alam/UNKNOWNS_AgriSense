"""Unit tests for the bundled CZIS edaphic soil survey (app.soil).

The bundle (app/data/bd_soil.json) is committed data — these pin the
invariants the mandatory soil_type slot relies on.
"""
from __future__ import annotations

import pytest

from app import geo, soil

pytestmark = pytest.mark.unit


def test_coverage_and_tanore_dominants():
    assert soil.coverage() >= 470  # 480 upazilas surveyed at harvest time
    ctx = soil.soil_context("508194")  # Tanore
    assert ctx is not None
    assert ctx["types"]["texture"]["dominant"] == "Clay Loam"
    assert ctx["types"]["landtype"]["dominant"] == "High Land"
    # Breakdown is sorted by area, largest first.
    breakdown = ctx["types"]["texture"]["breakdown"]
    areas = [a for _, a in breakdown]
    assert areas == sorted(areas, reverse=True)
    assert soil.dominant("508194", "texture") == "Clay Loam"


def test_unknown_upazila_returns_none_not_guess():
    assert soil.soil_context("999999") is None
    assert soil.dominant("999999", "texture") is None
    assert soil.soil_context("") is None


def test_definitions_present_for_core_categories():
    assert "Clay" in soil.definition("texture", "Clay Loam")
    assert soil.definition("texture", "No Such Category") == ""


def test_most_upazilas_in_gazetteer_have_soil_texture():
    # The mandatory-slot flow depends on broad coverage: nearly every real
    # upazila should auto-resolve soil. (A small gap — hill tracts / city
    # corporations — is expected and handled by the SOIL_UNKNOWN ask-path.)
    upazilas = geo.upazilas()
    covered = sum(
        1 for u in upazilas if soil.dominant(u["code"], "texture") is not None
    )
    assert covered / len(upazilas) > 0.9
