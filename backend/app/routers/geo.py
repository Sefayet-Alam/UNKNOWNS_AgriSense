"""Public gazetteer endpoints for the registration address picker.

Unauthenticated by design — the register form needs union options before the
user has an account. Data is the bundled CZIS/BBS hierarchy (read-only).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import geo

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("/unions/{upazila_code}")
async def unions_for_upazila(upazila_code: str):
    if geo.get("upazila", upazila_code) is None:
        raise HTTPException(status_code=404, detail="Unknown upazila code.")
    rows = geo.unions(upazila_code)
    return {
        "upazila_code": upazila_code,
        "results": [
            {"code": r["code"], "name": r["name_en"], "name_bn": r.get("name_bn") or ""}
            for r in rows
        ],
    }
