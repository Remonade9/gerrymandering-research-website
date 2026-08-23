# -*- coding: utf-8 -*-
"""
Precompute DRIVING road distance + time from every populated census block to every school of each
level, via ORS Matrix API (chunked: ~34-44 block origins x all schools per request, <=50 locations).
Only blocks with school-age kids (5-17) > 0 are routed (they carry all the weight anyway).
Output: <data root>/routing/routes_driving_<level>.json  { GEOID20: { schoolName: [km, min] } }
Incremental: saves after each chunk; re-running skips already-routed blocks. ~100 requests total,
throttled under the 40/min limit.
"""
import os, sys, json, time
from pathlib import Path
import geopandas as gpd, requests

REPO = Path(__file__).resolve().parents[1]  # repo root
# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or REPO / "final_data")
FDATA = str(DATA_ROOT)
WEB = str(REPO / "data")                    # the site's built map layers (school points)
OUT = os.path.join(FDATA, "routing"); os.makedirs(OUT, exist_ok=True)
# OpenRouteService API key: env var ORS_API_KEY, or an ors_api_key.txt file in the data root
KEY = os.environ.get("ORS_API_KEY")
_keyfile = DATA_ROOT / "ors_api_key.txt"
if not KEY and _keyfile.exists():
    KEY = _keyfile.read_text().strip()
if not KEY:
    raise SystemExit("OpenRouteService API key required: set the ORS_API_KEY environment variable, "
                     f"or put the key in a file at {_keyfile}")
LEVELS = ["elementary", "middle", "high"]
PROFILE = sys.argv[1] if len(sys.argv) > 1 else "driving-car"   # or "foot-walking"
TAG = {"driving-car": "driving", "foot-walking": "walking"}[PROFILE]
print("profile:", PROFILE, "->", TAG)

age = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_age_2020.geojson"))
age = age[age["school_age_5_17"] > 0].copy()
pts = age.geometry.representative_point()
blocks = [(g, [round(p.x, 6), round(p.y, 6)]) for g, p in zip(age["GEOID20"], pts)]
print("blocks to route:", len(blocks))

def matrix(src_coords, dest_coords):
    body = {"locations": src_coords + dest_coords,
            "sources": list(range(len(src_coords))),
            "destinations": list(range(len(src_coords), len(src_coords) + len(dest_coords))),
            "metrics": ["distance", "duration"]}
    for a in range(6):
        r = requests.post(f"https://api.openrouteservice.org/v2/matrix/{PROFILE}",
                          headers={"Authorization": KEY, "Content-Type": "application/json"},
                          json=body, timeout=120)
        if r.status_code == 200:
            return r.json()
        time.sleep(5 if r.status_code == 429 else 3)
    raise RuntimeError(f"matrix failed: {r.status_code} {r.text[:200]}")

for level in LEVELS:
    sch = json.load(open(os.path.join(WEB, f"bellevue_{level}_schools.geojson")))
    dests = [(f["properties"]["name"], f["geometry"]["coordinates"]) for f in sch["features"]]
    chunk = 50 - len(dests)
    fp = os.path.join(OUT, f"routes_{TAG}_{level}.json")
    routes = json.load(open(fp)) if os.path.exists(fp) else {}
    todo = [b for b in blocks if b[0] not in routes]
    print(f"{level}: {len(dests)} schools, chunk={chunk}, todo={len(todo)}/{len(blocks)}")
    for i in range(0, len(todo), chunk):
        part = todo[i:i + chunk]
        j = matrix([c for _, c in part], [c for _, c in dests])
        for bi, (geoid, _) in enumerate(part):
            rec = {}
            for di, (name, _) in enumerate(dests):
                dist, dur = j["distances"][bi][di], j["durations"][bi][di]
                if dist is not None and dur is not None:
                    rec[name] = [round(dist / 1000, 3), round(dur / 60, 2)]
            routes[geoid] = rec
        json.dump(routes, open(fp, "w"))
        print(f"  {level} chunk {i // chunk + 1}/{(len(todo) + chunk - 1) // chunk} saved ({len(routes)} blocks)")
        time.sleep(1.8)   # stay under 40 req/min
    print(f"{level} DONE -> {fp}")
print("all done")
