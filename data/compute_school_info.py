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
YEARS = ["2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
CUR = "2024-25"

enr = pd.read_csv(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"))
cap = pd.read_csv(os.path.join(FDATA, "capacity", "school_capacity.csv"))
ph = pd.read_csv(os.path.join(FDATA, "programs", "program_hosting.csv"))

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
        if er:
            cur = er.get(CUR)
            info["enroll_current"] = int(cur) if pd.notna(cur) else None
            info["enroll_year"] = CUR
            info["trend"] = [{"year": y, "n": (int(er[y]) if pd.notna(er.get(y)) else None)} for y in YEARS]
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
