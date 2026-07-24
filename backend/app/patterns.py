"""Offline per-upazila cropping patterns + economics (CZIS harvest).

Data bundle: ``app/data/bd_cropping_patterns.json`` (built by
``scripts/data_harvest/harvest_cropping_patterns.py``). Per upazila: the
existing cropping patterns practiced there, each with

- rabi / kharif1 / kharif2 crop of the rotation
- ``bcr_vc`` / ``bcr_tc`` — benefit-cost ratio over variable / total cost
- ``gm_tk_per_decimal`` — gross margin in Taka per decimal of land

These are recorded agricultural-economics reference values from the national
Crop Zoning Information System — the grounding source for "rough profit" in
crop recommendations (gm_tk_per_decimal x farm area_decimal = a defensible
gross-margin estimate for a season/rotation).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).parent / "data" / "bd_cropping_patterns.json"

_SEASON_FIELD = {"rabi": "rabi", "kharif-1": "kharif1", "kharif-2": "kharif2"}


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _as_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def patterns_for(
    upazila_code: str,
    season: Optional[str] = None,
    crop: Optional[str] = None,
) -> Optional[list[dict]]:
    """Cropping patterns for one upazila, highest gross margin first.

    ``season`` (rabi / kharif-1 / kharif-2) keeps patterns whose crop in that
    season is a real crop (not Fallow). ``crop`` keeps patterns that include
    the crop name (case-insensitive substring) in any season.
    Returns None when the upazila has no harvested pattern data.
    """
    rows = _bundle()["upazilas"].get((upazila_code or "").strip())
    if rows is None:
        return None
    out = []
    for r in rows:
        if not r.get("pattern"):
            # ~4% of source rows carry crops + economics but a blank name —
            # synthesize the canonical rabi-kharif1-kharif2 rotation label.
            r = {
                **r,
                "pattern": "-".join(
                    (r.get(f) or "").strip() or "Fallow"
                    for f in ("rabi", "kharif1", "kharif2")
                ),
            }
        out.append(r)
    if season:
        field = _SEASON_FIELD.get(season.strip().lower())
        if field:
            out = [
                r
                for r in out
                if r.get(field) and r[field].strip().lower() not in ("", "fallow")
            ]
    if crop:
        needle = crop.strip().lower()
        out = [
            r
            for r in out
            if any(
                needle in (r.get(f) or "").lower()
                for f in ("rabi", "kharif1", "kharif2", "pattern")
            )
        ]
    return sorted(
        out, key=lambda r: _as_float(r.get("gm_tk_per_decimal")) or -1, reverse=True
    )


def source() -> str:
    return _bundle().get("_source", "")


def coverage() -> int:
    return len(_bundle()["upazilas"])
