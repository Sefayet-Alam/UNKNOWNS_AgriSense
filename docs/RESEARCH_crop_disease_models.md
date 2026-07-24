# Research — Crop Disease Image Classification for Bangladesh (Tier 2 feature)

> Parked for after Tier 0/1. Goal: add a leaf-photo disease detector as an
> **agent tool** that feeds the RAG + financial + explainability pipeline (Tier 2
> "Plant disease detection from images"; also lifts Accuracy/practicality +
> Innovation scores). Do **not** train from scratch — wrap an existing model.

## TL;DR
Usable off-the-shelf models covering BD crops exist. Three paths:
- **A. Self-host an HF model** (`transformers` pipeline in backend) — best crop breadth, free, offline.
- **B. Call a hosted disease API** — fastest, no model hosting, external key + limits.
- **C. Fine-tune on BD field datasets** — best real-world accuracy, costs 3-5h.

**Recommendation:** Path A primary (`dsett-ml/BengalCropDisease-finetuned-vit`, MIT,
13 BD crops), rice fallback `prithivMLmods/Rice-Leaf-Disease`; Path B (Kindwise
crop.health) as backup demo. Validate on ~10 real rice/potato photos before committing.

## Key domain caveat (state this honestly in the README)
Almost every public model is trained on **PlantVillage / lab-style images** (single
leaf, clean background, good light) and reports 90-98% on the *same* clean
distribution. Accuracy drops sharply on a farmer's messy field phone photo
(background clutter, shadows, blur, multiple leaves) — the documented
PlantVillage→PlantDoc domain gap. Only Plantix (150M field images, enterprise-only)
and the BD gov app BAMIS run at real field scale, and neither is callable in a hackathon.

## Path A — off-the-shelf HuggingFace models (self-host)
| Model | Arch | Coverage | License | Hosted? | Notes |
|---|---|---|---|---|---|
| **`dsett-ml/BengalCropDisease-finetuned-vit`** | ViT-tiny | **94 classes, 13 BD crops** (rice, potato, tomato, jute, mango, tea, wheat, corn, banana, sugarcane, cotton, guava, papaya, cauliflower) | **MIT** | no (self-host) | Best breadth+license. Fresh/low-download/unvetted → validate first. Trained on `Saon110/bd-crop-vegetable-plant-disease-dataset`. `pipeline("image-classification", model=...)` |
| **`prithivMLmods/Rice-Leaf-Disease`** | Siglip2-base | Rice 5-class: Bacterial Blight, Blast, Brown Spot, Tungro, Healthy | **Apache-2.0** | no | Rice-only, solid, existing HF Spaces. Rice fallback (rice = 74% BD acreage). F1 ~0.947 (own split). |
| `wambugu71/crop_leaf_diseases_vit` | ViT-tiny | 15 classes: corn/potato/rice/wheat | MIT (verify) | no | 727 dl/mo, mixed lab/field data. |
| `linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification` | MobileNetV2 | PlantVillage 38-class (potato/tomato/corn… **no rice**) | other | **YES — warm/HF-hosted** | Only HF-served one; call by HTTP, zero hosting. But no rice → weak for BD. Good for a "zero-setup" demo only. |

Warm-model HTTP call (no self-hosting):
```bash
curl https://router.huggingface.co/hf-inference/models/linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification \
  -X POST -H "Authorization: Bearer $HF_TOKEN" \
  -H "Content-Type: application/octet-stream" --data-binary @leaf.jpg
```
Self-host any of the above:
```python
from transformers import pipeline
pipe = pipeline("image-classification", model="dsett-ml/BengalCropDisease-finetuned-vit")
pipe("leaf.jpg")  # -> [{label, score}, ...]
```

## Path B — hosted disease APIs
| Provider | Coverage | Access | Free tier |
|---|---|---|---|
| **Kindwise `crop.health`** | Purpose-built food-crop disease | REST + API key, POST image → JSON. Docs: https://documenter.getpostman.com/view/3802128/2sA2xh1CXy | **100 free credits** on signup (no card) → best no-train option |
| **Roboflow Universe** | Per-model (BD projects exist: Sylhet Agri Univ tomato, BD rice/mango/tea) | Hosted inference REST per model + key (`inference_sdk.InferenceHTTPClient`) | Free tier + credits; quality varies per community model |
| Plantix (PEAT) | 69 crops / 950+ diseases, >90% field acc, 150M field imgs | REST | **Enterprise sales-only, 4-6 wk onboarding → impractical for hackathon** |

