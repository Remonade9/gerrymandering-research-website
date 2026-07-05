# build_changes.py - data for the Boundary Changes tab.
#
# For each rezoning event (2018: A->B, 2023: B->C) computes the moved territory:
# the polygons whose elementary assignment changed, dissolved per (from,to) flow,
# with the people living there (fixed 2020 census blocks, same design as the main
# tool), travel before/after from the per-era ORS route caches, and (2023 only)
# nearest-program access before/after from the verified per-era hosting table.
#
# Outputs (Website/data):
#   changes_2018.geojson   moved-territory pieces, cross_source-flagged + sliver-filtered
#   changes_2023.geojson   moved-territory pieces
#   changes_flows.json     arrow endpoints, program moves, ghost pins, totals, district shares
#
# 2018 caveat: State A geometry is federal SABS (cross-source), so tiny edge
# slivers between same-named zones are source noise, not real reassignments.
# Pieces below MIN_AREA_KM2_2018 *and* below MIN_KIDS_2018 are dropped.

import json, csv, os
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "..", "..", "Main - Gerrymandering", "Final_Data")
METRIC = "EPSG:32610"

MIN_AREA_KM2_2018 = 0.05
MIN_KIDS_2018 = 10
# both events: drop pure snapping slivers (near-zero area, nobody lives there)
MIN_AREA_KM2_ANY = 0.03

ZONES = {
    "a": "bellevue_a_elementary_zones.geojson",
    "b": "bellevue_b_elementary_zones.geojson",
    "c": "bellevue_elementary_zones.geojson",
}
SCHOOLS = {
    "a": "bellevue_a_elementary_schools.geojson",
    "b": "bellevue_b_elementary_schools.geojson",
    "c": "bellevue_elementary_schools.geojson",
}

# route-cache key per era for schools whose site moved
ROUTE_KEY = {
    "b": {"Jing Mei": "Jing Mei Old", "Puesta del Sol": "Puesta Del Sol"},
    "c": {"Jing Mei": "Jing Mei", "Puesta del Sol": "Puesta Del Sol"},
}
PROG_CATS = {
    "advanced_learning": "Advanced Learning",
    "language_immersion": "Dual-language immersion",
    "special_education": "Site-based special education",
}


def load_zones(state):
    g = gpd.read_file(os.path.join(HERE, ZONES[state]))[["name", "geometry"]]
    return g.to_crs(METRIC)


def load_blocks():
    age = gpd.read_file(os.path.join(FD, "census", "2020", "census_blocks_age_2020.geojson"))
    race = gpd.read_file(os.path.join(HERE, "bellevue_blocks_race.geojson"))
    # positional join is safe: files were built from the same block pull in the same order
    assert len(age) == len(race)
    for col in ["pop", "w", "a", "h", "b"]:
        age[col] = race[col].values
    age["pt"] = [Point(float(lon), float(lat)) for lon, lat in zip(age["INTPTLON20"], age["INTPTLAT20"])]
    pts = gpd.GeoDataFrame(age.drop(columns=["geometry", "pt"]), geometry=age["pt"], crs="EPSG:4326").to_crs(METRIC)
    return pts


def load_routes():
    out = {}
    for prof in ["driving", "walking"]:
        with open(os.path.join(FD, "routing", f"routes_{prof}_elementary.json"), encoding="utf-8") as f:
            out[prof] = json.load(f)
    return out


