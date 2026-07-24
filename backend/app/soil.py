"""Offline per-upazila soil context from the CZIS edaphic survey.

Data bundle: ``app/data/bd_soil.json`` (480 upazilas; built by
``scripts/data_harvest/build_soil_bundle.py``). The live CZIS soil endpoints
(``/upazila/soil/property/...``) sit behind a login wall, so this harvested
snapshot is the canonical source.

Per upazila and per edaphic type (texture, landtype, drainage, reaction/pH,
consistency, moisture, salinity, recession, relief) we expose the dominant
category (largest surveyed area) plus the full breakdown. This is
UPAZILA-LEVEL data — a default to confirm with the farmer, not a plot
measurement.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).parent / "data" / "bd_soil.json"

# The types most relevant to crop planning, in presentation order.
CORE_TYPES = ("texture", "landtype", "drainage", "reaction", "salinity")


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def soil_context(upazila_code: str) -> Optional[dict]:
    """Soil survey summary for one upazila, or None if not covered.

    Returns {"upazila_code", "types": {type: {dominant, breakdown}}, "source"}.
    """
    code = (upazila_code or "").strip()
    entry = _bundle()["upazilas"].get(code)
    if not entry:
        return None
    return {
        "upazila_code": code,
        "types": entry,
        "source": _bundle().get("_source", ""),
    }


def dominant(upazila_code: str, soil_type: str) -> Optional[str]:
    """Dominant category of one edaphic type (e.g. texture -> 'Clay Loam')."""
    ctx = soil_context(upazila_code)
    if not ctx:
        return None
    entry = ctx["types"].get(soil_type.strip().lower())
    return entry["dominant"] if entry else None


def definition(soil_type: str, category: str) -> str:
    """CZIS legend text for a category (empty string if none)."""
    return (
        _bundle()
        .get("_definitions", {})
        .get(soil_type.strip().lower(), {})
        .get(category, "")
    )


def coverage() -> int:
    return len(_bundle()["upazilas"])
