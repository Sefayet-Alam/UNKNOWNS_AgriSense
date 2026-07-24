"""Build the frontend registration hierarchy from the canonical upazila CSV.

The registration and profile address pickers consume
``frontend/src/data/bd-geocodes.json``.  Regenerate that bundle from
``docs/upazilas.csv`` so the UI cannot drift back to the older CZIS response
that mixed metropolitan thanas into the upazila list.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs" / "upazilas.csv"
OUTPUT = ROOT / "frontend" / "src" / "data" / "bd-geocodes.json"
REQUIRED_COLUMNS = {
    "division_code",
    "division_name",
    "district_code",
    "district_name",
    "upazila_code",
    "upazila_name",
    "upazila_name_bn",
}


def _require(value: str | None, column: str, row_number: int) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"Missing {column} at CSV row {row_number}.")
    return cleaned


def main() -> None:
    with SOURCE.open(encoding="utf-8-sig", newline="") as source_file:
        reader = csv.DictReader(source_file)
        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames or ())
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"Canonical CSV is missing columns: {missing}")
        rows = list(reader)

    divisions: dict[str, dict] = {}
    districts: dict[str, dict] = {}
    seen_upazilas: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        division_code = _require(row["division_code"], "division_code", row_number)
        division_name = _require(row["division_name"], "division_name", row_number)
        district_code = _require(row["district_code"], "district_code", row_number)
        district_name = _require(row["district_name"], "district_name", row_number)
        upazila_code = _require(row["upazila_code"], "upazila_code", row_number)
        upazila_name = _require(row["upazila_name"], "upazila_name", row_number)

        division = divisions.setdefault(
            division_code,
            {"name": division_name, "code": division_code, "districts": []},
        )
        if division["name"] != division_name:
            raise ValueError(f"Conflicting name for division {division_code}.")

        district = districts.get(district_code)
        if district is None:
            district = {
                "name": district_name,
                "code": district_code,
                "upazilas": [],
                "_division_code": division_code,
            }
            districts[district_code] = district
            division["districts"].append(district)
        elif (
            district["name"] != district_name
            or district["_division_code"] != division_code
        ):
            raise ValueError(f"Conflicting hierarchy for district {district_code}.")

        if upazila_code in seen_upazilas:
            raise ValueError(f"Duplicate upazila code {upazila_code}.")
        seen_upazilas.add(upazila_code)
        district["upazilas"].append({"name": upazila_name, "code": upazila_code})

    for district in districts.values():
        del district["_division_code"]

    bundle = {
        "source": "docs/upazilas.csv (canonical registration hierarchy)",
        "divisions": list(divisions.values()),
    }
    OUTPUT.write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {OUTPUT.relative_to(ROOT)}: "
        f"{len(divisions)} divisions, {len(districts)} districts, "
        f"{len(seen_upazilas)} upazilas."
    )


if __name__ == "__main__":
    main()