def load_program_hosts():
    hosts = {"b": {}, "c": {}}
    state_key = {"2018_2023": "b", "post_2023": "c"}
    with open(os.path.join(FD, "programs", "program_hosting_by_state.csv"), encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            st = state_key.get(row["state"])
            if not st or row["level"] != "elementary" or row["category"] not in PROG_CATS:
                continue
            era = hosts[st].setdefault(row["category"], set())
            era.add(ROUTE_KEY[st].get(row["host_school"], row["host_school"]))
    return hosts


def wmean(pairs):
    """pairs = [(value, weight)]; weight fallback 1 if all zero."""
    pairs = [(v, w) for v, w in pairs if v is not None]
    if not pairs:
        return None
    tw = sum(w for _, w in pairs)
    if tw == 0:
        return round(sum(v for v, _ in pairs) / len(pairs), 2)
    return round(sum(v * w for v, w in pairs) / tw, 2)


def travel_stats(blocks, school, routes):
    """Pop-weighted mean road km / drive min / walk min from blocks to one school."""
    drv, wlk = routes["driving"], routes["walking"]
    km, dmin, wmin = [], [], []
    for _, b in blocks.iterrows():
        g = b["GEOID20"]
        wgt = b["school_age_5_17"]
        r = drv.get(g, {}).get(school)
        if r:
            km.append((r[0], wgt)); dmin.append((r[1], wgt))
        r = wlk.get(g, {}).get(school)
        if r:
            wmin.append((r[1], wgt))
    return {"road_km": wmean(km), "drive_min": wmean(dmin), "walk_min": wmean(wmin)}


def nearest_program_stats(blocks, hosts, routes):
    """Per category: pop-weighted mean of each block's nearest-host drive distance/time."""
    drv = routes["driving"]
    out = {}
    for cat, sites in hosts.items():
        km, mins = [], []
        for _, b in blocks.iterrows():
            row = drv.get(b["GEOID20"], {})
            best = None
            for s in sites:
                r = row.get(s)
                if r and (best is None or r[0] < best[0]):
                    best = r
            if best:
                wgt = b["school_age_5_17"]
                km.append((best[0], wgt)); mins.append((best[1], wgt))
        out[cat] = {"road_km": wmean(km), "drive_min": wmean(mins)}
    return out


def build_event(ev, before_st, after_st, blocks, routes, prog_hosts, nbh):
    zb, za = load_zones(before_st), load_zones(after_st)
    inter = gpd.overlay(
        zb.rename(columns={"name": "from"}),
        za.rename(columns={"name": "to"}),
        how="intersection", keep_geom_type=True)
    moved = inter[inter["from"] != inter["to"]]
    if moved.empty:
        return [], {}
    pieces = moved.dissolve(by=["from", "to"], as_index=False)
    pieces["area_km2"] = pieces.geometry.area / 1e6

    feats, flow_rows = [], []
    for _, p in pieces.iterrows():
        sub = blocks[blocks.within(p.geometry)]
        kids = int(sub["school_age_5_17"].sum())
        if p["area_km2"] < MIN_AREA_KM2_ANY and kids == 0:
            continue
        if ev == "2018" and p["area_km2"] < MIN_AREA_KM2_2018 and kids < MIN_KIDS_2018:
            continue
        pop = int(sub["pop"].sum())
        race = {}
        for grp in ["w", "a", "h", "b"]:
            cnt = float((sub[grp] / 100.0 * sub["pop"]).sum())
            race[grp] = round(100 * cnt / pop, 1) if pop else None
        # neighborhoods the piece overlaps meaningfully
        pn = []
        for _, nrow in nbh.iterrows():
            ov = p.geometry.intersection(nrow.geometry).area / 1e6
            if ov > 0.02 and ov > 0.04 * p["area_km2"]:
                pn.append(nrow["name"])
        props = {
            "event": ev,
            "from": p["from"], "to": p["to"],
            "area_km2": round(p["area_km2"], 2),
            "n_blocks": int(len(sub)),
            "pop": pop, "kids": kids,
            "age_5_9": int(sub["age_5_9"].sum()),
            "race": race,
            "travel_before": travel_stats(sub, p["from"], routes),
            "travel_after": travel_stats(sub, p["to"], routes),
            "neighborhoods": pn,
        }
        if ev == "2023":
            props["cross_source"] = False
            props["programs_before"] = nearest_program_stats(sub, prog_hosts["b"], routes)
            props["programs_after"] = nearest_program_stats(sub, prog_hosts["c"], routes)
        else:
            props["cross_source"] = True
        geom = gpd.GeoSeries([p.geometry], crs=METRIC).to_crs("EPSG:4326").iloc[0]
        feats.append({"type": "Feature", "properties": props,
                      "geometry": json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]})
        flow_rows.append({"from": p["from"], "to": p["to"], "kids": kids,
                          "pop": pop, "area_km2": round(p["area_km2"], 2)})
    return feats, flow_rows


def school_xy(state):
    g = gpd.read_file(os.path.join(HERE, SCHOOLS[state]))
    return {r["name"]: [round(r.geometry.x, 6), round(r.geometry.y, 6)] for _, r in g.iterrows()}


