"""Tests for the multi-head leaf-disease inference engine (Tier 2)."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

from app.config import settings
from app.engines import leaf_disease as ld


def _png_bytes(color=(40, 160, 40)):
    from PIL import Image

    img = Image.new("RGB", (256, 256), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _heads(crop, potato, rice, tomato):
    return {
        "crop": np.array(crop, dtype=np.float32),
        "potato": np.array(potato, dtype=np.float32),
        "rice": np.array(rice, dtype=np.float32),
        "tomato": np.array(tomato, dtype=np.float32),
    }


class _FakeInterpreter:
    """Mimics the LiteRT interface for the four-head disease model."""

    def __init__(self, heads):
        self._heads = heads
        # output detail names sorted -> crop, potato, rice, tomato order
        self._out = [
            {"name": "PartitionedCall:0", "index": 10},
            {"name": "PartitionedCall:1", "index": 11},
            {"name": "PartitionedCall:2", "index": 12},
            {"name": "PartitionedCall:3", "index": 13},
        ]
        self._by_index = {
            10: np.array([heads["crop"]]),
            11: np.array([heads["potato"]]),
            12: np.array([heads["rice"]]),
            13: np.array([heads["tomato"]]),
        }

    def get_input_details(self):
        return [{"index": 0, "shape": np.array([1, 224, 224, 3])}]

    def set_tensor(self, index, tensor):
        pass

    def invoke(self):
        pass

    def get_output_details(self):
        return self._out

    def get_tensor(self, index):
        return self._by_index[index]


def test_interpret_selects_crop_head_then_disease_head():
    # crop head favours index 1 -> rice; rice head favours index 3 -> Leaf Blast.
    heads = _heads(
        crop=[0.1, 5.0, 0.1],
        potato=[0, 0, 0],
        rice=[0.1, 0.1, 0.1, 6.0, 0.1],
        tomato=[0] * 8,
    )
    out = ld.interpret(heads, top_k=3)
    assert out["crop"] == "rice"
    assert out["crop_source"] == "model_crop_head"
    assert out["diagnosis"] == "Rice Leaf Blast"
    assert out["diagnosis_label"] == "Rice_Leaf_Blast"
    assert out["healthy"] is False
    assert len(out["top_k"]) == 3
    confs = [t["confidence"] for t in out["top_k"]]
    assert confs == sorted(confs, reverse=True)
    assert 0.0 <= out["confidence"] <= 1.0


def test_crop_hint_overrides_crop_head():
    # crop head says potato, but the farmer says tomato -> read tomato head.
    heads = _heads(
        crop=[5.0, 0.1, 0.1],
        potato=[5.0, 0, 0],
        rice=[0] * 5,
        tomato=[0, 0, 0, 0, 0, 0, 0, 9.0],  # index 7 -> Tomato_healthy
    )
    out = ld.interpret(heads, crop_hint="Tomato")
    assert out["crop"] == "tomato"
    assert out["crop_source"] == "farmer_or_farm_crop"
    assert out["diagnosis"] == "Tomato healthy"
    assert out["healthy"] is True
    assert out["model_predicted_crop"] == "potato"


def test_mismatched_head_size_raises():
    heads = _heads(crop=[1, 0, 0], potato=[1, 0], rice=[0] * 5, tomato=[0] * 8)
    with pytest.raises(ld.LeafDiseaseError):
        ld.interpret(heads)


def test_full_pipeline_with_fake_interpreter():
    heads = _heads(
        crop=[0.1, 0.1, 5.0],  # tomato
        potato=[0] * 3,
        rice=[0] * 5,
        tomato=[6.0, 0, 0, 0, 0, 0, 0, 0],  # Tomato_Bacterial_spot
    )
    out = ld.classify_image_bytes(
        _png_bytes(), interpreter=_FakeInterpreter(heads)
    )
    assert out["crop"] == "tomato"
    assert out["diagnosis"] == "Tomato Bacterial spot"
    assert out["model_provenance"]["type"].startswith("multi-head")


def test_bad_image_bytes_raise():
    with pytest.raises(ld.LeafDiseaseError):
        ld.classify_image_bytes(b"not an image", interpreter=_FakeInterpreter(
            _heads([1, 0, 0], [1, 0, 0], [0] * 5, [0] * 8)
        ))


@pytest.mark.skipif(
    not (Path.cwd() / settings.DISEASE_MODEL_PATH).exists(),
    reason="bundled TFLite model not present",
)
def test_real_model_runs_and_returns_valid_structure():
    out = ld.classify_image_bytes(_png_bytes())
    assert out["crop"] in ld.supported_crops()
    assert 0.0 <= out["confidence"] <= 1.0
    confs = [t["confidence"] for t in out["top_k"]]
    assert confs == sorted(confs, reverse=True)
    assert out["diagnosis_label"] in ld.load_class_map()["diseases"][out["crop"]]
