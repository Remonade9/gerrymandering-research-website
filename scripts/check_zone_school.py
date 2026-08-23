# -*- coding: utf-8 -*-
import geopandas as gpd, os
from pathlib import Path
# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
azb = os.path.join(BASE, "attendance zone boundaries", "(3) post-2023")
sch = gpd.read_file(os.path.join(BASE, "schools", "school_sites.geojson"))
sch = sch[(sch["DISTRICT"] == "Bellevue") & (sch["ISPUBLIC"].astype(str).str.strip() == "Y")]
snames = set(sch["SCHNAME"].astype(str).str.upper().str.strip())
for lvl in ["elementary", "middle", "high"]:
    z = gpd.read_file(os.path.join(azb, lvl + ".geojson"))
    zn = [str(n).upper().strip() for n in z["NAME"]]
    matched = [n for n in zn if n in snames]
    unmatched = [n for n in zn if n not in snames]
    print(f"{lvl:11} zones={len(zn):2}  matched={len(matched):2}  unmatched={unmatched}")
