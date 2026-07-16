# -*- coding: utf-8 -*-
"""
Enrich the web zone GeoJSONs (bellevue_<level>_zones.geojson) with per-zone IMPACT properties
1-5 for the side panel, computed on the current (post-2023 / State C) map:
  seg      - residential racial composition (%), from 2020 census blocks
  housing  - median household income / home value / gross rent, from ACS 2023 block groups
  language - limited-English household share (%), from ACS 2023
  travel   - distance (km) from each home to its ASSIGNED school, weighted by school-age kids
             (avg + min/q1/med/q3/max + histogram + within-1/2/3 km shares)
  programs - distance to the nearest school hosting each program type (same distribution shape)
Run AFTER build_bellevue_basics.py (it adds to the compactness props already in those files).
Distances are straight-line in UTM 10N metres (road/time distributions come with the routing step).
"""
import os, json
import numpy as np, pandas as pd, geopandas as gpd

WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
MCRS = 32610
LEVELS = ["elementary", "middle", "high"]
LEVEL_GRADE = {"elementary": "K-5", "middle": "6-8", "high": "9-12"}
RACE = {"white_nh": "white", "asian_nh": "asian", "hispanic": "hispanic", "black_nh": "black",
        "twoplus_nh": "twoplus", "aian_nh": "aian", "nhpi_nh": "nhpi", "other_nh": "other"}
PROG_CATS = ["advanced_learning", "language_immersion", "special_education", "ib"]

# ---- source data (once) ----
blk = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_2020.geojson"))
age = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_age_2020.geojson"))[["GEOID20", "school_age_5_17"]]
blk = blk.merge(age, on="GEOID20", how="left")
blk["school_age_5_17"] = blk["school_age_5_17"].fillna(0)
blk = blk.to_crs(MCRS)
bpts = gpd.GeoDataFrame(blk.drop(columns="geometry"), geometry=blk.geometry.representative_point(), crs=MCRS)

acs = gpd.read_file(os.path.join(FDATA, "census", "2023", "blockgroups_acs2023.geojson")).to_crs(MCRS)

ACS_COUNT_COLS = ["lang_hh_total", "spanish_lep_hh", "other_ie_lep_hh", "api_lep_hh", "other_lep_hh"]

def apportion_acs(bz_assigned, acs_bg):
    """Population-apportion ACS block-group data across zones.

    A block group that straddles a zone boundary contributes to each zone in
    proportion to its 2020 block population inside that zone (dasymetric split),
    instead of being dumped whole into whichever zone holds its center point.
    Count columns are scaled by the share; median columns keep their BG value and
    are later weighted by the in-zone 2020 population ("pop")."""
    b = bz_assigned[["GEOID20", "name", "total"]].copy()
    b["BG"] = b["GEOID20"].str[:12]
    zp = b.groupby(["BG", "name"])["total"].sum().rename("bgpop").reset_index()
    tot = zp.groupby("BG")["bgpop"].transform("sum")
    zp["share"] = np.where(tot > 0, zp["bgpop"] / tot, 0.0)
    zp = zp[zp["share"] > 0]
    aw = zp.merge(acs_bg.drop(columns="geometry"), left_on="BG", right_on="GEOID", how="inner")
    for c in ACS_COUNT_COLS:
        aw[c] = aw[c].fillna(0) * aw["share"]
    aw["pop"] = aw["bgpop"]
    return aw

sc = gpd.read_file(os.path.join(FDATA, "schools", "school_sites.geojson"))
sc = sc[(sc.DISTRICT == "Bellevue") & (sc.ISPUBLIC.astype(str).str.strip() == "Y")]
sc = sc[sc.SCHNAME.astype(str).str.strip() != "Vacant"].to_crs(MCRS)
sc["nm"] = sc.SCHNAME.astype(str).str.strip().str.title()
name2pt = dict(zip(sc.nm, sc.geometry))

ph = pd.read_csv(os.path.join(FDATA, "programs", "program_hosting.csv"))
def host_points(level, cat):
    sub = ph[(ph.level == level) & (ph.category == cat)]
    return [name2pt[str(n).strip().title()] for n in sub.host_school.dropna().unique()
            if str(n).strip().title() in name2pt]
def host_names(level, cat):
    sub = ph[(ph.level == level) & (ph.category == cat)]
    return [str(n).strip().title() for n in sub.host_school.dropna().unique()]

