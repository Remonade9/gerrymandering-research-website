"""Build King County school-district GeoJSON with Polsby-Popper compactness.

Source : U.S. Census TIGERweb, current unified school districts (downloaded
         live; greater-Seattle envelope), clipped to King County via
         data/counties.geojson.
Output : data/school_districts.geojson  (King County districts + PP, rank, areas)

Polsby-Popper = 4*pi*A / P^2, computed on the sphere so it is
projection-correct: spherical excess for area, haversine for perimeter.
Pure standard library -- no geopandas/shapely needed.  Run:  python data/build_school_districts.py
"""
import json
import math
import os
import urllib.request

R = 6371008.8  # mean Earth radius (m), IUGG

TIGER_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/School/MapServer/0/query"
    "?where=STATE%3D'53'"
    "&geometry=-122.55,47.08,-121.05,47.80&geometryType=esriGeometryEnvelope&inSR=4326"
    "&spatialRel=esriSpatialRelIntersects"
    "&outFields=NAME,GEOID,BASENAME&returnGeometry=true&outSR=4326&f=geojson"
)
RAW_CACHE = "data/_sd_raw.geojson"

def fetch_raw():
    if os.path.exists(RAW_CACHE):
        return json.load(open(RAW_CACHE))
    print("Downloading school districts from Census TIGERweb ...")
    with urllib.request.urlopen(TIGER_URL) as r:
        return json.loads(r.read().decode("utf-8"))

def _rings_to_polys(geom):
    """Yield list-of-rings (ring 0 = exterior) for each polygon part."""
    t = geom["type"]
    if t == "Polygon":
        yield geom["coordinates"]
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly

def ring_area(ring):
    """Signed spherical area of a ring (m^2)."""
    if len(ring) < 4:
        return 0.0
    total = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return total * R * R / 2.0

def ring_perimeter(ring):
    """Geodesic (haversine) perimeter of a ring (m)."""
    p = 0.0
    for i in range(len(ring) - 1):
        lon1, lat1 = math.radians(ring[i][0]), math.radians(ring[i][1])
        lon2, lat2 = math.radians(ring[i + 1][0]), math.radians(ring[i + 1][1])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        p += 2 * R * math.asin(min(1.0, math.sqrt(a)))
    return p

def area_perimeter(geom):
    """Total area (exterior minus holes) and exterior perimeter for a geometry."""
    area = 0.0
    perim = 0.0
    for poly in _rings_to_polys(geom):
        area += abs(ring_area(poly[0]))
        for hole in poly[1:]:
            area -= abs(ring_area(hole))
        perim += ring_perimeter(poly[0])  # PP convention: exterior boundary
    return area, perim

def representative_point(geom):
    """Centroid-ish point of the largest part's exterior ring."""
    best = None
    best_area = -1
    for poly in _rings_to_polys(geom):
        ring = poly[0]
        a = abs(ring_area(ring))
        if a > best_area:
            best_area = a
            xs = [c[0] for c in ring]
            ys = [c[1] for c in ring]
            best = (sum(xs) / len(xs), sum(ys) / len(ys))
    return best

def point_in_ring(pt, ring):
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        if (y1 > y) != (y2 > y):
            xinters = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xinters:
                inside = not inside
    return inside

def point_in_geom(pt, geom):
    for poly in _rings_to_polys(geom):
        if point_in_ring(pt, poly[0]):
            if not any(point_in_ring(pt, h) for h in poly[1:]):
                return True
    return False

# --- Load King County polygon -------------------------------------------------
counties = json.load(open("data/counties.geojson"))
king = next(f for f in counties["features"] if f["properties"].get("name") == "King")
king_geom = king["geometry"]

# --- Filter districts to those centered in King County ------------------------
raw = fetch_raw()
kept = []
for f in raw["features"]:
    rep = representative_point(f["geometry"])
    if rep and point_in_geom(rep, king_geom):
        kept.append(f)

# --- Compute Polsby-Popper ----------------------------------------------------
for f in kept:
    a, p = area_perimeter(f["geometry"])
    pp = (4 * math.pi * a) / (p * p) if p > 0 else 0.0
    props = f["properties"]
    f["properties"] = {
        "NAME": props.get("NAME"),
        "GEOID": props.get("GEOID"),
        "PP": round(pp, 4),
        "area_km2": round(a / 1e6, 1),
        "perimeter_km": round(p / 1e3, 1),
    }

# Rank: 1 = least compact (lowest PP), most visually irregular
kept.sort(key=lambda f: f["properties"]["PP"])
for i, f in enumerate(kept, start=1):
    f["properties"]["rank"] = i

out = {"type": "FeatureCollection", "features": kept}
json.dump(out, open("data/school_districts.geojson", "w"))

print(f"Kept {len(kept)} King County school districts\n")
print(f"{'rank':>4}  {'PP':>6}  {'area_km2':>9}  district")
for f in kept:
    pr = f["properties"]
    print(f"{pr['rank']:>4}  {pr['PP']:>6.3f}  {pr['area_km2']:>9.1f}  {pr['NAME']}")
