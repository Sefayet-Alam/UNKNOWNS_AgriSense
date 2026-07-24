"""CZIS GeoServer point-suitability adapter contract tests."""
from __future__ import annotations

import httpx
import pytest

from app.adapters import czis_suitability


@pytest.mark.asyncio
async def test_point_suitability_batches_crop_ids_and_parses_official_classes():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "properties": {
                            "crop_id": 3,
                            "suitability": 1,
                            "suite": "Very Suitable",
                            "suite_code": "VS",
                            "map_unit": 2,
                            "land_type": 1,
                            "soil_group": 1431,
                        }
                    },
                    {
                        "properties": {
                            "crop_id": 22,
                            "suitability": 2,
                            "suite": "Suitable",
                            "suite_code": "S",
                            "map_unit": 2,
                            "land_type": 1,
                            "soil_group": 1431,
                        }
                    },
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await czis_suitability.get_point_suitability(
            24.62968, 88.44103, [22, 3, 3], client=client
        )

    assert [row["crop_id"] for row in result["crops"]] == [3, 22]
    assert result["crops"][0]["suite_code"] == "VS"
    assert seen["request"] == "GetFeatureInfo"
    assert seen["CQL_FILTER"] == "crop_id IN (3,22)"
    assert seen["propertyName"].startswith("crop_id,suitability,suite")
    assert result["evidence"]["source"] == "BARC CZIS GeoServer"
    assert result["evidence"]["request_params"]["latitude"] == 24.62968


@pytest.mark.asyncio
async def test_point_suitability_rejects_empty_crop_ids_without_http_call():
    with pytest.raises(ValueError, match="crop id"):
        await czis_suitability.get_point_suitability(24.6, 88.5, [])


@pytest.mark.asyncio
async def test_point_suitability_reports_upstream_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(czis_suitability.CzisSuitabilityError, match="503"):
            await czis_suitability.get_point_suitability(
                24.6, 88.5, [3], client=client
            )
