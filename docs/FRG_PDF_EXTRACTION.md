# FRG 2024 PDF — Extraction Sanity Check (verified 24 Jul 2026)

Source file: `docs/FRG English 30.10.2024.pdf` (48 MB, 260 pp, PDF 1.5,
iLovePDF-processed, not encrypted). Question answered here: **can `pdftotext`
produce a usable corpus, or do we need OCR?**

## Verdict: `pdftotext -layout` works for everything Tier 0 needs. No blocking OCR.

The PDF is **mixed**: ~159 pages have a clean digital text layer; ~101 pages are
rasterized images (a side effect of the iLovePDF processing + scanned maps).

| Region (PDF pages) | Text layer | Content | Our use |
|---|---|---|---|
| 1–174 (most) | ✅ clean | Prose chapters + **section 7 per-crop fertilizer tables** | RAG corpus + structured tables |
| 87 | ✅ | **Boro rice** soil-test table (2 variety groups, N/P/K/S/Zn by fertility class + OF) | `frg_tables.json` |
| 90–91 | ✅ | **Wheat**, **Maize** tables | `frg_tables.json` |
| 101–102 | ✅ | **Mustard** (both species) tables + split-application method | `frg_tables.json` |
| 106–107 | ✅ | **Potato** table + method | `frg_tables.json` |
| 16, 18, 23–26, 34–46, 51–56, 66, 83, 85–86 (~20 scattered) | ❌ image | Rasterized prose/figures (e.g. p85 = Char/Haor/Barind ecosystem prose) | optional tesseract |
| 175–225 (section 8) | ❌ mostly image (only 176/179/181 have text) | **AEZ cropping-pattern nutrient tables** (one AEZ per ~1-2 pages) | transcribe only AEZ 25/26 |
| 226–230 | ✅ | Appendices 1–8 (fertilizer use stats, toxic limits, soil-test interpretation) | RAG corpus |
| 231–260 | ❌ image | Appendix maps (SRDI nutrient status maps of Bangladesh) | skip |

## Evidence

- `pdftotext -layout` on the whole file → 7,022 lines; per-page char census found
  101 near-empty pages (< 30 chars).
- Mustard table extracts with aligned columns (directly regex/space-splittable):

```
Soil Analysis                       Nutrient Recommendation (kg/ha)                          OF
Interpretation      N            P        K        S      Mg        Zn              B       (t/ha)
Optimum            0-30         0-8      0-25     0-8      –         -              –
Medium            31-60         9-16    26-50     9-16    0–3     0-1.3          0.0–1.0
Low               61-90        17-24    51-75    17-24    4–6    1.4-2.6         0.6–2.0
Very low          91-120       25-32 76-100 25-32         7–9    2.7-3.9         1.1–3.0
```

- AEZ tables for our demo region located by page render:
  **AEZ 25 Level Barind = PDF p209** (printed 194), **AEZ 26 High Barind Tract
  (Rajshahi/Chapai/Naogaon — includes Tanore) = PDF p210–211** (printed 195+).
  Image-only but fully legible at 80 dpi render; key rows already read:
  - AEZ 26, Rabi Wheat 4.0 t/ha: N 120, P 30, K 60, S 15, Mg 4, Zn 2.5, B 2, OF 2 t/ha
  - AEZ 26, Rabi Boro 7.5 t/ha: N 174, P 18, K 80, S 18, Zn 2.5, OF 2 t/ha
- Tesseract 5.3.4 is installed; OCR of rasterized prose p85 was near-perfect
  (checked verbatim). So scattered prose pages are recoverable if wanted.

## Ingestion strategy (feeds PLAN.md Task 4/6)

1. **RAG corpus**: `pdftotext -layout` → keep text-bearing pages only (skip the
   101 image pages), chunk by heading/crop with page metadata.
2. **Structured tables** (never RAG'd — per INSIGHTS, numbers must be computed,
   not retrieved as prose): parse the 5 demo-crop soil-test tables from clean
   text → `backend/app/data/frg_tables.json` with `source_page` per entry.
3. **AEZ 25/26 fallback tables**: hand-transcribe from page renders (2–3 pages,
   verifiable against the images committed nowhere — keep renders local only).
   Primary dose source remains the CZIS union endpoint; FRG AEZ = fallback mode.
4. **Optional, time-permitting**: tesseract the ~20 rasterized prose pages into
   the RAG corpus (`pdftoppm -r 150` → `tesseract` → append with page refs).
   Not required for Tier 0.

Integrity tests (from PLAN.md U8): every structured row keeps `source_page`,
rates non-negative, required nutrients complete per crop.
