"""Bangladesh admin-hierarchy gazetteer: division > district > upazila > union.

Data bundle: ``app/data/bd_admin.json``
- hierarchy + BBS/CZIS geocodes harvested from CZIS ``getAdminByCode.php``
- centroids joined from the OCHA COD-AB Bangladesh gazetteer (pcode == BBS
  geocode, e.g. adm4_pcode BD50819427 == CZIS union geocode 50819427)

Why: the weather API is only reliable when we hand it explicit lat/lon —
live geocoding of Bangla place names is the flaky step. With this bundle a
registered farm ALWAYS has coordinates (union centroid, falling back one
admin level up), so ``get_weather`` never needs the geocoder for the
farmer's own field.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

DATA_PATH = Path(__file__).parent / "data" / "bd_admin.json"


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    b = _bundle()
    by_code: dict[str, dict[str, dict]] = {}
    for level in ("divisions", "districts", "upazilas", "unions"):
        by_code[level] = {r["code"]: r for r in b[level]}
    unions_by_upazila: dict[str, list[dict]] = {}
    for u in b["unions"]:
        unions_by_upazila.setdefault(u["upazila_code"], []).append(u)
    # Name lookup (english, lowercased). Level priority when the same name
    # exists at several levels: upazila > district > union — an admin-unit
    # centroid at any of these levels is accurate enough for weather.
    by_name: dict[str, dict] = {}
    for level in ("unions", "districts", "upazilas"):
        for r in b[level]:
            name = (r.get("name_en") or "").strip().lower()
            if name and (r.get("lat") is not None):
                by_name[name] = {**r, "level": level[:-1]}
    return {
        "by_code": by_code,
        "unions_by_upazila": unions_by_upazila,
        "by_name": by_name,
    }


def divisions() -> list[dict]:
    return _bundle()["divisions"]


def districts(division_code: Optional[str] = None) -> list[dict]:
    rows = _bundle()["districts"]
    if division_code:
        rows = [r for r in rows if r["division_code"] == division_code]
    return rows


def upazilas(district_code: Optional[str] = None) -> list[dict]:
    rows = _bundle()["upazilas"]
    if district_code:
        rows = [r for r in rows if r["district_code"] == district_code]
    return rows


def unions(upazila_code: str) -> list[dict]:
    return _index()["unions_by_upazila"].get(upazila_code, [])


def get(level: str, code: str) -> Optional[dict]:
    """Look up one row by geocode. level: division|district|upazila|union."""
    return _index()["by_code"].get(level + "s", {}).get(code)


def union_valid(union_code: str, upazila_code: str) -> bool:
    row = get("union", union_code)
    return bool(row and row.get("upazila_code") == upazila_code)


def resolve_coords(
    union_code: str = "",
    upazila_code: str = "",
    district_code: str = "",
) -> Optional[dict]:
    """Best available centroid for an address, most specific level first.

    Returns {"lat", "lon", "level", "name"} or None if no code matches.
    """
    for level, code in (
        ("union", union_code),
        ("upazila", upazila_code),
        ("district", district_code),
    ):
        if not code:
            continue
        row = get(level, code)
        if row and row.get("lat") is not None:
            return {
                "lat": row["lat"],
                "lon": row["lon"],
                "level": level,
                "name": row.get("name_en") or "",
            }
    return None


def find_upazila_by_name(
    name: str, district_code: Optional[str] = None
) -> Optional[dict]:
    """Match an upazila by english name (unique match only)."""
    key = (name or "").strip().lower()
    if not key:
        return None
    rows = [
        r
        for r in _bundle()["upazilas"]
        if (r.get("name_en") or "").strip().lower() == key
        and (not district_code or r["district_code"] == district_code)
    ]
    return rows[0] if len(rows) == 1 else None


def find_union_by_name(name: str, upazila_code: str) -> Optional[dict]:
    """Match a union by english name within one upazila."""
    key = (name or "").strip().lower()
    if not key or not upazila_code:
        return None
    for r in unions(upazila_code):
        if (r.get("name_en") or "").strip().lower() == key:
            return r
    return None


def find_place(name: str) -> Optional[dict]:
    """Offline place-name lookup across upazila/district/union english names.

    Returns the gazetteer row (with lat/lon + level) or None. Used before the
    live geocoder so admin-unit names never depend on a network call.
    """
    key = (name or "").strip().lower()
    if not key:
        return None
    return _index()["by_name"].get(key)
