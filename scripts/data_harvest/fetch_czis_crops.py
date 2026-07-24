"""Refresh the bundled CZIS crop catalog (backend/app/data/czis_crops.json).

GET /crops/list2 (czis.cropzoning.gov.bd) -> JSON [{Crop_ID, Crop_Name,
Crop_Season, Crop_Var}] -> normalized {crop_id, name, season, variety_group}.
"""
import json
import urllib.request

URL = "https://czis.cropzoning.gov.bd/crops/list2"
OUT = "czis_crops.json"

req = urllib.request.Request(URL, headers={"User-Agent": "AgriSense-hackathon/1.0"})
with urllib.request.urlopen(req, timeout=25) as resp:
    raw = json.loads(resp.read().decode())

crops = [
    {
        "crop_id": c["Crop_ID"],
        "name": c["Crop_Name"],
        "season": c["Crop_Season"],
        "variety_group": c.get("Crop_Var", ""),
    }
    for c in raw
]
crops.sort(key=lambda x: (x["season"], x["name"]))
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(
        {"source": f"CZIS {URL}", "crops": crops},
        f,
        ensure_ascii=False,
        separators=(",", ":"),
    )
print(f"wrote {OUT}: {len(crops)} crops")
