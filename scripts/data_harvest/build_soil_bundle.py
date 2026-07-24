"""Build backend/app/data/bd_soil.json from the harvested CZIS edaphic survey.

Input : edaphic.csv + edaphic_definitions.csv (harvested 2026-07-24 from the
        CZIS per-upazila edaphic tabs — those endpoints now sit behind a login
        wall, so the raw CSVs committed next to this script are the canonical
        copy; see raw/README note).
Output: bd_soil.json —
        { "<upazila_code>": { "<type>": { "dominant": str,
                                          "breakdown": [[category, area_ha], ...] } } }
        plus "_definitions" with the CZIS legend text per (type, category).

Types: landtype, texture, consistency, drainage, reaction (pH class),
moisture, salinity, recession, relief. "dominant" = category with the largest
surveyed area for that upazila. Area unit: hectares as served by CZIS.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
EDAPHIC = HERE / "raw" / "edaphic.csv"
DEFS = HERE / "raw" / "edaphic_definitions.csv"
OUT = HERE / "bd_soil.json"

per_upazila: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(
    lambda: defaultdict(list)
)
with open(EDAPHIC, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        code = row["upazila_code"].strip()
        typ = row["type"].strip().lower()
        cat = row["category"].strip()
        try:
            area = float(row["area"])
        except (ValueError, TypeError):
            continue
        if code and typ and cat:
            per_upazila[code][typ].append((cat, area))

bundle: dict = {}
for code, types in sorted(per_upazila.items()):
    entry = {}
    for typ, rows in types.items():
        rows.sort(key=lambda r: -r[1])
        entry[typ] = {
            "dominant": rows[0][0],
            "breakdown": [[c, round(a, 2)] for c, a in rows],
        }
    bundle[code] = entry

definitions: dict[str, dict[str, str]] = defaultdict(dict)
with open(DEFS, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        definitions[row["type"].strip().lower()][row["category"].strip()] = row[
            "note"
        ].strip()

out = {
    "_source": (
        "CZIS per-upazila edaphic survey (czis.cropzoning.gov.bd), harvested "
        "2026-07-24. The soil endpoints now require login — these CSVs are the "
        "canonical offline copy."
    ),
    "_definitions": definitions,
    "upazilas": bundle,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

n_tex = sum(1 for v in bundle.values() if "texture" in v)
print(f"upazilas: {len(bundle)} (with texture: {n_tex})")
print(f"size: {OUT.stat().st_size / 1e6:.2f} MB")
print("Tanore 508194 texture:", bundle.get("508194", {}).get("texture"))
