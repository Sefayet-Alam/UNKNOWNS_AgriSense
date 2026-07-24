"""Live point crop-suitability lookup from the official BARC CZIS GeoServer.

The public WMS ``GetFeatureInfo`` endpoint can evaluate several crop overlays
at one map pixel in a single request.  That is substantially faster and less
fragile than downloading whole WFS polygons and doing point-in-polygon work in
the application.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

WMS_URL = "https://map2.cropzoning.gov.bd/geoserver/wsBARC/wms"
LAYER = "wsBARC:view_biophysics_suite_all"
TIMEOUT_S = 20.0

_PROPERTIES = (
    "crop_id,suitability,suite,suite_code,map_unit,land_type,soil_group"
)


class CzisSuitabilityError(Exception):
    """The official suitability service failed or returned invalid data."""


async def get_point_suitability(
    latitude: float,
    longitude: float,
    crop_ids: list[int],
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """Return official suitability classes for ``crop_ids`` at one point.

    Crop ids are deduplicated and sent in one CQL filter.  The result preserves
    the official ``VS/S/MS/...`` class rather than asking an LLM to infer land
    suitability from a district-level soil label.
    """
    ids = sorted({int(crop_id) for crop_id in crop_ids if int(crop_id) > 0})
    if not ids:
        raise ValueError("at least one positive crop id is required")

    lat = round(float(latitude), 5)
    lon = round(float(longitude), 5)
    if not (20.0 <= lat <= 27.5 and 87.0 <= lon <= 93.5):
        raise ValueError("point is outside the supported Bangladesh bounds")

    # A small map viewport centered on the field; query its center pixel.
    pad = 0.01
    params = {
        "service": "WMS",
        "version": "1.1.1",
        "request": "GetFeatureInfo",
        "layers": LAYER,
        "query_layers": LAYER,
        "styles": "",
        "bbox": f"{lon-pad:.5f},{lat-pad:.5f},{lon+pad:.5f},{lat+pad:.5f}",
        "srs": "EPSG:4326",
        "width": 101,
        "height": 101,
        "x": 50,
        "y": 50,
        "info_format": "application/json",
        "feature_count": len(ids),
        "CQL_FILTER": f"crop_id IN ({','.join(str(i) for i in ids)})",
        "propertyName": _PROPERTIES,
    }
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        response = await http.get(WMS_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise CzisSuitabilityError(f"CZIS suitability request failed: {exc}") from exc
    finally:
        if owns_client:
            await http.aclose()

    rows: list[dict] = []
    for feature in payload.get("features") or []:
        props = feature.get("properties") or {}
        try:
            crop_id = int(props["crop_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if crop_id not in ids:
            continue
        rows.append(
            {
                "crop_id": crop_id,
                "suitability": props.get("suitability"),
                "suite": props.get("suite") or "Unknown",
                "suite_code": props.get("suite_code") or "UNKNOWN",
                "map_unit": props.get("map_unit"),
                "land_type": props.get("land_type"),
                "soil_group": props.get("soil_group"),
            }
        )
    rows.sort(key=lambda row: row["crop_id"])
    return {
        "latitude": lat,
        "longitude": lon,
        "crops": rows,
        "missing_crop_ids": sorted(set(ids) - {row["crop_id"] for row in rows}),
        "evidence": {
            "source": "BARC CZIS GeoServer",
            "layer": LAYER,
            "endpoint": WMS_URL,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "request_params": {
                "latitude": lat,
                "longitude": lon,
                "crop_ids": ids,
            },
        },
    }
