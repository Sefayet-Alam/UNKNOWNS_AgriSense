"""CZIS adapter: live crop / variety / fertilizer grounding.

Source: Bangladesh Crop Zoning Information System (czis.cropzoning.gov.bd) —
plain un-authed HTTP endpoints of the national agricultural research council
(BARC). No API key, no Playwright.

Grounding discipline (mirrors adapters/weather.py):
- Only real endpoint values are returned; on failure a ``CzisError`` is raised
  so callers surface the outage honestly and fall back to the FRG knowledge
  base (PLAN.md D4) — never to invented numbers.
- Fertilizer doses are **computed server-side by CZIS** (AEZ + soil aware,
  scaled to the farmer's area). We parse and relay them with evidence; the LLM
  never recomputes them.
- Coordinates-first: the fertilizer + crop-context endpoints are point-based
  (lon/lat), matching how every farm already carries a union/upazila centroid.

Endpoints (discovered from the CZIS front-end JS):
- ``GET /crops/list2``                                    → JSON crop catalog
- ``GET /popup/cropvarietylist/{crop_id}``                → variety table (HTML)
- ``GET /mobile/fertilizer/czis/byvar/crop/{crop_id}/point/lon/{lon}/lat/{lat}``
      → crop name + variety <option> ids for a point (HTML)
- ``GET /czis/fertilizer/recommendationbypoint/crop/{crop_id}/lon/{lon}/lat/{lat}/var/{var_id}/{area_decimal}``
      → computed fertilizer table (HTML)
"""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import httpx

log = logging.getLogger("agrisense.adapters.czis")

BASE_URL = "https://czis.cropzoning.gov.bd"
TIMEOUT_S = 12.0
RETRIES = 2  # total attempts per HTTP call

_CROPS_PATH = Path(__file__).parent.parent / "data" / "czis_crops.json"


class CzisError(Exception):
    """Raised when a live CZIS endpoint could not be fetched or parsed."""


# --------------------------------------------------------------------------- #
# Crop catalog (bundled reference — no network; refresh via scripts/data_harvest)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _crops_bundle() -> dict[str, Any]:
    with open(_CROPS_PATH, encoding="utf-8") as f:
        return json.load(f)


# CZIS seasons -> the season vocabulary used across the app / farm profile.
_SEASON_MAP = {"rabi": "rabi", "kharif-1": "kharif-1", "kharif-2": "kharif-2"}


def list_crops(
    season: Optional[str] = None, name: Optional[str] = None
) -> list[dict]:
    """The bundled CZIS crop catalog (id, name, season, variety_group).

    Optional filters: ``season`` (rabi / kharif-1 / kharif-2) and a
    case-insensitive substring ``name``.
    """
    crops = _crops_bundle()["crops"]
    if season:
        key = _SEASON_MAP.get(season.strip().lower(), season.strip().lower())
        crops = [c for c in crops if c["season"].lower() == key]
    if name:
        needle = name.strip().lower()
        crops = [c for c in crops if needle in c["name"].lower()]
    return crops


def crops_source() -> str:
    return _crops_bundle().get("source", "")


# --------------------------------------------------------------------------- #
# HTTP + HTML helpers
# --------------------------------------------------------------------------- #
async def _get_text(path: str, client: Optional[httpx.AsyncClient]) -> str:
    """GET a CZIS path with bounded retry; raise CzisError on persistent failure."""
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    owns = client is None
    cl = client or httpx.AsyncClient(timeout=TIMEOUT_S, verify=False)
    try:
        last: Exception | None = None
        for attempt in range(RETRIES):
            try:
                resp = await cl.get(url)
                if resp.status_code >= 500:
                    raise CzisError(f"upstream {resp.status_code}")
                resp.raise_for_status()
                return resp.text
            except (httpx.HTTPError, CzisError) as exc:
                last = exc
                log.warning(
                    "GET %s failed (attempt %d/%d): %s",
                    url,
                    attempt + 1,
                    RETRIES,
                    exc,
                )
        log.error("GET %s exhausted retries: %s", url, last)
        raise CzisError(f"request to {url} failed: {last}")
    finally:
        if owns:
            await cl.aclose()


_TAG_RE = re.compile(r"<[^>]+>")
_TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_OPTION_RE = re.compile(
    r'<option\b[^>]*value=["\']([^"\']*)["\'][^>]*>(.*?)</option>',
    re.IGNORECASE | re.DOTALL,
)
_AMOUNT_RE = re.compile(r"([-+]?\d*\.?\d+)\s*(kg|gm|g|ton|t)\b", re.IGNORECASE)


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", fragment))).strip()


def _table_rows(html_text: str) -> list[list[str]]:
    """All table rows as lists of cleaned cell strings (comments stripped)."""
    body = _COMMENT_RE.sub("", html_text)
    rows = []
    for tr in _TR_RE.findall(body):
        cells = [_clean(c) for c in _CELL_RE.findall(tr)]
        rows.append(cells)
    return rows


def _parse_amount(text: str) -> Optional[dict]:
    m = _AMOUNT_RE.search(text or "")
    if not m:
        return None
    unit = m.group(2).lower()
    unit = {"g": "gm", "t": "ton"}.get(unit, unit)
    return {"value": float(m.group(1)), "unit": unit, "raw": text.strip()}


