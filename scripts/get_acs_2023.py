# -*- coding: utf-8 -*-
import os, urllib.request
from pathlib import Path
import geopandas as gpd, pandas as pd, requests

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
CDIR = os.path.join(BASE, "census")
OUT  = os.path.join(CDIR, "2023"); os.makedirs(OUT, exist_ok=True)
district_fp = os.path.join(BASE, "attendance zone boundaries", "district_boundary.geojson")
# Census API key: env var CENSUS_API_KEY, or a census_api_key.txt file in the data root
KEY = os.environ.get("CENSUS_API_KEY")
_keyfile = DATA_ROOT / "census_api_key.txt"
if not KEY and _keyfile.exists():
    KEY = _keyfile.read_text().strip()
if not KEY:
    raise SystemExit("Census API key required: set the CENSUS_API_KEY environment variable, "
                     f"or put the key in a file at {_keyfile}")

district = gpd.read_file(district_fp).to_crs(4326)
dgeom = district.geometry.union_all()

# block-group geometry: dissolve from cached King County blocks (BG GEOID = first 12 of block GEOID)
blk_fp = os.path.join(CDIR, "tl_2020_53033_tabblock20.zip")
if not os.path.exists(blk_fp):
    print("re-downloading blocks for dissolve ...")
    urllib.request.urlretrieve("https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/53_WASHINGTON/53033/tl_2020_53033_tabblock20.zip", blk_fp)
blocks = gpd.read_file(blk_fp).to_crs(4326)
blocks["GEOID"] = blocks["GEOID20"].str[:12]
bg = blocks.dissolve(by="GEOID").reset_index()[["GEOID", "geometry"]]
print("King County block groups (dissolved from blocks):", len(bg))

# ACS 2023 5-year variables (block group)
full = {"B01003_001E":"pop","B19013_001E":"med_hh_income","B25077_001E":"med_home_value",
        "B25064_001E":"med_gross_rent","C16002_001E":"lang_hh_total","C16002_004E":"spanish_lep_hh",
        "C16002_007E":"other_ie_lep_hh","C16002_010E":"api_lep_hh","C16002_013E":"other_lep_hh"}
core = {"B01003_001E":"pop","B19013_001E":"med_hh_income","B25077_001E":"med_home_value","B25064_001E":"med_gross_rent"}
url = "https://api.census.gov/data/2023/acs/acs5"

def fetch(varmap):
    p = {"get":",".join(varmap), "for":"block group:*", "in":"state:53 county:033 tract:*", "key":KEY}
    r = requests.get(url, params=p, timeout=180)
    try: rows = r.json()
    except Exception:
        print("  API not JSON:", r.text[:250]); return None
    d = pd.DataFrame(rows[1:], columns=rows[0])
    d["GEOID"] = d["state"]+d["county"]+d["tract"]+d["block group"]
    for k,v in varmap.items():
        d[v] = pd.to_numeric(d[k], errors="coerce")
        d.loc[d[v] < -100000000, v] = None   # ACS null sentinel
    return d[["GEOID"]+list(varmap.values())]

dem = fetch(full)
if dem is None:
    print("full set failed (likely language table not at block group) -> retrying core only")
    dem = fetch(core); usedvars = core
else:
    usedvars = full
print("ACS rows:", 0 if dem is None else len(dem))

bg = bg.merge(dem, on="GEOID", how="left")
bsd = bg[bg.representative_point().within(dgeom)].copy()
bsd = bsd[["GEOID"]+list(usedvars.values())+["geometry"]]
out = os.path.join(OUT, "blockgroups_acs2023.geojson")
bsd.to_file(out, driver="GeoJSON")
print("SAVED:", out)
print("block groups in district:", len(bsd))
print(bsd.drop(columns="geometry").head(8).to_string(index=False))
