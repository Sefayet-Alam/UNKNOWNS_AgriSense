"""Harvest per-upazila cropping patterns + economics from CZIS.

GET /croppingpattern/{upazila_code} (public JSON, czis.cropzoning.gov.bd)
returns the existing cropping patterns for an upazila with economics:
rabi/kharif1/kharif2 crops, BCR over variable cost (bcr_vc), BCR over total
cost (bcr_tc), and gross margin in Taka per decimal (gm_tk_dec).

Reads the upazila list from the committed gazetteer bundle and writes
bd_cropping_patterns.json next to this script (ship it to
backend/app/data/).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
GAZETTEER = HERE.parent.parent / "backend" / "app" / "data" / "bd_admin.json"
OUT = HERE / "bd_cropping_patterns.json"
BASE = "https://czis.cropzoning.gov.bd/croppingpattern/"
DELAY = 0.3
RETRIES = 3


def get(code: str):
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(
                BASE + code,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "AgriSense-hackathon/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"FAILED {code}: {last}", file=sys.stderr)
    return None


def main() -> None:
    with open(GAZETTEER, encoding="utf-8") as f:
        upazilas = json.load(f)["upazilas"]

    patterns: dict[str, list] = {}
    failed: list[str] = []
    total_rows = 0
    for i, up in enumerate(upazilas):
        code = up["code"]
        rows = get(code)
        if rows is None:
            failed.append(code)
            continue
        cleaned = []
        for r in rows:
            cleaned.append(
                {
                    "pattern": r.get("cropping_pattern_name") or "",
                    "rabi": r.get("rabi_crop") or "",
                    "kharif1": r.get("kharif1_crop") or "",
                    "kharif2": r.get("kharif2_crop") or "",
                    "bcr_vc": r.get("bcr_vc"),
                    "bcr_tc": r.get("bcr_tc"),
                    "gm_tk_per_decimal": r.get("gm_tk_dec"),
                }
            )
        if cleaned:
            patterns[code] = cleaned
            total_rows += len(cleaned)
        if i % 25 == 0:
            print(f"{i}/{len(upazilas)} -> upazilas with data: {len(patterns)}, rows: {total_rows}")
        time.sleep(DELAY)

    out = {
        "_source": (
            "CZIS /croppingpattern/{upazila_code} "
            "(czis.cropzoning.gov.bd), harvested 2026-07-24. bcr_vc/bcr_tc = "
            "benefit-cost ratio over variable/total cost; gm_tk_per_decimal = "
            "gross margin in Taka per decimal of land."
        ),
        "upazilas": patterns,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(
        f"done: {len(patterns)}/{len(upazilas)} upazilas with patterns, "
        f"{total_rows} rows, failed: {len(failed)}"
    )
    if failed:
        print("failed codes:", failed[:20])


if __name__ == "__main__":
    main()
