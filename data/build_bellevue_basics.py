# -*- coding: utf-8 -*-
"""
Build web-ready GeoJSON for the Bellevue rezoning site (basics layer):
  - bellevue_district.geojson              district outline (geometry only)
  - bellevue_<level>_zones.geojson         attendance zones for level (name + geometry)
  - bellevue_<level>_labels.geojson        one point per zone, for school-name labels
  for level in {elementary, middle, high} (post-2023 boundaries).
Coordinates rounded to 5 decimals (~1 m) to keep files small. Source = final_data (EPSG:4326).
"""
import os, json, math
import numpy as np
import geopandas as gpd
from shapely import minimum_bounding_circle
from shapely.geometry.polygon import orient

FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
SRC = os.path.join(FDATA, "attendance zone boundaries")
SCHOOLS_SRC = os.path.join(FDATA, "schools", "school_sites.geojson")
OUT = os.path.dirname(os.path.abspath(__file__))
LEVELS = ["elementary", "middle", "high"]
METRIC_CRS = 32610   # UTM zone 10N (metres) - correct for Bellevue-scale area/perimeter
# base per-zone metrics (percentiles are computed across each level afterwards)
BASE_KEYS = ["area_km2", "perimeter_km", "polsby_popper", "reock",
             "convex_hull", "bounding_rect", "moment_inertia"]
METRIC_KEYS = BASE_KEYS + ["pp_percentile", "reock_percentile", "convex_percentile"]

def _polar_moment(geom):
    """Polygon area A and polar 2nd moment of area J about the centroid (metric CRS)."""
    A = Sx = Sy = Ixx = Iyy = 0.0
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        poly = orient(poly, 1.0)  # exterior CCW (+area), holes CW (-area) -> signs cancel holes
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                cross = x0 * y1 - x1 * y0
                A += cross
                Sx += (x0 + x1) * cross
                Sy += (y0 + y1) * cross
                Ixx += (y0 * y0 + y0 * y1 + y1 * y1) * cross
                Iyy += (x0 * x0 + x0 * x1 + x1 * x1) * cross
    A *= 0.5
    cx, cy = (Sx / 6.0) / A, (Sy / 6.0) / A
    J = (Ixx / 12.0 + Iyy / 12.0) - A * (cx * cx + cy * cy)   # parallel-axis shift to centroid
    return A, J

def compactness(geom):
    """Shape-only compactness metrics. geom must be in a metric CRS."""
    A, P = geom.area, geom.length
    pp = 4 * math.pi * A / (P * P) if P else 0                    # Polsby-Popper (4piA/P^2)
    convex = A / geom.convex_hull.area                            # area / convex-hull area
    reock = A / minimum_bounding_circle(geom).area               # area / min enclosing circle
    brect = A / geom.minimum_rotated_rectangle.area              # area / min rotated rectangle
    Am, J = _polar_moment(geom)
    moi = (Am * Am) / (2 * math.pi * J) if J else 0              # moment of inertia (1 = circle)
    return {"area_km2": round(A / 1e6, 3), "perimeter_km": round(P / 1000, 2),
            "polsby_popper": round(pp, 3), "reock": round(reock, 3),
            "convex_hull": round(convex, 3), "bounding_rect": round(brect, 3),
            "moment_inertia": round(moi, 3)}

def percentile_rank(values):
    """Percentile-of-score (0-100) for each value within its own list."""
    v = np.asarray(values, dtype=float)
    n = len(v)
    return [round(float((np.sum(v < x) + 0.5 * np.sum(v == x)) / n * 100)) for x in v]

def round_geojson(gdf, props):
    gdf = gdf.to_crs(4326)
    feats = []
    for _, row in gdf.iterrows():
        feats.append({"type": "Feature",
                      "properties": {k: row[k] for k in props},
                      "geometry": json.loads(gpd.GeoSeries([row.geometry]).to_json())["features"][0]["geometry"]})
    fc = {"type": "FeatureCollection", "features": feats}
    def rnd(o):
        if isinstance(o, float): return round(o, 5)
        if isinstance(o, list): return [rnd(x) for x in o]
        return o
    for f in fc["features"]:
        f["geometry"]["coordinates"] = rnd(f["geometry"]["coordinates"])
    return fc