def summarize(d, w, thresholds=(1, 2, 3)):
    d = np.asarray(d, float); w = np.asarray(w, float)
    m = w > 0; d, w = d[m], w[m]
    if len(d) == 0 or w.sum() == 0:
        return None
    o = np.argsort(d); d, w = d[o], w[o]; cw = np.cumsum(w); tot = cw[-1]
    q = lambda p: float(d[min(int(np.searchsorted(cw, p * tot)), len(d) - 1)])
    wi = lambda t: round(float(w[d <= t].sum() / tot * 100), 1)
    n_total = int(round(tot))
    xmax = float(d[-1])
    # empirical cumulative curve: % of students within x, sampled 0..max at 40 steps
    N = 40
    ys = []
    for i in range(N + 1):
        x = xmax * i / N
        idx = int(np.searchsorted(d, x, side="right"))
        ys.append(round(float(cw[idx - 1]) / tot * 100, 1) if idx > 0 else 0.0)
    out = {"avg": round(float((d * w).sum() / tot), 2), "min": round(float(d[0]), 2),
           "q1": round(q(.25), 2), "med": round(q(.5), 2), "q3": round(q(.75), 2),
           "max": round(xmax, 2), "n": n_total,
           "cdf": {"max": round(xmax, 2), "y": ys}}
    for t in thresholds:
        out[f"within{t}"] = wi(t)
    return out

def dist_to_point(sub, pt):
    if pt is None or len(sub) == 0:
        return None
    return summarize((sub.geometry.distance(pt) / 1000.0).values, sub["school_age_5_17"].values)

def dist_to_nearest(sub, pts):
    if not pts or len(sub) == 0:
        return None
    dmin = None
    for p in pts:
        dd = sub.geometry.distance(p).values
        dmin = dd if dmin is None else np.minimum(dmin, dd)
    return summarize(dmin / 1000.0, sub["school_age_5_17"].values)

# ---- road routing (precomputed ORS matrices; see scripts/precompute_routes.py) ----
def load_routes(level, tag):
    fp = os.path.join(FDATA, "routing", f"routes_{tag}_{level}.json")
    return json.load(open(fp)) if os.path.exists(fp) else None

def road_stats(sub, routes, school_names, min_thresholds):
    """Network km + minutes summaries for blocks in `sub`, to the nearest of `school_names`
    (single assigned school = list of one). Returns {"km": {...}, "min": {...}} or None."""
    if not routes or not school_names or len(sub) == 0:
        return None
    kms, mins, ws = [], [], []
    for geoid, w in zip(sub["GEOID20"], sub["school_age_5_17"]):
        rec = routes.get(geoid)
        if not rec or w <= 0:
            continue
        pairs = [rec[s] for s in school_names if s in rec]
        if not pairs:
            continue
        kms.append(min(p[0] for p in pairs))
        mins.append(min(p[1] for p in pairs))
        ws.append(w)
    if not ws:
        return None
    return {"km": summarize(kms, ws, thresholds=(1, 2, 3)),
            "min": summarize(mins, ws, thresholds=min_thresholds)}

DRIVE_THR, WALK_THR = (5, 10, 15), (10, 20, 30)   # minute thresholds per profile

def zone_seg(sub):
    tot = float(sub["total"].sum())
    d = {"total_pop": int(tot)}
    for c, k in RACE.items():
        n = int(sub[c].sum())
        d[k] = round(n / tot * 100, 1) if tot > 0 else 0.0
        d[k + "_n"] = n
    return d

# district-wide reference mix (6 groups; 'other' = aian+nhpi+other) for the per-zone mix gap
import math as _math
_G6 = {"white": ["white_nh"], "asian": ["asian_nh"], "hispanic": ["hispanic"],
       "black": ["black_nh"], "twoplus": ["twoplus_nh"], "other": ["aian_nh", "nhpi_nh", "other_nh"]}
def district_ref(blocks):
    tot = float(blocks["total"].sum())
    return {g: sum(float(blocks[c].sum()) for c in cols) / tot for g, cols in _G6.items()}
def mix_gap(sub, ref):
    tot = float(sub["total"].sum())
    if tot <= 0:
        return None
    kl = 0.0
    for g, cols in _G6.items():
        p = sum(float(sub[c].sum()) for c in cols) / tot
        q = ref[g]
        if p > 0 and q > 0:
            kl += p * _math.log(p / q)
    return round(kl, 3)

def zone_housing(sa):
    w = sa["pop"].fillna(0).astype(float)
    def wm(col):
        v = sa[col]; m = v.notna() & (w > 0)
        return None if (m.sum() == 0 or w[m].sum() == 0) else int(round(float((v[m] * w[m]).sum() / w[m].sum())))
    return {"income": wm("med_hh_income"), "home_value": wm("med_home_value"), "rent": wm("med_gross_rent")}

def zone_lang(sa):
    tot = float(sa["lang_hh_total"].sum())
    if tot <= 0:
        return {"limited_pct": None}
    cnt = lambda c: int(round(sa[c].sum()))
    sp, ie, api, oth = cnt("spanish_lep_hh"), cnt("other_ie_lep_hh"), cnt("api_lep_hh"), cnt("other_lep_hh")
    lim = sp + ie + api + oth
    pc = lambda n: round(n / tot * 100, 1)
    return {"hh_total": int(tot), "limited_pct": pc(lim), "limited_n": lim,
            "spanish_pct": pc(sp), "spanish_n": sp, "other_ie_pct": pc(ie), "other_ie_n": ie,
            "api_pct": pc(api), "api_n": api, "other_pct": pc(oth), "other_n": oth}

