# -*- coding: utf-8 -*-
"""
Enrich the web school-point files (bellevue_<level>_schools.geojson) with an "info" property
for the marker popup: enrollment (+ recent trend), capacity, utilization, 2023 role, programs hosted.
Run AFTER build_bellevue_basics.py (which rebuilds the school files without info).
Sources: final_data enrollment / capacity / program-hosting.
"""
import os, json
import pandas as pd

WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
LEVELS = ["elementary", "middle", "high"]
LEVEL_CODE = {"elementary": 1, "middle": 2, "high": 3}
# Sparkline spans the trend to the current headline year. Historical points are NCES
# (OSPI has only the three era-snapshot years); the CUR endpoint is overridden with OSPI
# below so it matches the headline number. CUR = 2023-24 (first post-consolidation year).
YEARS = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24"]
CUR = "2023-24"

enr = pd.read_csv(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"))
cap = pd.read_csv(os.path.join(FDATA, "capacity", "school_capacity.csv"))
ph = pd.read_csv(os.path.join(FDATA, "programs", "program_hosting.csv"))

# OSPI per-school data (consistent pre-K-5 basis; elementary only). See Final_Data/ospi/.
# Carries the enrollment override AND the enrolled-student demographics for the pin.
def load_ospi(year, fname):
    race = {"white": "white", "asian": "asian", "hispanic": "hispanic",
            "black": "black", "two_or_more": "twoplus", "other": "other"}
    out = {}
    with open(os.path.join(FDATA, "ospi", fname), encoding="utf-8") as f:
        import csv as _csv
        for r in _csv.DictReader(f):
            if r["year"] == year and r["all_students_prek5"]:
                out[r["school"].strip().title()] = {
                    "year": year,
                    "n": int(r["all_students_prek5"]),
                    "race": {v: int(r[k] or 0) for k, v in race.items()},
                    "low_income": int(r["low_income"] or 0),
                    "ell": int(r["ell"] or 0),
                    "highly_capable": int(r["highly_capable"] or 0),
                    "iep": int(r["iep_swd"] or 0),
                }
    return out
_OSPI_CUR = load_ospi(CUR, "ospi_elementary.csv")   # elementary: committed enrollment + demographics
_OSPI_SEC = load_ospi(CUR, "ospi_secondary.csv")    # middle/high: demographics only (enrollment stays NCES)

def base_name(s):
    s = str(s).strip()
    for suf in [" Elementary School", " Elementary", " Middle School", " Middle",
                " Senior High School", " Senior High", " High School", " High"]:
        if s.endswith(suf):
            return s[:-len(suf)].strip()
    return s

# programs hosted, keyed by host school (title case)
prog_by_host = {}
for _, r in ph.iterrows():
    note = str(r["rezoning_relevant_change"]) if pd.notna(r["rezoning_relevant_change"]) else ""
    note = "" if note.strip().lower().startswith("current") else note.strip()
    prog_by_host.setdefault(str(r["host_school"]).strip().title(), []).append(
        {"program": str(r["program"]).strip(), "category": str(r["category"]).strip(), "note": note})

for level in LEVELS:
    fp = os.path.join(WEB, f"bellevue_{level}_schools.geojson")
    raw = json.load(open(fp))
    e = enr[enr["school_level"] == LEVEL_CODE[level]].copy()
    e["key"] = e["school_name"].map(base_name).str.title()
    enr_by = {row["key"]: row for row in e.to_dict("records")}
    c = cap[cap["level"] == level].copy()
    c["key"] = c["school"].astype(str).str.strip().str.title()
    cap_by = {row["key"]: row for row in c.to_dict("records")}

    for feat in raw["features"]:
        nm = feat["properties"]["name"]
        er, cr = enr_by.get(nm), cap_by.get(nm)
        info = {"programs": prog_by_host.get(nm, [])}
        elem_ospi = _OSPI_CUR.get(nm) if level == "elementary" else None
        sec_ospi = _OSPI_SEC.get(nm) if level != "elementary" else None
        ospi_cur = elem_ospi or sec_ospi
        if er or ospi_cur is not None:
            if elem_ospi is not None:
                info["enroll_current"] = elem_ospi["n"]           # elementary: OSPI is the committed enrollment
            else:
                cur = er.get(CUR) if er else None                 # secondary: enrollment stays NCES
                info["enroll_current"] = int(cur) if pd.notna(cur) else None
            if ospi_cur is not None:
                info["ospi"] = ospi_cur   # enrolled-student demographics for the pin + rankings (all levels)
            info["enroll_year"] = CUR
            # trend: NCES historical shape; OSPI override on the CUR endpoint for ELEMENTARY only,
            # so its headline (OSPI) and endpoint match. Secondary keeps NCES throughout.
            trend = []
            for y in YEARS:
                if y == CUR and elem_ospi is not None:
                    trend.append({"year": y, "n": elem_ospi["n"]})
                else:
                    v = er.get(y) if er else None
                    trend.append({"year": y, "n": (int(v) if pd.notna(v) else None)})
            info["trend"] = trend
        if cr:
            capv = cr.get("permanent_capacity")
            info["capacity"] = int(capv) if pd.notna(capv) else None
            info["role"] = str(cr.get("in_2023_consolidation")) if pd.notna(cr.get("in_2023_consolidation")) else None
            if info.get("enroll_current") and info.get("capacity"):
                info["utilization"] = round(info["enroll_current"] / info["capacity"] * 100)
        feat["properties"]["info"] = info
    json.dump(raw, open(fp, "w"))
    print(f"{level}: enriched {len(raw['features'])} schools")
    if level == "elementary":
        for feat in raw["features"][:4]:
            p = feat["properties"]; i = p["info"]
            print(f"   {p['name']:16} enroll={i.get('enroll_current')} cap={i.get('capacity')} "
                  f"util={i.get('utilization')}% role={i.get('role')} progs={len(i['programs'])}")
print("done")
