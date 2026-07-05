# -*- coding: utf-8 -*-
"""
Build bellevue_neighborhoods.geojson for the website: Bellevue's 16 named neighborhoods with,
for each school level, how the neighborhood's school-age kids are divided across attendance zones
PLUS the share living outside Bellevue School District entirely (parts of the city are served by
other districts, e.g. Issaquah / Renton SD).

Uses ALL King County blocks (cached TIGER zip) + a county-wide 2020 DHC P12 pull for ages 5-17,
so the outside-district share is real, not clipped away. Percentages are of the neighborhood's
total school-age kids. splits[level] = {"zones": [{school, pct}...], "outside": pct}.
"""
import os, json, time
import pandas as pd, geopandas as gpd, requests

WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
MCRS = 32610
LEVELS = ["elementary", "middle", "high"]
KEY = open(os.path.join(FDATA, "census", "census_api_key.txt")).read().strip()

# neighborhoods
nbh = gpd.read_file(os.path.join(FDATA, "neighborhoods", "neighborhood_areas.geojson")).to_crs(MCRS)
nbh = nbh.rename(columns={"Neighborhood": "name"})
nbh["name"] = nbh["name"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()

# ALL King County block geometry (cached TIGER zip), clipped to blocks inside a neighborhood
blk = gpd.read_file(os.path.join(FDATA, "census", "tl_2020_53033_tabblock20.zip")).to_crs(MCRS)
pts = gpd.GeoDataFrame(blk[["GEOID20"]].copy(), geometry=blk.geometry.representative_point(), crs=MCRS)
pts = gpd.sjoin(pts, nbh[["name", "geometry"]], predicate="within", how="inner").drop(columns="index_right")
pts = pts.rename(columns={"name": "nbh"})
print("blocks inside a neighborhood:", len(pts))

# county-wide school-age (5-17) per block from 2020 DHC P12 (one call, same pattern as get_age_2020)
VARS = ["P12_004N", "P12_005N", "P12_006N", "P12_028N", "P12_029N", "P12_030N"]
for a in range(5):
    try:
        r = requests.get("https://api.census.gov/data/2020/dec/dhc",
                         params={"get": ",".join(VARS), "for": "block:*",
                                 "in": "state:53 county:033 tract:*", "key": KEY}, timeout=300)
        if r.status_code == 200: break
    except Exception:
        time.sleep(3)
j = r.json()
age = pd.DataFrame(j[1:], columns=j[0])
for c in VARS:
    age[c] = pd.to_numeric(age[c], errors="coerce").fillna(0).astype(int)
age["GEOID20"] = age["state"] + age["county"] + age["tract"] + age["block"]
age["kids"] = age[VARS].sum(axis=1)
pts = pts.merge(age[["GEOID20", "kids"]], on="GEOID20", how="left")
pts["kids"] = pts["kids"].fillna(0)
print("school-age kids in neighborhoods:", int(pts["kids"].sum()))

# zone assignment per level; blocks with no zone = outside Bellevue SD
for lvl in LEVELS:
    z = gpd.read_file(os.path.join(FDATA, "attendance zone boundaries", "(3) post-2023", f"{lvl}.geojson"))[["NAME", "geometry"]].to_crs(MCRS)
    z["zname"] = z["NAME"].str.title()
    pts = gpd.sjoin(pts, z[["zname", "geometry"]], predicate="within", how="left").drop(columns="index_right")
    pts = pts.rename(columns={"zname": f"z_{lvl}"})

# historical states: only ELEMENTARY differs (middle/high documented as unchanged)
def base_name(x):
    x = str(x).strip()
    for suf in [" Elementary School", " Elementary"]:
        if x.endswith(suf): return x[:-len(suf)].strip()
    return x
zb = gpd.read_file(os.path.join(FDATA, "attendance zone boundaries", "(2) 2018-2023", "elementary.geojson"))[["NAME", "geometry"]].to_crs(MCRS)
zb["zname"] = zb["NAME"].str.title()
pts = gpd.sjoin(pts, zb[["zname", "geometry"]], predicate="within", how="left").drop(columns="index_right").rename(columns={"zname": "z_elem_b"})
za = gpd.read_file(os.path.join(FDATA, "attendance zone boundaries", "(1) pre-2018", "elementary.geojson"))
za = za[~za["schnam"].str.contains("Jing Mei|Puesta", case=False)].copy()
za["zname"] = za["schnam"].map(base_name).str.title()
za = za[["zname", "geometry"]].to_crs(MCRS)
pts = gpd.sjoin(pts, za, predicate="within", how="left").drop(columns="index_right").rename(columns={"zname": "z_elem_a"})

splits = {}
for nm in nbh["name"]:
    sub = pts[(pts["nbh"] == nm) & (pts["kids"] > 0)]
    tot = float(sub["kids"].sum())
    d = {"kids": int(tot)}
    def level_split(col):
        if tot <= 0: return {"zones": [], "outside": 0, "outside_n": 0}
        gg = sub.groupby(col, dropna=True)["kids"].sum().sort_values(ascending=False)
        zones = [{"school": k, "pct": round(float(v) / tot * 100, 1), "n": int(v)} for k, v in gg.items() if v > 0]
        out_n = int(sub[sub[col].isna()]["kids"].sum())
        return {"zones": zones, "outside": round(out_n / tot * 100, 1), "outside_n": out_n}
    for lvl in LEVELS:
        d[lvl] = level_split(f"z_{lvl}")
    d["elementary_b"] = level_split("z_elem_b")
    d["elementary_a"] = level_split("z_elem_a")
    splits[nm] = d

out = nbh.to_crs(4326)
feats = []
for _, row in out.iterrows():
    geom = json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"]
    def rnd(o):
        if isinstance(o, float): return round(o, 5)
        if isinstance(o, list): return [rnd(x) for x in o]
        return o
    geom["coordinates"] = rnd(geom["coordinates"])
    feats.append({"type": "Feature",
                  "properties": {"name": row["name"], "splits": splits.get(row["name"], {})},
                  "geometry": geom})
fc = {"type": "FeatureCollection", "features": feats}
fp = os.path.join(WEB, "bellevue_neighborhoods.geojson")
json.dump(fc, open(fp, "w"))
print("SAVED", fp, f"({os.path.getsize(fp)/1024:.0f} KB, {len(feats)} neighborhoods)")
for nm, s in splits.items():
    e = s["elementary"]
    if isinstance(e, dict) and (e["outside"] > 0 or len(e["zones"]) > 1):
        zz = ", ".join(f"{x['school']} {x['pct']}%" for x in e["zones"][:4])
        print(f"  {nm:26} kids={s['kids']:5}  elem: {zz}" + (f"  | OUTSIDE BSD {e['outside']}%" if e["outside"] > 0 else ""))
