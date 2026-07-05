"""Build Bellevue elementary attendance-area GeoJSON with Polsby-Popper compactness.

Source : City of Bellevue GIS, "Attendance Areas (Elementary School)" feature
         service (the elementary catchment zones inside Bellevue School District).
Output : data/bellevue_elementary.geojson  (zones + PP, rank, areas)

Same projection-correct Polsby-Popper as build_school_districts.py:
PP = 4*pi*A / P^2 on the sphere (spherical-excess area, haversine perimeter).
Pure standard library.  Run:  python data/build_bellevue_elementary.py
"""
import json
import math
import os
import time
import urllib.request

R = 6371008.8  # mean Earth radius (m), IUGG

SERVICE = (
    "https://services1.arcgis.com/EYzEZbDhXZjURPbP/arcgis/rest/services/"
    "Attendance_Areas_%28Elementary_School%29/FeatureServer/1/query"
    "?where=1%3D1&outFields=NAME,ESDIST_ID&returnGeometry=true&outSR=4326&f=geojson"
)
RAW_CACHE = "data/_bel_raw.geojson"

def fetch():
    if os.path.exists(RAW_CACHE):
        return json.load(open(RAW_CACHE))
    # The City of Bellevue host occasionally resets the TLS connection; retry.
    last = None
    for attempt in range(6):
        try:
            req = urllib.request.Request(SERVICE, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise SystemExit(f"Could not fetch attendance areas after retries: {last}")

def _rings_to_polys(geom):
    if geom["type"] == "Polygon":
        yield geom["coordinates"]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly

def ring_area(ring):
    if len(ring) < 4:
        return 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return total * R * R / 2.0

def ring_perimeter(ring):
    p = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        p += 2 * R * math.asin(min(1.0, math.sqrt(a)))
    return p

def area_perimeter(geom):
    area = perim = 0.0
    for poly in _rings_to_polys(geom):
        area += abs(ring_area(poly[0]))
        for hole in poly[1:]:
            area -= abs(ring_area(hole))
        perim += ring_perimeter(poly[0])
    return area, perim

def titlecase(s):
    return " ".join(w.capitalize() for w in (s or "").split())

raw = fetch()
feats = [f for f in raw["features"] if f.get("geometry")]
for f in feats:
    a, p = area_perimeter(f["geometry"])
    pp = (4 * math.pi * a) / (p * p) if p > 0 else 0.0
    props = f["properties"]
    f["properties"] = {
        "NAME": titlecase(props.get("NAME")),
        "ESDIST_ID": props.get("ESDIST_ID"),
        "PP": round(pp, 4),
        "area_km2": round(a / 1e6, 1),
        "perimeter_km": round(p / 1e3, 1),
    }

feats.sort(key=lambda f: f["properties"]["PP"])  # rank 1 = least compact
for i, f in enumerate(feats, start=1):
    f["properties"]["rank"] = i

json.dump({"type": "FeatureCollection", "features": feats},
          open("data/bellevue_elementary.geojson", "w"))

print(f"Wrote {len(feats)} Bellevue elementary attendance areas\n")
print(f"{'rank':>4}  {'PP':>6}  {'area_km2':>9}  zone")
for f in feats:
    pr = f["properties"]
    print(f"{pr['rank']:>4}  {pr['PP']:>6.3f}  {pr['area_km2']:>9.1f}  {pr['NAME']}")