## Path C — Bangladesh-collected datasets (fine-tune)
All BD field-collected unless noted. Small enough for a Colab session.
| Dataset | Crop | Size / classes | License | URL |
|---|---|---|---|---|
| Dhan-Shomadhan | Rice (Dhaka fields) | 1,106 / 5 | **MIT** | kaggle.com/datasets/nirmalsankalana/dhan-shomadhan |
| RiceLeafBD | Rice (Sylhet+Dhaka field) | 1,555 / 4 | CC BY 4.0 | data.mendeley.com/datasets/kx9rx8p2mz/1 |
| BRRI-Gazipur rice | Rice (field) | 2,753 orig (19k aug) / 7 | check | PMC12398871 |
| teaLeafBD | Tea (BD gardens) | 5,276 / 7 | CC BY-SA 4.0 | kaggle.com/datasets/bmshahriaalam/tealeafbd-tea-leaf-disease-detection |
| MangoLeafBD | Mango (4 BD orchards) | 4,000 / 8 | CC BY-NC 4.0 | kaggle.com/datasets/aryashah2k/mango-leaf-disease-dataset |
| BananaLSD | Banana (BSMRAU) | 937 (1,600 aug) / 4 | CC BY-SA 4.0 | kaggle.com/datasets/shifatearman/bananalsd |
| Jute Leaf Disease | Jute (Dinajpur/Brahmanbaria) | 920 / 3 | check | kaggle.com/datasets/mdsaimunalam/jute-leaf-disease-detection |
| **Saon110 BD multi-crop** | 13 crops | **123,588 / 94** (pre-split) | **CC BY-NC-SA 4.0** (non-commercial) | huggingface.co/datasets/Saon110/bd-crop-vegetable-plant-disease-dataset |
| BCDD | Corn/Potato/Rice/Tomato/Wheat | 8,992 / 19 | CC BY 4.0 | kaggle.com/datasets/musfiqurtuhin/bangladeshi-crops-disease-dataset-bcdd |

Rice benchmark for credibility: **Kaggle Paddy Doctor** (10 classes, 10,407 real
field images) — many public notebooks with downloadable weights (ConvNeXt/EfficientNet).

## Existing BD deployed tools (cite in pitch, not callable)
- **BAMIS** (DAE+RIMES gov app, live Jul 2025) — AI disease detection for rice/potato/tomato, Bangla, offline. Closed, no API.
- **BRRI Rice Solution**, **Krishoker Janala** — advisory tools, no ML API.
- Paper: "Bangladeshi crops leaf disease detection using YOLOv8" (Heliyon 2024, 19 classes, rice/corn/wheat/potato/tomato) — PMC11415705.

## Proposed AgriSense integration (the winning framing)
Don't ship a standalone classifier — wire it into the agent loop so one photo hits
4 judged capabilities at once:
```
photo → [tool] diagnose_crop_disease(image) → {crop, disease, confidence, top3 raw scores}
      → visible trace shows model id + scores          (Cap #8 tool trace ✓ — proves it's real)
      → agent routes disease → [RAG] treatment KB       (Cap #7 grounding ✓)
      → explained rec tied to farm profile + cost        (Cap #6 explainability + #5 financial ✓)
```
Impl notes:
- Add a `diagnose_crop_disease` `@tool` in `backend/app/agent/tools.py`; lazy-load
  the model on first call (don't bloat startup). Trace UI shows it automatically.
- `transformers`+`torch` (CPU) adds ~2GB to the backend image — cleaner alternative:
  a small separate `vision` FastAPI service in docker-compose the tool calls over HTTP.
- README must state: model is real off-the-shelf, lab/curated-trained → "best on
  clear, well-lit single-leaf photos." The honest caveat helps the scope score.
