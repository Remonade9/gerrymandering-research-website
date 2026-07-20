# -*- coding: utf-8 -*-
"""
Build web data for a historical district state, in the same shape as the State C files:
  bellevue_<S>_elementary_{zones,labels,schools}.geojson   for S in {a, b}
Only ELEMENTARY differs across states (middle/high boundaries unchanged - documented); the
frontend reuses the C middle/high files for states A/B.

  b = 2018-2023 (city GIS layer recovered from StateOfNeighborhoods service; 16 zones)
  a = pre-2018  (NCES SABS 2015-16; 15 zones after dropping Jing Mei/Puesta pseudo-zones;
                 cross-source caveat: coarser digitization than the city layers)

Zone props: name, compactness set (+within-state percentiles), kids_5_17, seg, housing,
language, travel (straight + road/walk from the extended route caches). Programs are OMITTED
for historical states (era program locations only partially documented - honesty rule).
School points use era-accurate NCES CCD lat/long (e.g. Jing Mei at its OLD site; Wilburton
at the building Jing Mei now occupies). Usage: python build_state.py a|b
"""
import os, sys, json, math
import numpy as np, pandas as pd, geopandas as gpd
from shapely import minimum_bounding_circle
from shapely.geometry.polygon import orient

S = (sys.argv[1] if len(sys.argv) > 1 else "b").lower()
assert S in ("a", "b")
WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
MCRS = 32610
ZONE_DIR = {"a": "(1) pre-2018", "b": "(2) 2018-2023"}[S]
CCD_YEAR = {"a": 2017, "b": 2022}[S]
ENR_COL = {"a": "2017-18", "b": "2022-23"}[S]
CAP_ERA = {"a": "pre_2018", "b": "2018_2023"}[S]

def base_name(s):
    s = str(s).strip()
    for suf in [" Elementary School", " Elementary", " Middle School", " Middle",
                " Senior High School", " Senior High", " High School", " High"]:
        if s.endswith(suf): return s[:-len(suf)].strip()
    return s

# ---------- zones ----------
fp = os.path.join(FDATA, "attendance zone boundaries", ZONE_DIR, "elementary.geojson")
g = gpd.read_file(fp)
if S == "b":
    g["name"] = g["NAME"].str.title()
else:
    g = g[~g["schnam"].str.contains("Jing Mei|Puesta", case=False)].copy()
    g["name"] = g["schnam"].map(base_name).str.title()
g = g[["name", "geometry"]].reset_index(drop=True)
if S == "a":
    # SABS geometries overrun the shoreline (extend into Lake WA / Lake Sammamish), distorting
    # compactness. Clip to the district boundary - which B and C already effectively match -
    # so all three eras share a consistent coastline. Raw SABS file left untouched.
    from shapely.ops import unary_union
    dist = gpd.read_file(os.path.join(FDATA, "attendance zone boundaries", "district_boundary.geojson")).to_crs(g.crs)
    dgeom = dist.union_all()
    def _clip(geom):
        inter = geom.intersection(dgeom)
        if inter.geom_type == "GeometryCollection":
            inter = unary_union([x for x in inter.geoms if x.geom_type in ("Polygon", "MultiPolygon")])
        return inter
    g["geometry"] = g.geometry.map(_clip)
    g = g[~g.geometry.is_empty].reset_index(drop=True)
    print("state a: zones clipped to district boundary (shoreline fix)")
print(f"state {S}: {len(g)} elementary zones:", sorted(g["name"]))

# ---------- compactness (same formulas as build_bellevue_basics) ----------
def _polar_moment(geom):
    A = Sx = Sy = Ixx = Iyy = 0.0
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        poly = orient(poly, 1.0)
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                cross = x0 * y1 - x1 * y0
                A += cross; Sx += (x0 + x1) * cross; Sy += (y0 + y1) * cross
                Ixx += (y0 * y0 + y0 * y1 + y1 * y1) * cross
                Iyy += (x0 * x0 + x0 * x1 + x1 * x1) * cross
    A *= 0.5
    cx, cy = (Sx / 6.0) / A, (Sy / 6.0) / A
    return A, (Ixx / 12.0 + Iyy / 12.0) - A * (cx * cx + cy * cy)

