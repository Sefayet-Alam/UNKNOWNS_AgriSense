"""Merge the CZIS admin hierarchy with COD-AB centroids into the app bundle.

Inputs : czis_admin_raw.json (CZIS harvest), cod_coords.json (OCHA COD-AB)
Output : bd_admin.json — shipped as backend/app/data/bd_admin.json

Coordinates: unions/upazilas/districts get their COD centroid where the BBS
code matches; anything unmatched keeps null (runtime falls back one admin
level up: union -> upazila -> district).
"""
import json

with open("czis_admin_raw.json", encoding="utf-8") as f:
    czis = json.load(f)
with open("cod_coords.json", encoding="utf-8") as f:
    cod = json.load(f)

stats = {"upazila_hit": 0, "upazila_miss": [], "union_hit": 0, "union_miss": 0}


def strip(row, keep):
    out = {k: (row.get(k) or "").strip() if isinstance(row.get(k), str) else row.get(k) for k in keep}
    return out


divisions = [strip(r, ("code", "name_en", "name_bn")) for r in czis["divisions"]]

districts = []
for r in czis["districts"]:
    row = strip(r, ("code", "name_en", "name_bn", "division_code"))
    ll = cod["districts"].get(row["code"])
    row["lat"], row["lon"] = (ll if ll else (None, None))
    districts.append(row)

upazilas = []
for r in czis["upazilas"]:
    row = strip(r, ("code", "name_en", "name_bn", "district_code", "division_code"))
    ll = cod["upazilas"].get(row["code"])
    if ll:
        stats["upazila_hit"] += 1
        row["lat"], row["lon"] = ll
    else:
        stats["upazila_miss"].append(f"{row['code']}:{row['name_en']}")
        row["lat"], row["lon"] = None, None
    upazilas.append(row)

unions = []
for r in czis["unions"]:
    row = strip(
        r,
        (
            "code",
            "name_en",
            "name_bn",
            "paurashava_name",
            "upazila_code",
            "district_code",
            "division_code",
        ),
    )
    ll = cod["unions"].get(row["code"])
    if ll:
        stats["union_hit"] += 1
        row["lat"], row["lon"] = ll
    else:
        stats["union_miss"] += 1
        row["lat"], row["lon"] = None, None
    unions.append(row)

bundle = {
    "sources": {
        "hierarchy": "CZIS getAdminByCode.php (czis.cropzoning.gov.bd), harvested 2026-07-24",
        "coordinates": "OCHA COD-AB Bangladesh gazetteer (data.humdata.org/dataset/cod-ab-bgd, v03 2023)",
    },
    "divisions": divisions,
    "districts": districts,
    "upazilas": upazilas,
    "unions": unions,
}

with open("bd_admin.json", "w", encoding="utf-8") as f:
    json.dump(bundle, f, ensure_ascii=False, separators=(",", ":"))

print(
    f"divisions={len(divisions)} districts={len(districts)} "
    f"upazilas={len(upazilas)} unions={len(unions)}"
)
print(
    f"coords: upazila {stats['upazila_hit']}/{len(upazilas)}, "
    f"union {stats['union_hit']}/{len(unions)} (miss {stats['union_miss']})"
)
if stats["upazila_miss"]:
    print("upazila misses:", stats["upazila_miss"][:20])
import os

print("bundle size:", round(os.path.getsize("bd_admin.json") / 1e6, 2), "MB")