REF = district_ref(blk)

# per-school enrollment (2024-25) + era capacity for the capacity impact, keyed by base name
def _base(nm):
    nm = str(nm).strip()
    for suf in [" Elementary School", " Elementary", " Middle School", " Middle",
                " Senior High School", " Senior High", " High School", " High"]:
        if nm.endswith(suf): return nm[:-len(suf)].strip()
    return nm
_enr = pd.read_csv(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"))
_enr["key"] = _enr["school_name"].map(_base).str.title()
# OSPI enrollment override (era C = 2023-24, consistent pre-K-5 basis; elementary only).
# 2023-24 (first post-consolidation year) replaces the shipped 2024-25 to drop a year of
# enrollment drift; middle/high fall through to NCES. See Final_Data/ospi/.
_OSPI_C = {}
with open(os.path.join(FDATA, "ospi", "ospi_elementary.csv"), encoding="utf-8") as _f:
    import csv as _csv
    for _r in _csv.DictReader(_f):
        if _r["year"] == "2023-24" and _r["all_students_prek5"]:
            _OSPI_C[_r["school"].strip().title()] = int(_r["all_students_prek5"])
_cap = pd.read_csv(os.path.join(FDATA, "capacity", "school_capacity_by_state.csv"))
_cap = _cap[_cap["state"] == "post_2023"]
_capby = {(str(r["school"]).strip().title(), str(r["level"]).strip()): r for r in _cap.to_dict("records")}
_LVLCODE = {"elementary": 1, "middle": 2, "high": 3}
def zone_capacity(nm, level):
    out = {}
    if level == "elementary" and nm in _OSPI_C:
        out["enroll"] = _OSPI_C[nm]; out["enroll_year"] = "2023-24"
    else:
        er = _enr[(_enr["key"] == nm) & (_enr["school_level"] == _LVLCODE[level])]
        if len(er) and pd.notna(er.iloc[0].get("2024-25")):
            out["enroll"] = int(er.iloc[0]["2024-25"]); out["enroll_year"] = "2024-25"
    cr = _capby.get((nm, level))
    if cr is not None and pd.notna(cr.get("permanent_capacity")):
        out["capacity"] = int(cr["permanent_capacity"])
        if out.get("enroll"): out["utilization"] = round(out["enroll"] / out["capacity"] * 100)
    return out or None

for level in LEVELS:
    fp = os.path.join(WEB, f"bellevue_{level}_zones.geojson")
    raw = json.load(open(fp))
    z = gpd.read_file(fp).to_crs(MCRS)
    bz = gpd.sjoin(bpts, z[["name", "geometry"]], predicate="within").drop(columns="index_right")
    az = apportion_acs(bz, acs)
    slevel = sc[sc.GradeLevel.astype(str).str.strip() == LEVEL_GRADE[level]]
    school_pt = dict(zip(slevel.nm, slevel.geometry))
    hosts = {c: host_points(level, c) for c in PROG_CATS}
    hosts = {c: p for c, p in hosts.items() if p}
    routes_d = load_routes(level, "driving")
    routes_w = load_routes(level, "walking")
    for feat in raw["features"]:
        nm = feat["properties"]["name"]
        sub, sa = bz[bz["name"] == nm], az[az["name"] == nm]
        feat["properties"]["kids_5_17"] = int(sub["school_age_5_17"].sum())
        feat["properties"]["seg"] = zone_seg(sub)
        feat["properties"]["mix_gap"] = mix_gap(sub, REF)
        feat["properties"]["cap"] = zone_capacity(nm, level)
        feat["properties"]["housing"] = zone_housing(sa)
        feat["properties"]["language"] = zone_lang(sa)
        t = dist_to_point(sub, school_pt.get(nm))
        if t:
            rd = road_stats(sub, routes_d, [nm], DRIVE_THR)
            if rd: t["road"] = rd
            rw = road_stats(sub, routes_w, [nm], WALK_THR)
            if rw: t["walk"] = rw
        feat["properties"]["travel"] = t
        progs = {}
        for c in hosts:
            d = dist_to_nearest(sub, hosts[c])
            if d:
                rd = road_stats(sub, routes_d, host_names(level, c), DRIVE_THR)
                if rd: d["road"] = rd
                rw = road_stats(sub, routes_w, host_names(level, c), WALK_THR)
                if rw: d["walk"] = rw
            progs[c] = d
        feat["properties"]["programs"] = progs
    json.dump(raw, open(fp, "w"))
    print(f"{level}: enriched {len(raw['features'])} zones (programs: {list(hosts)})")
    if level == "high":
        for feat in raw["features"]:
            p = feat["properties"]
            t = p["travel"]["avg"] if p["travel"] else None
            print(f"   {p['name']:10} pop={p['seg']['total_pop']:6} inc={p['housing']['income']} "
                  f"limEng%={p['language'].get('limited_pct')} travel_avg_km={t}")
print("done")
