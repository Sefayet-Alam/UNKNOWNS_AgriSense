"""Unit tests for the bundled per-upazila cropping-pattern economics."""
from __future__ import annotations

import pytest

from app import patterns

pytestmark = pytest.mark.unit


def test_coverage_is_broad():
    # Nearly every upazila should carry recorded patterns; the tool's
    # PATTERNS_UNKNOWN path covers the gap.
    assert patterns.coverage() >= 400


def test_kalihati_patterns_sorted_by_margin():
    rows = patterns.patterns_for("309347")  # Kalihati (probed live)
    assert rows
    margins = [
        float(r["gm_tk_per_decimal"])
        for r in rows
        if r.get("gm_tk_per_decimal") is not None
    ]
    assert margins == sorted(margins, reverse=True)
    # Economics fields present on the top row.
    top = rows[0]
    assert top["pattern"]
    assert top["bcr_vc"] is not None
    assert top["gm_tk_per_decimal"] is not None


def test_season_filter_excludes_fallow():
    rows = patterns.patterns_for("309347", season="rabi")
    assert rows
    assert all(r["rabi"].strip().lower() not in ("", "fallow") for r in rows)


def test_crop_filter_matches_any_season():
    rows = patterns.patterns_for("309347", crop="Boro dhan")
    assert rows
    assert all(
        "boro dhan"
        in " ".join(
            (r.get(f) or "").lower() for f in ("rabi", "kharif1", "kharif2", "pattern")
        )
        for r in rows
    )


def test_unknown_upazila_returns_none_not_guess():
    assert patterns.patterns_for("999999") is None
    assert patterns.patterns_for("") is None