def compactness(geom):
    A, P = geom.area, geom.length
    pp = 4 * math.pi * A / (P * P) if P else 0
    Am, J = _polar_moment(geom)
    return {"area_km2": round(A / 1e6, 3), "perimeter_km": round(P / 1000, 2),
            "polsby_popper": round(pp, 3),
            "reock": round(A / minimum_bounding_circle(geom).area, 3),
            "convex_hull": round(A / geom.convex_hull.area, 3),
            "bounding_rect": round(A / geom.minimum_rotated_rectangle.area, 3),
            "moment_inertia": round((Am * Am) / (2 * math.pi * J) if J else 0, 3)}

def percentile_rank(values):
    v = np.asarray(values, dtype=float); n = len(v)
    return [round(float((np.sum(v < x) + 0.5 * np.sum(v == x)) / n * 100)) for x in v]

gm = g.to_crs(MCRS)
mets = [compactness(geom) for geom in gm.geometry]
for k in mets[0]:
    g[k] = [m[k] for m in mets]
g["pp_percentile"] = percentile_rank(g["polsby_popper"])
g["reock_percentile"] = percentile_rank(g["reock"])
g["convex_percentile"] = percentile_rank(g["convex_hull"])

# ---------- demographics / travel (same method as compute_impacts) ----------
blk = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_2020.geojson"))
agef = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_age_2020.geojson"))[["GEOID20", "school_age_5_17"]]
blk = blk.merge(agef, on="GEOID20", how="left"); blk["school_age_5_17"] = blk["school_age_5_17"].fillna(0)
blk = blk.to_crs(MCRS)
bpts = gpd.GeoDataFrame(blk.drop(columns="geometry"), geometry=blk.geometry.representative_point(), crs=MCRS)
acs = gpd.read_file(os.path.join(FDATA, "census", "2023", "blockgroups_acs2023.geojson")).to_crs(MCRS)

ACS_COUNT_COLS = ["lang_hh_total", "spanish_lep_hh", "other_ie_lep_hh", "api_lep_hh", "other_lep_hh"]

def apportion_acs(bz_assigned, acs_bg):
    """Population-apportion ACS block groups across zones (same as compute_impacts):
    straddling BGs contribute to each zone by their 2020 block-population share
    rather than being dumped whole into the zone holding their center point."""
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

zm = g.to_crs(MCRS)
bz = gpd.sjoin(bpts, zm[["name", "geometry"]], predicate="within").drop(columns="index_right")
az = apportion_acs(bz, acs)
print("blocks assigned:", bz["GEOID20"].nunique(), "/", len(bpts))

# era school points from CCD directory lat/long
raw = json.load(open(os.path.join(FDATA, "enrollment", "enrollment_raw.json")))
ccd = {}
for r in raw:
    if r["year"] == CCD_YEAR and r.get("latitude") and r.get("longitude"):
        ccd[base_name(r["school_name"]).title()] = [float(r["longitude"]), float(r["latitude"])]
school_ll = {n: ccd[n] for n in g["name"] if n in ccd}
missing = [n for n in g["name"] if n not in ccd]
if missing: print("WARNING - no CCD point for:", missing)
sp_m = gpd.GeoSeries(gpd.points_from_xy([v[0] for v in school_ll.values()], [v[1] for v in school_ll.values()]),
                     index=list(school_ll.keys()), crs=4326).to_crs(MCRS)
sp_all = gpd.GeoSeries(gpd.points_from_xy([v[0] for v in ccd.values()], [v[1] for v in ccd.values()]),
                       index=list(ccd.keys()), crs=4326).to_crs(MCRS)

RACE = {"white_nh": "white", "asian_nh": "asian", "hispanic": "hispanic", "black_nh": "black",
        "twoplus_nh": "twoplus", "aian_nh": "aian", "nhpi_nh": "nhpi", "other_nh": "other"}
_dt = float(blk["total"].sum())
DIST_REF = {"white": float(blk["white_nh"].sum()) / _dt, "asian": float(blk["asian_nh"].sum()) / _dt,
            "hispanic": float(blk["hispanic"].sum()) / _dt, "black": float(blk["black_nh"].sum()) / _dt,
            "twoplus": float(blk["twoplus_nh"].sum()) / _dt,
            "other": (float(blk["aian_nh"].sum()) + float(blk["nhpi_nh"].sum()) + float(blk["other_nh"].sum())) / _dt}

