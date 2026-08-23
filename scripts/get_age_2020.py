# -*- coding: utf-8 -*-
"""
Pull child / school-age population per census block for Bellevue SD, 2020 Census DHC table P12
(Sex by Age). Used to weight the travel impact by actual students, not total residents.
Merges onto the block geometry already saved in census/2020/census_blocks_2020.geojson (by GEOID20).
Output: census/2020/census_blocks_age_2020.geojson  (self-contained: GEOID20 + age bands + geometry).

Age bands (both sexes summed):
  under_5   = P12_003N + P12_027N
  age_5_9   = P12_004N + P12_028N   <- primary ELEMENTARY proxy (grades K-5 = ages ~5-10; 5-9 is closest single band)
  age_10_14 = P12_005N + P12_029N   (middle-ish; also covers the age-10 tail of elementary)
  age_15_17 = P12_006N + P12_030N   (high-ish)
Derived: school_age_5_17 = 5_9 + 10_14 + 15_17 ; under_18 = under_5 + school_age_5_17
"""
import os, time
from pathlib import Path
import geopandas as gpd, pandas as pd, requests

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
CDIR = os.path.join(BASE, "census", "2020")
# Census API key: env var CENSUS_API_KEY, or a census_api_key.txt file in the data root
KEY = os.environ.get("CENSUS_API_KEY")
_keyfile = DATA_ROOT / "census_api_key.txt"
if not KEY and _keyfile.exists():
    KEY = _keyfile.read_text().strip()
if not KEY:
    raise SystemExit("Census API key required: set the CENSUS_API_KEY environment variable, "
                     f"or put the key in a file at {_keyfile}")

blocks = gpd.read_file(os.path.join(CDIR, "census_blocks_2020.geojson"))
blocks["tract"] = blocks["GEOID20"].str[5:11]
tracts = sorted(blocks["tract"].unique())
print("district tracts:", len(tracts))

URL = "https://api.census.gov/data/2020/dec/dhc"
VARS = ["P12_001N",  # total
        "P12_003N","P12_004N","P12_005N","P12_006N",   # male: <5, 5-9, 10-14, 15-17
        "P12_027N","P12_028N","P12_029N","P12_030N"]   # female: <5, 5-9, 10-14, 15-17

frames = []
for t in tracts:
    for a in range(5):
        try:
            r = requests.get(URL, params={"get": ",".join(VARS), "for": "block:*",
                                          "in": f"state:53 county:033 tract:{t}", "key": KEY}, timeout=90)
            if r.status_code == 200:
                j = r.json(); frames.append(pd.DataFrame(j[1:], columns=j[0])); break
            elif r.status_code == 204:
                break  # no blocks
        except Exception:
            time.sleep(2)
print("tract responses:", len(frames))

df = pd.concat(frames, ignore_index=True)
for c in VARS:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
df["GEOID20"] = df["state"] + df["county"] + df["tract"] + df["block"]
df["under_5"]   = df["P12_003N"] + df["P12_027N"]
df["age_5_9"]   = df["P12_004N"] + df["P12_028N"]
df["age_10_14"] = df["P12_005N"] + df["P12_029N"]
df["age_15_17"] = df["P12_006N"] + df["P12_030N"]
df["school_age_5_17"] = df["age_5_9"] + df["age_10_14"] + df["age_15_17"]
df["under_18"] = df["under_5"] + df["school_age_5_17"]
keep = ["GEOID20","under_5","age_5_9","age_10_14","age_15_17","school_age_5_17","under_18"]

out = blocks[["GEOID20","INTPTLAT20","INTPTLON20","geometry"]].merge(df[keep], on="GEOID20", how="left")
for c in keep[1:]:
    out[c] = out[c].fillna(0).astype(int)
outpath = os.path.join(CDIR, "census_blocks_age_2020.geojson")
out.to_file(outpath, driver="GeoJSON")

print("SAVED:", outpath, "| blocks:", len(out))
print("district totals:")
for c in ["under_5","age_5_9","age_10_14","age_15_17","school_age_5_17","under_18"]:
    print(f"  {c:16} {out[c].sum():>7,}")
print("blocks with any 5-9 child:", (out['age_5_9']>0).sum())
