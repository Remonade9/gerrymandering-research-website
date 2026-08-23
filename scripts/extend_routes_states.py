# -*- coding: utf-8 -*-
"""
Extend the ELEMENTARY route caches for States A/B:
  - 'Wilburton'  = alias of 'Jing Mei' (Jing Mei moved INTO the Wilburton building in 2023,
                   so the current Jing Mei destination IS the Wilburton building - already routed)
  - 'Eastgate'   = new ORS matrix runs to the Eastgate building (no city site point exists;
                   coords from NCES CCD directory: -122.137628, 47.570069)
Adds keys in-place to routes_{driving,walking}_elementary.json. ~42 requests total.
"""
import os, json, time
from pathlib import Path
import geopandas as gpd, requests

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
FDATA = str(DATA_ROOT)
OUT = os.path.join(FDATA, "routing")
# OpenRouteService API key: env var ORS_API_KEY, or an ors_api_key.txt file in the data root
KEY = os.environ.get("ORS_API_KEY")
_keyfile = DATA_ROOT / "ors_api_key.txt"
if not KEY and _keyfile.exists():
    KEY = _keyfile.read_text().strip()
if not KEY:
    raise SystemExit("OpenRouteService API key required: set the ORS_API_KEY environment variable, "
                     f"or put the key in a file at {_keyfile}")
EASTGATE = [-122.137628, 47.570069]

age = gpd.read_file(os.path.join(FDATA, "census", "2020", "census_blocks_age_2020.geojson"))
age = age[age["school_age_5_17"] > 0]
pts = age.geometry.representative_point()
blocks = [(g, [round(p.x, 6), round(p.y, 6)]) for g, p in zip(age["GEOID20"], pts)]

def matrix(profile, src_coords, dest_coords):
    body = {"locations": src_coords + dest_coords,
            "sources": list(range(len(src_coords))),
            "destinations": list(range(len(src_coords), len(src_coords) + len(dest_coords))),
            "metrics": ["distance", "duration"]}
    for a in range(6):
        r = requests.post(f"https://api.openrouteservice.org/v2/matrix/{profile}",
                          headers={"Authorization": KEY, "Content-Type": "application/json"},
                          json=body, timeout=120)
        if r.status_code == 200:
            return r.json()
        time.sleep(6 if r.status_code == 429 else 3)
    raise RuntimeError(f"matrix failed: {r.status_code} {r.text[:200]}")

for tag, profile in [("driving", "driving-car"), ("walking", "foot-walking")]:
    fp = os.path.join(OUT, f"routes_{tag}_elementary.json")
    routes = json.load(open(fp))
    # Wilburton alias
    n_alias = 0
    for geoid, rec in routes.items():
        if "Jing Mei" in rec and "Wilburton" not in rec:
            rec["Wilburton"] = list(rec["Jing Mei"]); n_alias += 1
    # Eastgate matrix
    todo = [b for b in blocks if b[0] in routes and "Eastgate" not in routes[b[0]]]
    print(f"{tag}: aliased Wilburton for {n_alias} blocks; Eastgate todo {len(todo)}")
    CH = 49
    for i in range(0, len(todo), CH):
        part = todo[i:i + CH]
        j = matrix(profile, [c for _, c in part], [EASTGATE])
        for bi, (geoid, _) in enumerate(part):
            dist, dur = j["distances"][bi][0], j["durations"][bi][0]
            if dist is not None and dur is not None:
                routes[geoid]["Eastgate"] = [round(dist / 1000, 3), round(dur / 60, 2)]
        json.dump(routes, open(fp, "w"))
        print(f"  {tag} chunk {i // CH + 1}/{(len(todo) + CH - 1) // CH}")
        time.sleep(1.8)
    print(f"{tag} DONE")
print("all done")