def summarize(d, w, thresholds=(1, 2, 3)):
    d = np.asarray(d, float); w = np.asarray(w, float)
    m = w > 0; d, w = d[m], w[m]
    if len(d) == 0 or w.sum() == 0: return None
    o = np.argsort(d); d, w = d[o], w[o]; cw = np.cumsum(w); tot = cw[-1]
    q = lambda p: float(d[min(int(np.searchsorted(cw, p * tot)), len(d) - 1)])
    xmax = float(d[-1]); N = 40
    ys = []
    for i in range(N + 1):
        idx = int(np.searchsorted(d, xmax * i / N, side="right"))
        ys.append(round(float(cw[idx - 1]) / tot * 100, 1) if idx > 0 else 0.0)
    out = {"avg": round(float((d * w).sum() / tot), 2), "min": round(float(d[0]), 2),
           "q1": round(q(.25), 2), "med": round(q(.5), 2), "q3": round(q(.75), 2),
           "max": round(xmax, 2), "n": int(round(tot)), "cdf": {"max": round(xmax, 2), "y": ys}}
    for t in thresholds: out[f"within{t}"] = round(float(w[d <= t].sum() / tot * 100), 1)
    return out

def load_routes(tag):
    fp2 = os.path.join(FDATA, "routing", f"routes_{tag}_elementary.json")
    return json.load(open(fp2)) if os.path.exists(fp2) else None
routes_d, routes_w = load_routes("driving"), load_routes("walking")

def road_stats(sub, routes, names, thr):
    if not routes or not names or len(sub) == 0: return None
    kms, mins, ws = [], [], []
    for geoid, w in zip(sub["GEOID20"], sub["school_age_5_17"]):
        rec = routes.get(geoid)
        if not rec or w <= 0: continue
        pairs = [rec[n] for n in names if n in rec]
        if not pairs: continue
        kms.append(min(p[0] for p in pairs)); mins.append(min(p[1] for p in pairs)); ws.append(w)
    if not ws: return None
    return {"km": summarize(kms, ws, (1, 2, 3)), "min": summarize(mins, ws, thr)}

def rnd(o):
    if isinstance(o, float): return round(o, 5)
    if isinstance(o, list): return [rnd(x) for x in o]
    return o

# ---------- era program hosting (State B only: direct Oct-2022 documentation) ----------
# pre-2018 slice is knowingly incomplete (2010 anchors) -> nearest-distance would overstate; omit for A.
PROG_CATS = ["advanced_learning", "language_immersion", "special_education"]
ROUTE_KEY = {"Jing Mei": "Jing Mei Old"}   # B-era Jing Mei = its old site (routed separately)
era_hosts = {}          # category -> [names]
prog_rows_by_host = {}  # host -> [{program, category}]
if S == "b":
    ph = pd.read_csv(os.path.join(FDATA, "programs", "program_hosting_by_state.csv"))
    ph = ph[(ph["state"] == "2018_2023") & (ph["level"] == "elementary") & (ph["category"].isin(PROG_CATS))]
    for _, r in ph.iterrows():
        h = str(r["host_school"]).strip().title()
        era_hosts.setdefault(r["category"], [])
        if h not in era_hosts[r["category"]]: era_hosts[r["category"]].append(h)
        prog_rows_by_host.setdefault(h, []).append({"program": str(r["program"]).strip(), "category": str(r["category"]).strip(), "note": ""})

def era_programs(sub):
    if S != "b" or not era_hosts or len(sub) == 0:
        return {}
    out = {}
    for cat, names in era_hosts.items():
        pts_c = [sp_all[n] for n in names if n in sp_all.index]   # NB: bare `in` on a GeoSeries is SPATIAL
        if not pts_c: continue
        import numpy as _np
        dmin = None
        for ptc in pts_c:
            dd = sub.geometry.distance(ptc).values
            dmin = dd if dmin is None else _np.minimum(dmin, dd)
        d = summarize(dmin / 1000.0, sub["school_age_5_17"].values)
        if not d: continue
        rkeys = [ROUTE_KEY.get(n, n) for n in names]
        rd = road_stats(sub, routes_d, rkeys, (5, 10, 15))
        if rd: d["road"] = rd
        rw = road_stats(sub, routes_w, rkeys, (10, 20, 30))
        if rw: d["walk"] = rw
        out[cat] = d
    return out