def main():
    blocks = load_blocks()
    routes = load_routes()
    prog_hosts = load_program_hosts()
    nbh = gpd.read_file(os.path.join(HERE, "bellevue_neighborhoods.geojson"))[["name", "geometry"]].to_crs(METRIC)

    events = {"2018": ("a", "b"), "2023": ("b", "c")}
    flows_out = {}
    for ev, (b_st, a_st) in events.items():
        feats, flow_rows = build_event(ev, b_st, a_st, blocks, routes, prog_hosts, nbh)
        out = {"type": "FeatureCollection", "features": feats}
        fn = os.path.join(HERE, f"changes_{ev}.geojson")
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(out, f)
        xy_b, xy_a = school_xy(b_st), school_xy(a_st)
        for fr in flow_rows:
            fr["from_xy"] = xy_b.get(fr["from"])
            fr["to_xy"] = xy_a.get(fr["to"])
        tot = {
            "pieces": len(flow_rows),
            "area_km2": round(sum(f["area_km2"] for f in flow_rows), 2),
            "kids": sum(f["kids"] for f in flow_rows),
            "pop": sum(f["pop"] for f in flow_rows),
        }
        flows_out[ev] = {"flows": sorted(flow_rows, key=lambda r: -r["kids"]), "totals": tot}
        print(f"[{ev}] {len(feats)} pieces | {tot['area_km2']} km2 | {tot['kids']} kids (5-17)")
        for fr in flows_out[ev]["flows"]:
            print(f"   {fr['from']:>16} -> {fr['to']:<16} {fr['area_km2']:>6} km2  {fr['kids']:>5} kids")

    # program moves + ghost pins + school-site move (2023, from verified hosting table)
    xy_b, xy_c = school_xy("b"), school_xy("c")
    flows_out["2023"]["program_moves"] = [
        {"label": "Advanced Learning", "from": "Spiritridge", "to": "Woodridge",
         "from_xy": xy_b["Spiritridge"], "to_xy": xy_c["Woodridge"]},
        {"label": "Olympic program", "from": "Eastgate", "to": "Spiritridge",
         "from_xy": xy_b["Eastgate"], "to_xy": xy_c["Spiritridge"]},
        {"label": "Jing Mei (school moved)", "from": "Jing Mei", "to": "Wilburton building",
         "from_xy": xy_b["Jing Mei"], "to_xy": xy_b["Wilburton"]},
    ]
    flows_out["2023"]["ghosts"] = [
        {"name": "Wilburton Elementary", "xy": xy_b["Wilburton"],
         "note": "Opened fall 2018; closed June 2023 in the consolidation. Final-year enrollment 350 (2022-23), capacity 650. The building now houses Jing Mei Elementary."},
        {"name": "Eastgate Elementary", "xy": xy_b["Eastgate"],
         "note": "Closed June 2023 in the consolidation. Final-year enrollment 316 (2022-23), capacity 529. Hosted the Olympic program, which moved to Spiritridge."},
    ]
    flows_out["2018"]["program_moves"] = []
    flows_out["2018"]["ghosts"] = []
    flows_out["2018"]["opened"] = [
        {"name": "Wilburton Elementary", "xy": xy_b["Wilburton"],
         "note": "Opened fall 2018 to relieve elementary overcrowding; its zone was assembled from neighboring zones."}
    ]

    # program host sites with era-correct coordinates (for the personal pin's
    # nearest-program before/after; era school files already place Jing Mei at
    # its era-correct site)
    def host_sites(state_key):
        state_name = {"b": "2018_2023", "c": "post_2023"}[state_key]
        xy = {k.lower(): v for k, v in school_xy(state_key).items()}
        out = {}
        with open(os.path.join(FD, "programs", "program_hosting_by_state.csv"), encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["state"] != state_name or row["level"] != "elementary" or row["category"] not in PROG_CATS:
                    continue
                c = xy.get(row["host_school"].lower())
                if not c:
                    continue
                lst = out.setdefault(row["category"], [])
                if not any(h["name"] == row["host_school"] for h in lst):
                    lst.append({"name": row["host_school"], "xy": c})
        return out
    flows_out["program_hosts"] = {"b": host_sites("b"), "c": host_sites("c")}

    # district-wide race shares (pop-weighted, for panel comparison bars)
    pop = blocks["pop"].sum()
    flows_out["district_race"] = {
        g: round(100 * float((blocks[g] / 100.0 * blocks["pop"]).sum()) / pop, 1)
        for g in ["w", "a", "h", "b"]
    }

    with open(os.path.join(HERE, "changes_flows.json"), "w", encoding="utf-8") as f:
        json.dump(flows_out, f, indent=1)
    print("wrote changes_flows.json")


if __name__ == "__main__":
    main()
