# -*- coding: utf-8 -*-
"""
Derive the FEEDER PATTERN (elementary -> middle -> high) spatially from attendance-zone boundaries,
weighted by 2020 school-age population per block. BSD publishes no feeder chart (assignment is purely
residential geography), so this reproducible overlay IS the feeder pattern.

Bonus: the split fractions ARE the continuity-vs-travel signal - an elementary that splits across
two middle schools tears its cohort apart at the next level (e.g. Phantom Lake ~54/46 Odle/Tillicum).

Method: assign each block (by representative point) to its elem/middle/high zone, then cross-tabulate
school-age population (5-17). Runs per district state via the STATE var below (default post-2023).
Output: feeder/feeder_<state>.csv (elem->mid, mid->high, elem->high) + feeder_primary_<state>.csv.
"""
import os
from pathlib import Path
import geopandas as gpd, pandas as pd

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
STATE_DIR = "(3) post-2023"          # swap to "(1) pre-2018" for State A; "(2) 2018-2023" once State B arrives
STATE_TAG = "post2023"
OUT = os.path.join(BASE, "feeder"); os.makedirs(OUT, exist_ok=True)

azb = os.path.join(BASE, "attendance zone boundaries", STATE_DIR)
elem = gpd.read_file(os.path.join(azb, "elementary.geojson"))[["NAME","geometry"]].rename(columns={"NAME":"elem"})
mid  = gpd.read_file(os.path.join(azb, "middle.geojson"))[["NAME","geometry"]].rename(columns={"NAME":"mid"})
high = gpd.read_file(os.path.join(azb, "high.geojson"))[["NAME","geometry"]].rename(columns={"NAME":"high"})
age  = gpd.read_file(os.path.join(BASE, "census", "2020", "census_blocks_age_2020.geojson"))

pts = age.copy(); pts["geometry"] = pts.geometry.representative_point()
for layer in (elem, mid, high):
    pts = gpd.sjoin(pts, layer.to_crs(pts.crs), how="left", predicate="within").drop(columns="index_right")

W = "school_age_5_17"

def feeder(a, b):
    t = pts.dropna(subset=[a, b])
    f = t.groupby([a, b])[W].sum().reset_index()
    f["pct"] = (f[W] / f.groupby(a)[W].transform("sum") * 100).round(1)
    return f.sort_values([a, W], ascending=[True, False]).rename(columns={W: "school_age"})

em, mh, eh = feeder("elem","mid"), feeder("mid","high"), feeder("elem","high")
for name, df in [("elem_to_mid", em), ("mid_to_high", mh), ("elem_to_high", eh)]:
    df.insert(0, "level_pair", name)
allf = pd.concat([em.assign(level_pair="elem_to_mid"),
                  mh.assign(level_pair="mid_to_high"),
                  eh.assign(level_pair="elem_to_high")], ignore_index=True)
allf.to_csv(os.path.join(OUT, f"feeder_{STATE_TAG}.csv"), index=False, encoding="utf-8")

# primary feeder (largest share) + a "split" flag when the top share < 85%
def primary(df, a, b):
    top = df.sort_values("school_age", ascending=False).groupby(a).head(1)[[a, b, "pct"]]
    top = top.rename(columns={b: f"primary_{b}", "pct": f"primary_{b}_pct"})
    top[f"{b}_split"] = top[f"primary_{b}_pct"] < 85
    return top
prim = primary(em,"elem","mid").merge(primary(eh,"elem","high"), on="elem", how="outer")
prim.to_csv(os.path.join(OUT, f"feeder_primary_{STATE_TAG}.csv"), index=False, encoding="utf-8")

print("blocks assigned all 3 levels:", pts[["elem","mid","high"]].notna().all(axis=1).sum(), "/", len(pts))
print("\n=== ELEM -> MIDDLE ===\n", em.to_string(index=False))
print("\n=== MIDDLE -> HIGH ===\n", mh.to_string(index=False))
print("\n=== primary feeder + split flags ===\n", prim.to_string(index=False))
print("\nSAVED to", OUT)
