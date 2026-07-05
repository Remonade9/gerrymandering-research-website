# -*- coding: utf-8 -*-
"""
Pull Zillow ZHVI (typical home value, smoothed, seasonally adjusted, all homes) for the City of
Bellevue, WA. City-level series = MARKET CONTEXT ONLY for the housing impact (price change over
time is the market, not a rezoning effect - per Measurement_Plan impact 5, question 2).
Saves: raw filtered row -> final_data/housing/zhvi_bellevue_raw.csv
       web series       -> Website/data/bellevue_zhvi.json  { "points": [{"d": "2015-01", "v": 600000}, ...] }
"""
import os, io, json
import pandas as pd, requests

WEB = os.path.dirname(os.path.abspath(__file__))
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
os.makedirs(os.path.join(FDATA, "housing"), exist_ok=True)

URL = "https://files.zillowstatic.com/research/public_csvs/zhvi/City_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
print("downloading ZHVI city file ...")
r = requests.get(URL, timeout=300)
print("status", r.status_code, f"{len(r.content)/1e6:.1f} MB")
df = pd.read_csv(io.BytesIO(r.content))
row = df[(df["RegionName"] == "Bellevue") & (df["State"] == "WA")]
print("Bellevue WA rows:", len(row))
row.to_csv(os.path.join(FDATA, "housing", "zhvi_bellevue_raw.csv"), index=False)

date_cols = [c for c in df.columns if c[:2] in ("19", "20")]
s = row.iloc[0][date_cols].astype(float).dropna()
pts = [{"d": d[:7], "v": int(round(v))} for d, v in s.items()]
json.dump({"region": "Bellevue, WA (city)", "metric": "ZHVI all homes, smoothed, seasonally adjusted",
           "points": pts}, open(os.path.join(WEB, "bellevue_zhvi.json"), "w"))
print(f"SAVED bellevue_zhvi.json ({len(pts)} monthly points, {pts[0]['d']} .. {pts[-1]['d']})")
print("first/last:", pts[0], pts[-1])
