# bd_admin.json provenance

`backend/app/data/bd_admin.json` (division > district > upazila > union + centroids)
was built on 2026-07-24, inside the hackathon window, by:

1. `harvest_czis_admin.py` — full admin hierarchy from CZIS
   `getAdminByCode.php` (czis.cropzoning.gov.bd): 8 divisions, 64 districts,
   497 upazilas, 7,761 unions/wards with BBS geocodes + Bangla names.
2. `reharvest_unions.py` — re-fetch of the union level keeping
   `paurashava_name` so ward rows get unambiguous labels.
3. `extract_cod_coords.py` — centroids from the OCHA COD-AB Bangladesh
   gazetteer XLSX (data.humdata.org/dataset/cod-ab-bgd, v03 2023). COD pcodes
   are `BD` + the same BBS geocode, so the join is exact (544 upazila points,
   5,160 union points, 64 district centers).
4. `merge_admin_bundle.py` — join + emit `bd_admin.json`. Unions without a
   COD point (mostly paurashava wards) keep null coords; the app falls back
   one admin level up (union -> upazila -> district) at runtime.

Both sources are public government / UN-OCHA data (CC BY 3.0 IGO for COD-AB).
