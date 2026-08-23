# -*- coding: utf-8 -*-
import os, urllib.request
from pathlib import Path
import geopandas as gpd
import pandas as pd
import requests

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
CENSUS_DIR = os.path.join(BASE, "census")
os.makedirs(CENSUS_DIR, exist_ok=True)
district_fp = os.path.join(BASE, "attendance zone boundaries", "district_boundary.geojson")
# Census API key: set env var CENSUS_API_KEY, or drop census_api_key.txt in the data root
KEY = os.environ.get("CENSUS_API_KEY")
keyfile = DATA_ROOT / "census_api_key.txt"
if not KEY and keyfile.exists():
    KEY = keyfile.read_text().strip()

# 1) district
district = gpd.read_file(district_fp).to_crs(4326)
dgeom = district.geometry.union_all()
print("district bounds:", [round(x,4) for x in district.total_bounds])

# 2) King County 2020 blocks (TIGER PL - includes POP20/HOUSING20)
zip_url = "https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/53_WASHINGTON/53033/tl_2020_53033_tabblock20.zip"
zip_fp = os.path.join(CENSUS_DIR, "tl_2020_53033_tabblock20.zip")
if not os.path.exists(zip_fp):
    print("downloading TIGER blocks ..."); urllib.request.urlretrieve(zip_url, zip_fp)
blocks = gpd.read_file(zip_fp).to_crs(4326)
print("King County blocks:", len(blocks))
for c in ["POP20","HOUSING20"]:
    if c in blocks.columns: blocks[c] = pd.to_numeric(blocks[c])

# 3) optional race/ethnicity via API (needs key)
if KEY:
    vars_ = ["P2_001N","P2_002N","P2_005N","P2_006N","P2_007N","P2_008N","P2_009N","P2_010N","P2_011N"]
    lab = {"P2_001N":"total","P2_002N":"hispanic","P2_005N":"white_nh","P2_006N":"black_nh","P2_007N":"aian_nh",
           "P2_008N":"asian_nh","P2_009N":"nhpi_nh","P2_010N":"other_nh","P2_011N":"twoplus_nh"}
    r = requests.get("https://api.census.gov/data/2020/dec/pl",
        params={"get":",".join(vars_),"for":"block:*","in":"state:53 county:033 tract:*","key":KEY}, timeout=180)
    rows = r.json(); dem = pd.DataFrame(rows[1:], columns=rows[0])
    dem["GEOID20"] = dem["state"]+dem["county"]+dem["tract"]+dem["block"]
    for v in vars_: dem[lab[v]] = pd.to_numeric(dem[v])
    blocks = blocks.merge(dem[["GEOID20"]+list(lab.values())], on="GEOID20", how="left")
    print("race data merged")
else:
    print("NO API KEY -> geometry + POP20/HOUSING20 only (race skipped)")
    print(f"  (to include race: set env var CENSUS_API_KEY, or put the key in {keyfile})")

# 4) clip to district (representative point within)
racecols = ["total","hispanic","white_nh","black_nh","aian_nh","asian_nh","nhpi_nh","other_nh","twoplus_nh"] if KEY else []
keepcols = [c for c in (["GEOID20","POP20","HOUSING20","INTPTLAT20","INTPTLON20"]+racecols) if c in blocks.columns]
bsd = blocks[blocks.representative_point().within(dgeom)].copy()
bsd = bsd[keepcols+["geometry"]]
msg = "blocks in Bellevue district: %d" % len(bsd)
if "total" in bsd.columns: msg += " | total pop: %d" % int(bsd["total"].sum())
elif "POP20" in bsd.columns: msg += " | total POP20: %d" % int(bsd["POP20"].sum())
print(msg)

# 5) save (census/2020/ = where the downstream scripts read it)
out_dir = os.path.join(CENSUS_DIR, "2020")
os.makedirs(out_dir, exist_ok=True)
out = os.path.join(out_dir, "census_blocks_2020.geojson")
bsd.to_file(out, driver="GeoJSON")
print("SAVED:", out)
print(bsd.drop(columns="geometry").head(6).to_string(index=False))