# era enrollment + capacity for the capacity impact (also reused by the schools section below)
enr = pd.read_csv(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"))
enr["key"] = enr["school_name"].map(base_name).str.title()
enr_by = {r["key"]: r for r in enr[enr["school_level"] == 1].to_dict("records")}
# OSPI enrollment override: consistent pre-K-5 basis (elementary only; NCES is inconsistent
# on Pre-K, which had made Wilburton look falsely "emptiest"). Non-elementary schools are
# absent from the OSPI file, so they fall through to the NCES record. See Final_Data/ospi/.
import csv as _csv
_ospi = {}
_RACE6 = {"white": "white", "asian": "asian", "hispanic": "hispanic",
          "black": "black", "two_or_more": "twoplus", "other": "other"}
with open(os.path.join(FDATA, "ospi", "ospi_elementary.csv"), encoding="utf-8") as _f:
    for _r in _csv.DictReader(_f):
        if _r["year"] == ENR_COL and _r["all_students_prek5"]:
            _ospi[_r["school"].strip().title()] = {
                "year": ENR_COL,
                "n": int(_r["all_students_prek5"]),
                "k5": int(_r["k5"] or 0),
                "race": {v: int(_r[k] or 0) for k, v in _RACE6.items()},
                "low_income": int(_r["low_income"] or 0),
                "ell": int(_r["ell"] or 0),
                "highly_capable": int(_r["highly_capable"] or 0),
                "iep": int(_r["iep_swd"] or 0),
            }
def era_enroll(nm):
    """(enroll, year): OSPI pre-K-5 total preferred, NCES fallback."""
    if nm in _ospi:
        return _ospi[nm]["n"], ENR_COL
    er = enr_by.get(nm)
    if er is not None and pd.notna(er.get(ENR_COL)):
        return int(er[ENR_COL]), ENR_COL
    return None, None
cap = pd.read_csv(os.path.join(FDATA, "capacity", "school_capacity_by_state.csv"))
cap = cap[(cap["state"] == CAP_ERA) & (cap["level"] == "elementary")]
cap_by = {str(r["school"]).strip().title(): r for r in cap.to_dict("records")}
def zone_capacity(nm):
    out = {}
    en, yr = era_enroll(nm)
    if en is not None:
        out["enroll"] = en; out["enroll_year"] = yr
    # utilization uses K-5 (matches the K-5 capacity); enroll stays pre-K-5 for display + all else
    k5v = _ospi.get(nm, {}).get("k5")
    if k5v is not None:
        out["k5"] = k5v
    cr = cap_by.get(nm)
    if cr is not None and pd.notna(cr.get("permanent_capacity")):
        out["capacity"] = int(cr["permanent_capacity"])
        basis = k5v if k5v is not None else out.get("enroll")
        if basis: out["utilization"] = round(basis / out["capacity"] * 100)
    return out or None

feats = []
for _, row in g.to_crs(4326).iterrows():
    nm = row["name"]
    sub, sa = bz[bz["name"] == nm], az[az["name"] == nm]
    p = {k: row[k] for k in ["name", "area_km2", "perimeter_km", "polsby_popper", "reock",
                             "convex_hull", "bounding_rect", "moment_inertia",
                             "pp_percentile", "reock_percentile", "convex_percentile"]}
    p["kids_5_17"] = int(sub["school_age_5_17"].sum())
    tot = float(sub["total"].sum()); seg = {"total_pop": int(tot)}
    for c, k in RACE.items():
        n = int(sub[c].sum()); seg[k] = round(n / tot * 100, 1) if tot > 0 else 0.0; seg[k + "_n"] = n
    p["seg"] = seg
    # mix gap: KL divergence of the zone's 6-group mix from the district-wide mix (0 = mirrors district)
    if tot > 0:
        kl = 0.0
        for grp, cols in {"white": ["white_nh"], "asian": ["asian_nh"], "hispanic": ["hispanic"],
                          "black": ["black_nh"], "twoplus": ["twoplus_nh"],
                          "other": ["aian_nh", "nhpi_nh", "other_nh"]}.items():
            pp = sum(float(sub[c].sum()) for c in cols) / tot
            qq = DIST_REF[grp]
            if pp > 0 and qq > 0:
                kl += pp * math.log(pp / qq)
        p["mix_gap"] = round(kl, 3)
    else:
        p["mix_gap"] = None
    wpop = sa["pop"].fillna(0).astype(float)
    def wm(col):
        v = sa[col]; m = v.notna() & (wpop > 0)
        return None if (m.sum() == 0 or wpop[m].sum() == 0) else int(round(float((v[m] * wpop[m]).sum() / wpop[m].sum())))
    p["housing"] = {"income": wm("med_hh_income"), "home_value": wm("med_home_value"), "rent": wm("med_gross_rent")}
    lt = float(sa["lang_hh_total"].sum())
    if lt > 0:
        cnt = lambda c: int(round(sa[c].sum()))
        spn, ie, api, oth = cnt("spanish_lep_hh"), cnt("other_ie_lep_hh"), cnt("api_lep_hh"), cnt("other_lep_hh")
        lim = spn + ie + api + oth; pc = lambda n: round(n / lt * 100, 1)
        p["language"] = {"hh_total": int(lt), "limited_pct": pc(lim), "limited_n": lim,
                         "spanish_pct": pc(spn), "spanish_n": spn, "other_ie_pct": pc(ie), "other_ie_n": ie,
                         "api_pct": pc(api), "api_n": api, "other_pct": pc(oth), "other_n": oth}
    else:
        p["language"] = {"limited_pct": None}
    t = None
    if nm in sp_m.index and len(sub):
        t = summarize((sub.geometry.distance(sp_m[nm]) / 1000.0).values, sub["school_age_5_17"].values)
        if t:
            rd = road_stats(sub, routes_d, [nm], (5, 10, 15))
            if rd: t["road"] = rd
            rw = road_stats(sub, routes_w, [nm], (10, 20, 30))
            if rw: t["walk"] = rw
    p["travel"] = t
    p["programs"] = era_programs(sub)   # B: documented Oct-2022 hosting; A: omitted (incomplete map)
    p["cap"] = zone_capacity(nm)
    geom = json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"]
    geom["coordinates"] = rnd(geom["coordinates"])
    feats.append({"type": "Feature", "properties": p, "geometry": geom})

json.dump({"type": "FeatureCollection", "features": feats},
          open(os.path.join(WEB, f"bellevue_{S}_elementary_zones.geojson"), "w"))

# labels
lab = g.to_crs(4326).copy(); lab["geometry"] = gpd.GeoDataFrame(g, crs=g.crs).to_crs(4326).geometry.representative_point()
lfeats = [{"type": "Feature", "properties": {"name": r["name"]},
           "geometry": {"type": "Point", "coordinates": [round(r.geometry.x, 5), round(r.geometry.y, 5)]}}
          for _, r in lab.iterrows()]
json.dump({"type": "FeatureCollection", "features": lfeats},
          open(os.path.join(WEB, f"bellevue_{S}_elementary_labels.geojson"), "w"))

# ---------- schools (era-accurate points + era info; reuses enr_by/cap_by above) ----------
ROLE = {"b": {"Wilburton": "opened fall 2018; closed in the 2023 consolidation at the end of this era",
              "Eastgate": "closed in the 2023 consolidation at the end of this era"},
        "a": {"Eastgate": "later closed in the 2023 consolidation"}}[S]
sfeats = []
def school_feat(nm, kind, display, type_label):
    ll = ccd.get(nm)
    if not ll: return None
    info = {"programs": []}
    en, yr = era_enroll(nm)
    if en is not None:
        info["enroll_current"] = en; info["enroll_year"] = yr
    if nm in _ospi:
        info["ospi"] = _ospi[nm]   # enrolled-student demographics for the pin
    cr = cap_by.get(nm)
    if cr is not None and pd.notna(cr.get("permanent_capacity")):
        info["capacity"] = int(cr["permanent_capacity"])
        if info.get("enroll_current"): info["utilization"] = round(info["enroll_current"] / info["capacity"] * 100)
    if nm in ROLE: info["role"] = ROLE[nm]
    if prog_rows_by_host.get(nm): info["programs"] = prog_rows_by_host[nm]
    return {"type": "Feature",
            "properties": {"name": nm, "kind": kind, "display": display, "type_label": type_label, "info": info},
            "geometry": {"type": "Point", "coordinates": [round(ll[0], 6), round(ll[1], 6)]}}
for nm in sorted(g["name"]):
    f = school_feat(nm, "main", f"{nm} Elementary", "Attendance-area school")
    if f: sfeats.append(f)
for nm in ["Jing Mei", "Puesta Del Sol"]:
    f = school_feat(nm, "choice", f"{nm} Elementary", "Choice / immersion school")
    if f: sfeats.append(f)
json.dump({"type": "FeatureCollection", "features": sfeats},
          open(os.path.join(WEB, f"bellevue_{S}_elementary_schools.geojson"), "w"))
print(f"schools: {len(sfeats)} ({sum(1 for f in sfeats if f['properties']['kind']=='main')} main)")
for f in sfeats[:4]:
    i = f["properties"]["info"]
    print("  ", f["properties"]["name"], "| enroll", i.get("enroll_current"), "| cap", i.get("capacity"), "| util", i.get("utilization"))
print("done state", S)
