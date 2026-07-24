"""Harvest the full CZIS admin hierarchy (division > district > upazila > union).

Produces czis_admin_raw.json:
{
  "divisions": [...], "districts": [...], "upazilas": [...], "unions": [...]
}
Each row keeps the CZIS/BBS geocode plus English & Bangla names.
Sequential with small delay + retries (be polite to the .gov.bd box).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://czis.cropzoning.gov.bd/cz_assets/php/getAdminByCode.php"
OUT = "czis_admin_raw.json"
DELAY = 0.35
RETRIES = 3


def post(request: str, code: str | None = None, field: str | None = None):
    data = {"request": request}
    if code is not None:
        data[field] = code
    body = urllib.parse.urlencode(data).encode()
    last = None
    for attempt in range(RETRIES):
        try:
            req = urllib.request.Request(
                BASE,
                data=body,
                headers={
                    "X-Requested-With": "XMLHttpRequest",
                    "User-Agent": "AgriSense-hackathon/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"FAILED {request} {code}: {last}", file=sys.stderr)
    return None


def clean(rows, code_key, name_key):
    out = []
    for r in rows or []:
        out.append(
            {
                "code": r.get(code_key) or r.get("code") or r.get("geocode"),
                "name_en": r.get("name_en") or r.get(name_key),
                "name_bn": r.get("name_bn"),
                **{
                    k: r[k]
                    for k in (
                        "division_code",
                        "district_code",
                        "upazila_code",
                    )
                    if r.get(k)
                },
            }
        )
    return out


def main() -> None:
    divisions = clean(post("forDiv"), "code", "division_name")
    print(f"divisions: {len(divisions)}")

    districts = []
    for d in divisions:
        rows = post("forDist", d["code"], "division_code")
        got = clean(rows, "code", "district_name")
        for g in got:
            g.setdefault("division_code", d["code"])
        districts.extend(got)
        time.sleep(DELAY)
    print(f"districts: {len(districts)}")

    upazilas = []
    for i, dist in enumerate(districts):
        rows = post("forThana", dist["code"], "district_code")
        got = clean(rows, "code", "thana_name")
        for g in got:
            g.setdefault("district_code", dist["code"])
            g.setdefault("division_code", dist.get("division_code"))
        upazilas.extend(got)
        if i % 10 == 0:
            print(f"  district {i}/{len(districts)} -> upazilas so far {len(upazilas)}")
        time.sleep(DELAY)
    print(f"upazilas: {len(upazilas)}")

    unions = []
    for i, up in enumerate(upazilas):
        rows = post("forUnion", up["code"], "thana_name")
        got = clean(rows, "code", "union_name")
        for g in got:
            g.setdefault("upazila_code", up["code"])
            g.setdefault("district_code", up.get("district_code"))
            g.setdefault("division_code", up.get("division_code"))
        unions.extend(got)
        if i % 25 == 0:
            print(f"  upazila {i}/{len(upazilas)} -> unions so far {len(unions)}")
        time.sleep(DELAY)
    print(f"unions: {len(unions)}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": BASE,
                "divisions": divisions,
                "districts": districts,
                "upazilas": upazilas,
                "unions": unions,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
