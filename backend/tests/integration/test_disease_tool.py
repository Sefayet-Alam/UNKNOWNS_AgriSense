"""Integration tests for the classify_leaf_disease agent tool (Tier 2)."""
from __future__ import annotations

import io
import json

import pytest
from sqlalchemy import select

from app.agent import tools as tools_mod
from app.agent.tools import build_disease_tool
from app.models import Attachment, User


def _png(path):
    from PIL import Image

    Image.new("RGB", (32, 32), (30, 150, 30)).save(path, format="PNG")


async def _image_attachment(db_session, tmp_path, kind="image"):
    user = (await db_session.execute(select(User))).scalar_one()
    p = tmp_path / "leaf.png"
    _png(p)
    row = Attachment(
        user_id=user.id, kind=kind, mime_type="image/png", path=str(p), transcript=None
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return user, row


@pytest.mark.asyncio
async def test_tool_returns_engine_diagnosis(auth_client, db_session, tmp_path, monkeypatch):
    user, row = await _image_attachment(db_session, tmp_path)

    def fake_classify(image_bytes, *, crop_hint="", top_k=3):
        assert image_bytes  # the stored file was read
        return {
            "crop": "potato",
            "diagnosis": "Potato Early blight",
            "diagnosis_label": "Potato_Early_blight",
            "confidence": 0.91,
            "healthy": False,
            "top_k": [{"label": "Potato_Early_blight", "confidence": 0.91}],
        }

    monkeypatch.setattr(tools_mod.leaf_disease_mod, "classify_image_bytes", fake_classify)

    payload = json.loads(
        await build_disease_tool(user).ainvoke({"attachment_id": row.id})
    )
    assert payload["status"] == "ok"
    assert payload["result"]["diagnosis"] == "Potato Early blight"
    assert payload["result"]["confidence"] == 0.91


@pytest.mark.asyncio
async def test_crop_hint_is_forwarded(auth_client, db_session, tmp_path, monkeypatch):
    user, row = await _image_attachment(db_session, tmp_path)
    seen = {}

    def fake_classify(image_bytes, *, crop_hint="", top_k=3):
        seen["crop_hint"] = crop_hint
        return {"crop": "rice", "diagnosis": "Rice Brown Spot", "confidence": 0.7,
                "healthy": False, "top_k": []}

    monkeypatch.setattr(tools_mod.leaf_disease_mod, "classify_image_bytes", fake_classify)
    await build_disease_tool(user).ainvoke({"attachment_id": row.id, "crop": "rice"})
    assert seen["crop_hint"] == "rice"


@pytest.mark.asyncio
async def test_missing_attachment(auth_client, db_session):
    user = (await db_session.execute(select(User))).scalar_one()
    payload = json.loads(
        await build_disease_tool(user).ainvoke({"attachment_id": 999999})
    )
    assert payload["status"] == "ATTACHMENT_NOT_FOUND"


@pytest.mark.asyncio
async def test_audio_attachment_rejected(auth_client, db_session, tmp_path):
    user, row = await _image_attachment(db_session, tmp_path, kind="audio")
    payload = json.loads(
        await build_disease_tool(user).ainvoke({"attachment_id": row.id})
    )
    assert payload["status"] == "NOT_AN_IMAGE"


@pytest.mark.asyncio
async def test_model_outage_invents_nothing(auth_client, db_session, tmp_path, monkeypatch):
    user, row = await _image_attachment(db_session, tmp_path)

    def boom(image_bytes, *, crop_hint="", top_k=3):
        raise tools_mod.leaf_disease_mod.LeafDiseaseError("model missing")

    monkeypatch.setattr(tools_mod.leaf_disease_mod, "classify_image_bytes", boom)
    payload = json.loads(
        await build_disease_tool(user).ainvoke({"attachment_id": row.id})
    )
    assert payload["status"] == "DISEASE_MODEL_UNAVAILABLE"
