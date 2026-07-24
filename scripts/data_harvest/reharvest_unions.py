"""Re-fetch the union stage keeping paurashava fields for disambiguation."""
import json
import time

from harvest_czis_admin import post

with open("czis_admin_raw.json", encoding="utf-8") as f:
    raw = json.load(f)

unions = []
ups = raw["upazilas"]
for i, up in enumerate(ups):
    rows = post("forUnion", up["code"], "thana_name")
    for r in rows or []:
        pname = (r.get("paurashava_name") or "").strip()
        name_en = (r.get("name_en") or r.get("union_name") or "").strip()
        name_bn = (r.get("name_bn") or "").strip()
        if pname:
            name_en = f"{pname} — {name_en}"
        unions.append(
            {
                "code": r.get("code") or r.get("geocode"),
                "name_en": name_en,
                "name_bn": name_bn,
                "paurashava_name": pname,
                "upazila_code": up["code"],
                "district_code": up.get("district_code"),
                "division_code": up.get("division_code"),
            }
        )
    if i % 50 == 0:
        print(f"{i}/{len(ups)} -> {len(unions)}")
    time.sleep(0.3)

raw["unions"] = unions
with open("czis_admin_raw.json", "w", encoding="utf-8") as f:
    json.dump(raw, f, ensure_ascii=False, indent=1)
print(f"unions: {len(unions)}")
