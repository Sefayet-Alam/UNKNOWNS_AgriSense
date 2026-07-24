"""Unit tests for the CZIS adapter (crop catalog + variety/fertilizer parsers).

Fully offline: HTML endpoints are served from saved fixtures via
httpx.MockTransport; the bundled crop catalog is read straight from disk. No
network, ever.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.adapters import czis as czis_mod

pytestmark = pytest.mark.unit

FIX = Path(__file__).parent.parent / "fixtures" / "czis"


def _fix(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def make_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# Crop catalog (bundled, no network)
# --------------------------------------------------------------------------- #
def test_list_crops_all_and_filtered():
    all_crops = czis_mod.list_crops()
    assert len(all_crops) == 129
    rabi = czis_mod.list_crops(season="rabi")
    assert rabi and all(c["season"].lower() == "rabi" for c in rabi)
    # season vocabulary maps (winter alias handled by caller, exact here).
    kharif2 = czis_mod.list_crops(season="kharif-2")
    assert all(c["season"] == "Kharif-2" for c in kharif2)


def test_list_crops_name_filter_returns_boro_ids():
    boro = czis_mod.list_crops(name="boro dhan")
    ids = {c["crop_id"] for c in boro}
    assert ids == {1, 2}
    assert all(c["season"] == "Rabi" for c in boro)


# --------------------------------------------------------------------------- #
# get_varieties  (/popup/cropvarietylist/{id})
# --------------------------------------------------------------------------- #
async def test_get_varieties_parses_yield_and_duration():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "cropvarietylist/1" in str(request.url)
        return httpx.Response(200, text=_fix("cropvarietylist_1.html"))

    async with make_client(handler) as client:
        data = await czis_mod.get_varieties(1, client=client)

    assert data["crop_id"] == 1
    assert len(data["varieties"]) >= 50
    first = data["varieties"][0]
    assert first["name"] == "BRRI hybrid dhan10"
    assert first["yield_t_ha"] == "9.7-10.7"
    assert first["duration_days"] == "145-147"
    assert "Saline" in first["characteristics"]
    assert data["evidence"]["source"].startswith("CZIS")


# --------------------------------------------------------------------------- #
# get_crop_context  (byvar point → variety ids)
# --------------------------------------------------------------------------- #
async def test_get_crop_context_extracts_name_and_variety_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        # point-based path carries lon/lat
        assert "/point/lon/" in str(request.url)
        return httpx.Response(200, text=_fix("byvar_point_crop1.html"))

    async with make_client(handler) as client:
        ctx = await czis_mod.get_crop_context(1, 24.62968, 88.44103, client=client)

    assert ctx["crop_name"] == "Boro dhan"
    assert len(ctx["varieties"]) >= 50
    v0 = ctx["varieties"][0]
    assert v0["variety_id"] == 1067
    assert v0["name"] == "BRRI hybrid dhan10"
    assert all(isinstance(v["variety_id"], int) for v in ctx["varieties"])


# --------------------------------------------------------------------------- #
# get_fertilizer_recommendation  (computed doses)
# --------------------------------------------------------------------------- #
async def test_fertilizer_recommendation_parses_products_and_alternatives():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200, text=_fix("recommendationbypoint_crop1_var1067.html")
        )

    async with make_client(handler) as client:
        f = await czis_mod.get_fertilizer_recommendation(
            1, 24.62968, 88.44103, 1067, 33, client=client
        )

    # URL carries every parameter.
    for part in ["crop/1", "var/1067", "/33", "lon/88.44103", "lat/24.62968"]:
        assert part in captured["url"]

    by_product = {p["product"]: p for p in f["products"]}
    assert by_product["Urea"]["amount"] == {
        "value": 58.373,
        "unit": "kg",
        "raw": "58.373 kg",
    }
    assert by_product["Urea"]["element"] == "Nitrogen"
    assert by_product["MoP"]["amount"]["value"] == 30.864
    # Zinc is reported in grams.
    assert by_product["Zinc Sulphate (M)"]["amount"]["unit"] == "gm"
    # "or" rows mark the following product as an alternative.
    assert by_product["Urea (if DAP is used)"]["is_alternative"] is True
    assert by_product["DAP"]["is_alternative"] is True
    assert by_product["Urea"]["is_alternative"] is False
    # Organic-matter note captured, header/blank rows excluded.
    assert any("organic fertilizer" in n.lower() for n in f["notes"])
    assert f["area_decimal"] == 33
    assert f["evidence"]["computed_by"].startswith("CZIS")


# --------------------------------------------------------------------------- #
# Failure sentinels
# --------------------------------------------------------------------------- #
async def test_get_text_retries_then_raises_on_5xx():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="down")

    async with make_client(handler) as client:
        with pytest.raises(czis_mod.CzisError):
            await czis_mod.get_varieties(1, client=client)
    assert calls["n"] == czis_mod.RETRIES  # retried, not one-shot


async def test_empty_table_raises_not_silent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>no table here</body></html>")

    async with make_client(handler) as client:
        with pytest.raises(czis_mod.CzisError):
            await czis_mod.get_fertilizer_recommendation(
                1, 24.6, 88.4, 1067, 33, client=client
            )
