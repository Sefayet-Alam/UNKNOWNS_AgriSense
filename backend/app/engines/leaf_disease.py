"""Deterministic leaf-disease classification from a photo (Tier 2).

Wraps the bundled multi-head TFLite model (``crop_disease_int8.tflite``):

* input  — float32 ``[1, 224, 224, 3]``, pixels scaled to ``[0, 1]``;
* outputs — four heads in export order: a crop classifier (potato/rice/tomato)
  then one disease head per crop (potato=3, rice=5, tomato=8), matching
  ``class_names.json``.

The model predicts the crop, then we read that crop's disease head. When the
farmer (or the active farm) already names the crop we trust that instead of the
crop head, and always read the matching disease head. No LLM is in the
classification path — the model is the deterministic engine; the agent only
explains the labelled result. Inference errors raise ``LeafDiseaseError`` so the
tool degrades honestly instead of inventing a diagnosis.
"""
from __future__ import annotations

import io
import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

import numpy as np

from ..config import settings

log = logging.getLogger("agrisense.engines.leaf_disease")

INPUT_SIZE = 224
# Export order of the model's output heads. Head 0 is the crop classifier; the
# rest are per-crop disease heads. Kept explicit so a re-exported model with a
# different order is caught by the load-time shape check rather than silently
# mislabelling. See class_names.json for the label lists.
_HEAD_ORDER = ("crop", "potato", "rice", "tomato")

_lock = threading.Lock()
_interpreter = None
_class_map: Optional[dict] = None


class LeafDiseaseError(Exception):
    """Model unavailable, unreadable image, or inconsistent model output."""


def _base_dir() -> Path:
    # settings paths are relative to the backend working directory.
    return Path.cwd()


def load_class_map() -> dict:
    """Load and cache crops + per-crop disease label lists."""
    global _class_map
    if _class_map is None:
        path = _base_dir() / settings.DISEASE_CLASS_NAMES_PATH
        with open(path, encoding="utf-8") as handle:
            _class_map = json.load(handle)
    return _class_map


def _get_interpreter():
    global _interpreter
    if _interpreter is None:
        with _lock:
            if _interpreter is None:
                try:
                    from ai_edge_litert.interpreter import Interpreter
                except Exception as exc:  # pragma: no cover - import guard
                    raise LeafDiseaseError(f"LiteRT runtime unavailable: {exc}") from exc
                model_path = _base_dir() / settings.DISEASE_MODEL_PATH
                if not model_path.exists():
                    raise LeafDiseaseError(f"disease model not found at {model_path}")
                interp = Interpreter(model_path=str(model_path))
                interp.allocate_tensors()
                _interpreter = interp
    return _interpreter


def preprocess(image_bytes: bytes) -> np.ndarray:
    """Decode -> RGB -> 224x224 -> float32 [0,1] -> batch of 1."""
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - import guard
        raise LeafDiseaseError(f"Pillow unavailable: {exc}") from exc
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise LeafDiseaseError(f"could not read image: {exc}") from exc
    img = img.resize((INPUT_SIZE, INPUT_SIZE))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def _softmax(vector: np.ndarray) -> np.ndarray:
    shifted = vector - np.max(vector)
    exp = np.exp(shifted)
    return exp / exp.sum()


def _prettify(label: str) -> str:
    return label.replace("_", " ").strip()


def _is_healthy(label: str) -> bool:
    return "healthy" in label.lower()


def interpret(
    heads: dict[str, np.ndarray],
    *,
    crop_hint: Optional[str] = None,
    top_k: int = 3,
) -> dict:
    """Turn raw head vectors into a labelled diagnosis. Pure, no I/O.

    ``heads`` maps each name in ``_HEAD_ORDER`` to its 1-D score vector.
    ``crop_hint`` (if a supported crop) overrides the crop head.
    """
    class_map = load_class_map()
    crops = [c.lower() for c in class_map["crops"]]
    diseases = {k.lower(): v for k, v in class_map["diseases"].items()}

    crop_scores = _softmax(np.asarray(heads["crop"], dtype=np.float32))
    predicted_crop = crops[int(crop_scores.argmax())]
    crop_confidence = float(crop_scores.max())

    hint = (crop_hint or "").strip().lower()
    if hint in crops:
        crop = hint
        crop_source = "farmer_or_farm_crop"
    else:
        crop = predicted_crop
        crop_source = "model_crop_head"

    disease_vector = np.asarray(heads[crop], dtype=np.float32)
    labels = diseases[crop]
    if disease_vector.shape[0] != len(labels):
        raise LeafDiseaseError(
            f"model disease head for {crop} has {disease_vector.shape[0]} outputs "
            f"but class_names lists {len(labels)}"
        )
    probs = _softmax(disease_vector)
    order = list(np.argsort(probs)[::-1])
    ranked = [
        {
            "label": labels[i],
            "name": _prettify(labels[i]),
            "confidence": round(float(probs[i]), 4),
            "healthy": _is_healthy(labels[i]),
        }
        for i in order[: max(1, top_k)]
    ]
    top = ranked[0]
    return {
        "crop": crop,
        "crop_source": crop_source,
        "crop_confidence": round(crop_confidence, 4),
        "model_predicted_crop": predicted_crop,
        "diagnosis": top["name"],
        "diagnosis_label": top["label"],
        "confidence": top["confidence"],
        "healthy": top["healthy"],
        "top_k": ranked,
        "model_provenance": {
            "model": "crop_disease_int8.tflite (bundled, on-device)",
            "type": "multi-head CNN, int8-quantized TFLite",
            "note": "Deterministic on-device classification; confirm with local extension staff before treatment.",
        },
    }


def classify_image_bytes(
    image_bytes: bytes,
    *,
    crop_hint: Optional[str] = None,
    top_k: int = 3,
    interpreter=None,
) -> dict:
    """Run the full pipeline: preprocess -> model -> labelled diagnosis."""
    interp = interpreter or _get_interpreter()
    tensor = preprocess(image_bytes)
    input_details = interp.get_input_details()[0]
    interp.set_tensor(input_details["index"], tensor)
    interp.invoke()

    outputs = sorted(interp.get_output_details(), key=lambda d: d["name"])
    if len(outputs) != len(_HEAD_ORDER):
        raise LeafDiseaseError(
            f"expected {len(_HEAD_ORDER)} output heads, got {len(outputs)}"
        )
    heads = {
        name: interp.get_tensor(details["index"])[0]
        for name, details in zip(_HEAD_ORDER, outputs)
    }
    return interpret(heads, crop_hint=crop_hint, top_k=top_k)


def supported_crops() -> list[str]:
    return [c.lower() for c in load_class_map()["crops"]]