def _evidence(path: str, **extra) -> dict:
    return {
        "source": "CZIS (czis.cropzoning.gov.bd)",
        "endpoint": path,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        **extra,
    }


# --------------------------------------------------------------------------- #
# Variety list: /popup/cropvarietylist/{crop_id}
# --------------------------------------------------------------------------- #
async def get_varieties(
    crop_id: int, *, client: Optional[httpx.AsyncClient] = None
) -> dict:
    """Variety table for a crop: name, yield (t/ha), duration (days), notes.

    Row shape: ``<th>name</th><td>yield</td><td>duration</td><td>notes</td>``.
    """
    path = f"/popup/cropvarietylist/{int(crop_id)}"
    text = await _get_text(path, client)
    varieties = []
    for cells in _table_rows(text):
        if len(cells) < 3:
            continue
        name = cells[0]
        # Skip header / empty rows.
        if not name or name.lower().startswith("variety"):
            continue
        varieties.append(
            {
                "name": name,
                "yield_t_ha": cells[1] or None,
                "duration_days": cells[2] or None,
                "characteristics": cells[3] if len(cells) > 3 else "",
            }
        )
    if not varieties:
        raise CzisError(f"no varieties parsed for crop {crop_id}")
    return {"crop_id": int(crop_id), "varieties": varieties, "evidence": _evidence(path)}


# --------------------------------------------------------------------------- #
# Crop context at a point (crop name + variety ids for the fertilizer call)
# --------------------------------------------------------------------------- #
_CROP_NAME_RE = re.compile(
    r"Crop Name:\s*</b>\s*([^<;]+)", re.IGNORECASE
)


async def get_crop_context(
    crop_id: int,
    latitude: float,
    longitude: float,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Crop name + selectable varieties (with CZIS variety ids) at a point.

    The variety ids returned here are what ``get_fertilizer_recommendation``
    needs as ``variety_id``.
    """
    lat = round(float(latitude), 5)
    lon = round(float(longitude), 5)
    path = f"/mobile/fertilizer/czis/byvar/crop/{int(crop_id)}/point/lon/{lon}/lat/{lat}"
    text = await _get_text(path, client)
    m = _CROP_NAME_RE.search(text)
    crop_name = _clean(m.group(1)) if m else ""
    varieties = []
    seen = set()
    for value, label in _OPTION_RE.findall(text):
        vid = value.strip()
        name = _clean(label)
        if not vid or not vid.isdigit() or not name or vid in seen:
            continue
        seen.add(vid)
        varieties.append({"variety_id": int(vid), "name": name})
    if not varieties:
        raise CzisError(f"no variety options for crop {crop_id} at ({lat},{lon})")
    return {
        "crop_id": int(crop_id),
        "crop_name": crop_name,
        "latitude": lat,
        "longitude": lon,
        "varieties": varieties,
        "evidence": _evidence(path),
    }


# --------------------------------------------------------------------------- #
# Computed fertilizer recommendation at a point
# --------------------------------------------------------------------------- #
async def get_fertilizer_recommendation(
    crop_id: int,
    latitude: float,
    longitude: float,
    variety_id: int,
    area_decimal: float,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """CZIS server-computed fertilizer doses for a crop/variety/point/area.

    Returns structured product rows (Urea / TSP / DAP / MoP / Gypsum / Zinc,
    incl. "or" alternatives) with element + parsed amount, the organic-matter
    note, and evidence. These numbers are computed by CZIS (AEZ + soil aware);
    we relay them verbatim.
    """
    lat = round(float(latitude), 5)
    lon = round(float(longitude), 5)
    area = float(area_decimal)
    area_str = f"{area:g}"
    path = (
        f"/czis/fertilizer/recommendationbypoint/crop/{int(crop_id)}"
        f"/lon/{lon}/lat/{lat}/var/{int(variety_id)}/{area_str}"
    )
    text = await _get_text(path, client)

    products: list[dict] = []
    alternative = False
    notes: list[str] = []
    for cells in _table_rows(text):
        joined = " ".join(cells).strip()
        if not joined:
            continue
        low = joined.lower()
        if low == "or":
            alternative = True  # the NEXT product row is an alternative
            continue
        if low.startswith("* note") or "organic fertilizer" in low or low.startswith(
            "fertilizer application"
        ):
            if len(joined) > 8 and "amount" not in low:
                notes.append(joined.lstrip("* ").strip())
            continue
        if joined.lower().startswith("fertilizer") and "nutrient" in low:
            continue  # header
        if len(cells) >= 3:
            amount = _parse_amount(cells[2])
            if amount is None:
                continue
            products.append(
                {
                    "product": cells[0],
                    "element": cells[1],
                    "amount": amount,
                    "is_alternative": alternative,
                }
            )
            alternative = False

    if not products:
        raise CzisError(
            f"no fertilizer rows parsed (crop {crop_id}, var {variety_id})"
        )
    return {
        "crop_id": int(crop_id),
        "variety_id": int(variety_id),
        "area_decimal": area,
        "latitude": lat,
        "longitude": lon,
        "products": products,
        "notes": notes,
        "evidence": _evidence(path, computed_by="CZIS server (AEZ/soil aware)"),
    }