# district
dist = gpd.read_file(os.path.join(SRC, "district_boundary.geojson"))
json.dump(round_geojson(dist, []), open(os.path.join(OUT, "bellevue_district.geojson"), "w"))
print("bellevue_district.geojson")

# per level: zones + label points
for level in LEVELS:
    g = gpd.read_file(os.path.join(SRC, "(3) post-2023", f"{level}.geojson"))[["NAME", "geometry"]]
    g["name"] = g["NAME"].str.title()

    # compactness metrics (computed in a metric CRS, attached to each zone's properties)
    gm = g.to_crs(METRIC_CRS)
    mets = [compactness(geom) for geom in gm.geometry]
    for k in BASE_KEYS:
        g[k] = [m[k] for m in mets]
    # percentiles are computed across this level's zones (small reference set for now)
    g["pp_percentile"] = percentile_rank(g["polsby_popper"])
    g["reock_percentile"] = percentile_rank(g["reock"])
    g["convex_percentile"] = percentile_rank(g["convex_hull"])

    zones = round_geojson(g, ["name"] + METRIC_KEYS)
    json.dump(zones, open(os.path.join(OUT, f"bellevue_{level}_zones.geojson"), "w"))

    lab = g.copy(); lab["geometry"] = lab.geometry.representative_point()
    labels = round_geojson(lab, ["name"])
    json.dump(labels, open(os.path.join(OUT, f"bellevue_{level}_labels.geojson"), "w"))

    zkb = os.path.getsize(os.path.join(OUT, f"bellevue_{level}_zones.geojson")) / 1024
    print(f"bellevue_{level}_zones.geojson ({len(g)} zones, {zkb:.0f} KB) + labels")
    if level == "high":
        import pandas as pd
        pd.set_option("display.width", 200)
        print(g[["name"] + METRIC_KEYS].to_string(index=False))

# school POINTS per level (main attendance-area vs choice), exact locations.
# Secondary choice schools (Big Picture, International) are grades 6-12 -> shown on middle AND high.
s = gpd.read_file(SCHOOLS_SRC)
s = s[(s["DISTRICT"] == "Bellevue") & (s["ISPUBLIC"].astype(str).str.strip() == "Y")].copy()
s = s[s["SCHNAME"].astype(str).str.strip() != "Vacant"]
s["nm"] = s["SCHNAME"].astype(str).str.strip().str.title()
s["grade"] = s["GradeLevel"].astype(str).str.strip()
s["is_choice"] = s["Type"].astype(str).str.contains("Choice", case=False)

LEVEL_RULES = {
    "elementary": {"main": ["K-5"], "choice": ["K-5"],  "suffix": "Elementary",
                   "choice_label": "Choice / immersion school", "choice_display": lambda nm: f"{nm} Elementary"},
    "middle":     {"main": ["6-8"], "choice": ["6-8", "6-12"], "suffix": "Middle School",
                   "choice_label": "Choice school (grades 6–12)", "choice_display": lambda nm: nm},
    "high":       {"main": ["9-12"], "choice": ["9-12", "6-12"], "suffix": "High School",
                   "choice_label": "Choice school (grades 6–12)", "choice_display": lambda nm: nm},
}

for level, r in LEVEL_RULES.items():
    main = s[s["grade"].isin(r["main"]) & (~s["is_choice"])]
    choice = s[s["grade"].isin(r["choice"]) & s["is_choice"]]
    recs = []
    for _, row in main.iterrows():
        recs.append((row["nm"], "main", f"{row['nm']} {r['suffix']}", "Attendance-area school", row.geometry))
    for _, row in choice.iterrows():
        recs.append((row["nm"], "choice", r["choice_display"](row["nm"]), r["choice_label"], row.geometry))
    gdf = gpd.GeoDataFrame(
        {"name": [x[0] for x in recs], "kind": [x[1] for x in recs],
         "display": [x[2] for x in recs], "type_label": [x[3] for x in recs],
         "geometry": [x[4] for x in recs]}, crs=s.crs)
    fc = round_geojson(gdf, ["name", "kind", "display", "type_label"])
    json.dump(fc, open(os.path.join(OUT, f"bellevue_{level}_schools.geojson"), "w"))
    nc = sum(1 for f in fc["features"] if f["properties"]["kind"] == "choice")
    print(f"bellevue_{level}_schools.geojson ({len(fc['features'])} schools: {len(fc['features']) - nc} main + {nc} choice)")

print("done")
