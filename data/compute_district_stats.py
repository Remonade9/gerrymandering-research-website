# -*- coding: utf-8 -*-
"""
District-wide segregation indices (impact 3's index half), on TWO bases:
  residential = 2020 census blocks aggregated to attendance zones (who LIVES in each zone)
  enrollment  = actual per-school race enrollment, CCD 2023-24 via Urban Institute API (who ATTENDS)
Units = the zoned schools per level (choice schools excluded; they are not zone units).
  - Dissimilarity D (White vs non-White): 0.5 * sum |w_i/W - n_i/N|
  - Theil's H (multigroup entropy): 1 - weighted avg unit entropy / district entropy
Groups: white, asian, hispanic, black, twoplus, other(combined incl. AIAN/NHPI/unknown).
Output: bellevue_district_stats.json { residential: {level:{D,H,n}}, enrollment: {...}, meta }
"""
import os, json, math, time
import pandas as pd, geopandas as gpd, requests

WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
MCRS = 32610
LEVELS = ["elementary", "middle", "high"]
G_RES = ["white_nh", "asian_nh", "hispanic", "black_nh", "twoplus_nh", "_other"]

def entropy(shares):
    return -sum(p * math.log(p) for p in shares if p > 0)

def indices(agg, groups, white_col, total_col):
    T = agg[total_col].sum()
    W = agg[white_col].sum(); N = T - W
    D = 0.5 * sum(abs(r[white_col] / W - (r[total_col] - r[white_col]) / N) for _, r in agg.iterrows())
    E = entropy([agg[g].sum() / T for g in groups])
    H = 0.0
    for _, r in agg.iterrows():
        t = r[total_col]
        if t <= 0: continue
        H += (t / T) * (E - entropy([r[g] / t for g in groups])) / E
    return round(float(D), 3), round(float(H), 3), int(len(agg))

# ---------- residential basis ----------
blk = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_2020.geojson")).to_crs(MCRS)
blk["_other"] = blk["aian_nh"] + blk["nhpi_nh"] + blk["other_nh"]
pts = gpd.GeoDataFrame(blk[G_RES + ["total"]].copy(), geometry=blk.geometry.representative_point(), crs=MCRS)
res = {}
zone_names = {}
for lvl in LEVELS:
    z = gpd.read_file(os.path.join(FDATA, "attendance zone boundaries", "(3) post-2023", f"{lvl}.geojson"))[["NAME", "geometry"]].to_crs(MCRS)
    zone_names[lvl] = set(z["NAME"].str.title())
    j = gpd.sjoin(pts, z, predicate="within", how="inner")
    agg = j.groupby("NAME")[G_RES + ["total"]].sum()
    D, H, n = indices(agg, G_RES, "white_nh", "total")
    res[lvl] = {"D": D, "H": H, "n": n}
    print(f"residential {lvl:11} D={D} H={H} n={n}")

# ---------- actual-enrollment basis (CCD 2023-24 race counts) ----------
YEAR = 2023
for a in range(5):
    try:
        r = requests.get(f"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/{YEAR}/grade-99/race/",
                         params={"leaid": "5300390"}, timeout=90)
        if r.status_code == 200: break
    except Exception:
        time.sleep(3)
rows = pd.DataFrame(r.json()["results"])
dirinfo = pd.read_csv(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"))[["ncessch", "school_name", "school_level"]]
def base_name(s):
    s = str(s).strip()
    for suf in [" Elementary School", " Elementary", " Middle School", " Middle",
                " Senior High School", " Senior High", " High School", " High"]:
        if s.endswith(suf): return s[:-len(suf)].strip()
    return s
dirinfo["key"] = dirinfo["school_name"].map(base_name).str.title()
dirinfo["ncessch"] = dirinfo["ncessch"].astype(str).str.zfill(12)
rows["ncessch"] = rows["ncessch"].astype(str).str.zfill(12)
m = rows.merge(dirinfo, on="ncessch", how="left")
# CCD race codes -> our groups
RC = {1: "white", 2: "black", 3: "hispanic", 4: "asian", 5: "other", 6: "other", 7: "twoplus", 8: "other", 9: "other", 20: "other"}
m = m[m["race"] != 99].copy()
m["grp"] = m["race"].map(RC)
m["enrollment"] = pd.to_numeric(m["enrollment"], errors="coerce").fillna(0).clip(lower=0)
piv = m.pivot_table(index=["key", "school_level"], columns="grp", values="enrollment", aggfunc="sum").fillna(0).reset_index()
G_ENR = ["white", "asian", "hispanic", "black", "twoplus", "other"]
for g in G_ENR:
    if g not in piv.columns: piv[g] = 0
piv["total"] = piv[G_ENR].sum(axis=1)
enr = {}
LVL_CODE = {"elementary": 1, "middle": 2, "high": 3}
for lvl in LEVELS:
    sub = piv[(piv["school_level"] == LVL_CODE[lvl]) & (piv["key"].isin(zone_names[lvl]))].set_index("key")
    D, H, n = indices(sub, G_ENR, "white", "total")
    enr[lvl] = {"D": D, "H": H, "n": n}
    print(f"enrollment  {lvl:11} D={D} H={H} n={n}  (schools: {sorted(sub.index)[:3]}...)")

out = {"residential": res, "enrollment": enr,
       "meta": {"residential": "2020 census blocks aggregated to post-2023 zones",
                "enrollment": f"NCES CCD {YEAR}-{YEAR+1-2000} actual per-school race enrollment; zoned schools only (choice excluded)",
                "groups": "White, Asian, Hispanic, Black, Two-plus, Other (combined)"}}
json.dump(out, open(os.path.join(WEB, "bellevue_district_stats.json"), "w"), indent=1)
print("SAVED bellevue_district_stats.json")
