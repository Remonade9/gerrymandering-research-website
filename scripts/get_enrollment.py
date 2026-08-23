# -*- coding: utf-8 -*-
"""
Pull per-school enrollment for Bellevue SD (NCES leaid 5300390) across years,
from the NCES Common Core of Data via the Urban Institute Education Data API.
Covers all three district states:
  State A (pre-2018): 2016-17, 2017-18
  State B (2018-2023): 2018-19 .. 2022-23  (2022-23 = key pre-closure "before")
  State C (post-2023): 2023-24, 2024-25
Output: final_data/enrollment/  (wide CSV + long CSV + raw JSON)
Enrollment field = total school enrollment (the numerator for utilization = enrollment/capacity).
Also captures school_level, grade span, lat/long, and free/reduced-price-lunch counts (income proxy).
"""
import os, time, json
from pathlib import Path
import requests, pandas as pd

# Data root: $BSD_DATA_DIR if set, else <repo root>/final_data
DATA_ROOT = Path(os.environ.get("BSD_DATA_DIR") or Path(__file__).resolve().parents[1] / "final_data")
BASE = str(DATA_ROOT)
OUT = os.path.join(BASE, "enrollment"); os.makedirs(OUT, exist_ok=True)
API = "https://educationdata.urban.org/api/v1/schools/ccd/directory/{}/"
LEAID = "5300390"
YEARS = list(range(2014, 2025))  # school year = YEAR..YEAR+1

# which state each year belongs to (school year starting in that year)
def state_of(y):
    if y <= 2017: return "A_pre2018"
    if y <= 2022: return "B_2018-2023"
    return "C_post2023"

KEEP = ["ncessch","school_name","school_level","lowest_grade_offered","highest_grade_offered",
        "latitude","longitude","enrollment","free_lunch","reduced_price_lunch",
        "free_or_reduced_price_lunch","school_status"]

rows = []
for y in YEARS:
    data = None
    for a in range(5):
        try:
            r = requests.get(API.format(y), params={"leaid": LEAID}, timeout=90)
            if r.status_code == 200:
                data = r.json().get("results", []); break
        except Exception:
            time.sleep(3)
    if data is None:
        print(y, "unavailable"); continue
    for s in data:
        rec = {k: s.get(k) for k in KEEP}
        rec["year"] = y
        rec["school_year"] = f"{y}-{str(y+1)[2:]}"
        rec["state"] = state_of(y)
        rows.append(rec)
    print(y, "-> schools:", len(data))

long = pd.DataFrame(rows)
long.to_csv(os.path.join(OUT, "enrollment_long.csv"), index=False, encoding="utf-8")

# wide: one row per school, one column per school year (enrollment only)
wide = long.pivot_table(index=["ncessch","school_name","school_level"],
                        columns="school_year", values="enrollment", aggfunc="first").reset_index()
wide = wide.sort_values(["school_level","school_name"])
wide.to_csv(os.path.join(OUT, "enrollment_wide.csv"), index=False, encoding="utf-8")

json.dump(rows, open(os.path.join(OUT, "enrollment_raw.json"), "w"), indent=1)

print("\nSAVED to", OUT)
print("wide table shape:", wide.shape)
print("\n--- enrollment by school year (elementary only, first 12) ---")
elem = wide[wide["school_level"].astype(str).str.contains("Elementary", case=False, na=False)]
cols = ["school_name"] + [c for c in wide.columns if "-" in str(c)]
print(elem[cols].head(12).to_string(index=False))
