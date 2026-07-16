# -*- coding: utf-8 -*-
"""
Per-ERA district-wide segregation indices for the District overview.

For each boundary era (a = pre-2018, b = 2018-2023, c = 2023-now) and level:
  residential D + Theil's H  - from the website zone geojsons' own per-zone 2020
                               census counts (frozen population; same aggregation
                               the site displays, so numbers stay consistent)
  district mix gap           - child-weighted (kids 5-17) average of the per-zone
                               mix_gap values already computed for the site
  enrollment D + Theil's H   - actual per-school race enrollment (CCD via Urban
                               Institute API), using each era's own school set and
                               the era's FINAL school year (a: 2017-18, b: 2022-23,
                               c: 2023-24); dropped for an era if school matching
                               fails validation

Only elementary boundaries differ across eras; middle/high residential values are
computed once from the current files and reused. Enrollment values are per-year,
so middle/high get their own year per era.

Output (new schema): bellevue_district_stats.json
  { eras: { a|b|c: { residential:{lvl:{D,H,n}}, enrollment:{lvl:{D,H,n}}|null,
                     mix_gap:{lvl:v}, enroll_year:"YYYY-YY"|null } }, meta: {...} }
Validation: era-c residential must reproduce the previous file's values
(elementary D=0.148 H=0.023 n=14).
"""
import json, math, os, time
import requests

WEB = os.path.dirname(os.path.abspath(__file__))
GROUPS = ["white", "asian", "hispanic", "black", "twoplus", "other"]

def entropy(shares):
    return -sum(p * math.log(p) for p in shares if p > 0)

def indices(rows):
    """rows: list of dicts with GROUPS counts + total. Returns (D, H, n)."""
    T = sum(r["total"] for r in rows)
    W = sum(r["white"] for r in rows); N = T - W
    D = 0.5 * sum(abs(r["white"] / W - (r["total"] - r["white"]) / N) for r in rows)
    E = entropy([sum(r[g] for r in rows) / T for g in GROUPS])
    H = 0.0
    for r in rows:
        t = r["total"]
        if t <= 0:
            continue
        H += (t / T) * (E - entropy([r[g] / t for g in GROUPS])) / E
    return round(D, 3), round(H, 3), len(rows)

def load(fn):
    return json.load(open(os.path.join(WEB, fn), encoding="utf-8"))

def zone_rows(fc):
    """Residential race counts per zone from the site's own seg block."""
    rows = []
    for ft in fc["features"]:
        s = ft["properties"].get("seg") or {}
        if not s.get("total_pop"):
            continue
        rows.append({
            "white": s.get("white_n", 0), "asian": s.get("asian_n", 0),
            "hispanic": s.get("hispanic_n", 0), "black": s.get("black_n", 0),
            "twoplus": s.get("twoplus_n", 0),
            "other": s.get("aian_n", 0) + s.get("nhpi_n", 0) + s.get("other_n", 0),
            "total": s.get("total_pop", 0),
        })
    return rows

def district_mix_gap(fc):
    """Child-weighted average of the per-zone mix_gap values."""
    num = den = 0.0
    for ft in fc["features"]:
        p = ft["properties"]
        if p.get("mix_gap") is None or not p.get("kids_5_17"):
            continue
        num += p["mix_gap"] * p["kids_5_17"]
        den += p["kids_5_17"]
    return round(num / den, 3) if den else None

# ---------- per-era zone files (website copies = what the site displays) ----------
ZONES = {
    "a": {"elementary": "bellevue_a_elementary_zones.geojson"},
    "b": {"elementary": "bellevue_b_elementary_zones.geojson"},
    "c": {"elementary": "bellevue_elementary_zones.geojson"},
}
SHARED = {"middle": "bellevue_middle_zones.geojson", "high": "bellevue_high_zones.geojson"}
SCHOOLS = {
    "a": "bellevue_a_elementary_schools.geojson",
    "b": "bellevue_b_elementary_schools.geojson",
    "c": "bellevue_elementary_schools.geojson",
}
ENROLL_YEAR = {"a": 2017, "b": 2022, "c": 2023}   # each era's final school year
LEVELS = ["elementary", "middle", "high"]

# ---------- residential + mix gap ----------
eras = {}
shared_res, shared_mg = {}, {}
for lvl, fn in SHARED.items():
    fc = load(fn)
    shared_res[lvl] = dict(zip(("D", "H", "n"), indices(zone_rows(fc))))
    shared_mg[lvl] = district_mix_gap(fc)
for era, files in ZONES.items():
    fc = load(files["elementary"])
    D, H, n = indices(zone_rows(fc))
    eras[era] = {
        "residential": {"elementary": {"D": D, "H": H, "n": n}, **{l: dict(shared_res[l]) for l in SHARED}},
        "mix_gap": {"elementary": district_mix_gap(fc), **dict(shared_mg)},
        "enrollment": None, "enroll_year": None,
    }
    print(f"era {era} residential elementary: D={D} H={H} n={n}  mix_gap={eras[era]['mix_gap']['elementary']}")
print("shared middle/high residential:", shared_res, "| mix gap:", shared_mg)

# ---------- enrollment basis, per era ----------
RC = {1: "white", 2: "black", 3: "hispanic", 4: "asian", 5: "other", 6: "other",
      7: "twoplus", 8: "other", 9: "other", 20: "other"}
LVL_CODE = {"elementary": 1, "middle": 2, "high": 3}

def base_name(s):
    s = str(s).strip()
    for suf in [" Elementary School", " Elementary", " Middle School", " Middle",
                " Senior High School", " Senior High", " High School", " High"]:
        if s.endswith(suf):
            return s[:-len(suf)].strip()
    return s

def fetch_ccd(year):
    for _ in range(5):
        try:
            r = requests.get(
                f"https://educationdata.urban.org/api/v1/schools/ccd/enrollment/{year}/grade-99/race/",
                params={"leaid": "5300390"}, timeout=90)
            if r.status_code == 200:
                return r.json()["results"]
        except Exception:
            pass
        time.sleep(3)
    return None

# directory info: ncessch -> name + level (from the existing enrollment pull)
import csv
FDATA = r"C:\Users\lucas\OneDrive\Lucas College Application\04_GIS_Research\Main - Gerrymandering\Final_Data"
dirinfo = {}
with open(os.path.join(FDATA, "enrollment", "enrollment_wide.csv"), encoding="utf-8") as f:
    for row in csv.DictReader(f):
        dirinfo[str(row["ncessch"]).zfill(12)] = (base_name(row["school_name"]).title(),
                                                  int(float(row["school_level"])) if row["school_level"] else None)

# OSPI per-school race (elementary only) — the committed source for the ELEMENTARY
# enrollment-basis indices (consistent with the OSPI school pins; reconciles to district
# counts). Middle/high stay on CCD. CCD elementary is still computed below, only to report
# the OSPI-vs-CCD difference. Switched 2026-07-16.
OSPI_YEAR = {2017: "2017-18", 2022: "2022-23", 2023: "2023-24"}
_ORMAP = {"white": "white", "asian": "asian", "hispanic": "hispanic",
          "black": "black", "two_or_more": "twoplus", "other": "other"}
def ospi_race(year_label):
    out = {}
    with open(os.path.join(FDATA, "ospi", "ospi_elementary.csv"), encoding="utf-8") as fo:
        for r in csv.DictReader(fo):
            if r["year"] != year_label or not r["all_students_prek5"]:
                continue
            rec = {g: 0 for g in GROUPS}
            for src, g in _ORMAP.items():
                rec[g] += int(r[src] or 0)
            rec["total"] = sum(rec[g] for g in GROUPS)
            out[r["school"].strip().title()] = rec
    return out
DIFFS = []  # (era, D_ccd, H_ccd, n_ccd, D_ospi, H_ospi, n_ospi) for the elementary comparison record

# per-era zoned-school sets
main_sets = {}
for era, fn in SCHOOLS.items():
    fc = load(fn)
    elem = {ft["properties"]["name"] for ft in fc["features"] if ft["properties"].get("kind") == "main"}
    mid = {ft["properties"]["name"] for ft in load("bellevue_middle_schools.geojson")["features"] if ft["properties"].get("kind") == "main"}
    high = {ft["properties"]["name"] for ft in load("bellevue_high_schools.geojson")["features"] if ft["properties"].get("kind") == "main"}
    main_sets[era] = {"elementary": elem, "middle": mid, "high": high}

for era in ["a", "b", "c"]:
    year = ENROLL_YEAR[era]
    rows = fetch_ccd(year)
    if not rows:
        print(f"era {era}: CCD {year} fetch FAILED - enrollment basis omitted")
        continue
    # pivot: school key -> level, group counts
    piv = {}
    for r in rows:
        if r.get("race") in (99, None):
            continue
        key = dirinfo.get(str(r.get("ncessch", "")).zfill(12))
        if not key:
            continue
        name, lvlcode = key
        g = RC.get(r["race"])
        if g is None:
            continue
        e = r.get("enrollment") or 0
        if e < 0:
            e = 0
        rec = piv.setdefault((name, lvlcode), {g2: 0 for g2 in GROUPS})
        rec[g] += e
    ok = True
    enr = {}
    o_race = ospi_race(OSPI_YEAR[year])
    for lvl in LEVELS:
        want = main_sets[era][lvl]
        # CCD subset for this level (committed source for middle/high; comparison-only for elementary)
        sub_ccd = []
        found_ccd = set()
        for (name, lvlcode), rec in piv.items():
            if lvlcode == LVL_CODE[lvl] and name in want:
                total = sum(rec.values())
                if total > 0:
                    sub_ccd.append({**rec, "total": total})
                    found_ccd.add(name)
        if lvl == "elementary":
            found_o = {nm for nm in want if nm in o_race and o_race[nm]["total"] > 0}
            missing = want - found_o
            if missing:
                print(f"era {era} elementary: MISSING from OSPI: {sorted(missing)} - enrollment basis omitted")
                ok = False
                break
            D, H, n = indices([dict(o_race[nm]) for nm in found_o])            # committed: OSPI
            Dc, Hc, nc = indices(sub_ccd) if sub_ccd else (None, None, 0)       # comparison: CCD
            DIFFS.append((era, Dc, Hc, nc, D, H, n))
            print(f"era {era} enrollment elementary ({OSPI_YEAR[year]}): "
                  f"CCD D={Dc} H={Hc} n={nc}  ->  OSPI D={D} H={H} n={n}")
            enr[lvl] = {"D": D, "H": H, "n": n}
        else:
            missing = want - found_ccd
            if missing:
                print(f"era {era} {lvl}: MISSING from CCD {year}: {sorted(missing)} - enrollment basis omitted for this era")
                ok = False
                break
            D, H, n = indices(sub_ccd)
            enr[lvl] = {"D": D, "H": H, "n": n}
            print(f"era {era} enrollment {lvl:11} ({year}): D={D} H={H} n={n} (CCD)")
    if ok:
        eras[era]["enrollment"] = enr
        eras[era]["enroll_year"] = f"{year}–{str(year + 1)[2:]}"

# ---------- validation against the previous file ----------
prev = load("bellevue_district_stats.json")
if "residential" in prev:
    exp = prev["residential"]["elementary"]
    got = eras["c"]["residential"]["elementary"]
    assert (exp["D"], exp["H"], exp["n"]) == (got["D"], got["H"], got["n"]), (exp, got)
    print("validation: era-c residential elementary matches previous file")
    exp2 = prev["enrollment"]["elementary"]
    got2 = eras["c"]["enrollment"]["elementary"] if eras["c"]["enrollment"] else None
    print(f"era-c enrollment elementary: prev {exp2} -> now {got2}")

out = {
    "eras": eras,
    "meta": {
        "residential": "2020 census blocks (frozen population) aggregated to each era's zones - the same per-zone counts the map displays",
        "enrollment": "Per-school race enrollment for each era's FINAL school year (a: 2017-18, b: 2022-23, c: 2023-24), zoned schools only. ELEMENTARY basis = WA OSPI (pre-K-5; reconciles to district counts; matches the school-pin demographics). MIDDLE/HIGH basis = NCES CCD (grade-99, all grades). Elementary switched CCD -> OSPI 2026-07-16; see Final_Data/ospi/enrollment_dh_ospi_vs_ccd.md.",
        "mix_gap": "district mix gap = child-weighted (5-17) average of the per-zone mix gap values",
        "groups": "White, Asian, Hispanic, Black, Two-plus, Other (combined)",
    },
}
json.dump(out, open(os.path.join(WEB, "bellevue_district_stats.json"), "w"), indent=1)
print("SAVED bellevue_district_stats.json (new per-era schema)")

# ---------- persistent record of the elementary OSPI-vs-CCD difference ----------
rec_lines = [
    "# Elementary enrollment-basis D / H — OSPI vs NCES CCD",
    "",
    "The committed source for the ELEMENTARY enrollment-basis segregation indices was",
    "switched from NCES CCD to WA OSPI on 2026-07-16 — for consistency with the OSPI",
    "school-pin demographics, and because OSPI reconciles to the district's own counts.",
    "Middle/high remain on CCD. OSPI is pre-K-5; CCD grade-99 is all-grades, which is part",
    "of the small gap below. D = dissimilarity (White vs non-White), H = Theil's multigroup",
    "entropy index; both on the enrollment basis, zoned elementaries only.",
    "",
    "| era | year | D (CCD) | D (OSPI) | ΔD | H (CCD) | H (OSPI) | ΔH | n |",
    "|-----|------|--------:|---------:|---:|--------:|---------:|---:|--:|",
]
for era, Dc, Hc, nc, Do, Ho, no in DIFFS:
    dD = f"{Do - Dc:+.3f}" if Dc is not None else "n/a"
    dH = f"{Ho - Hc:+.3f}" if Hc is not None else "n/a"
    rec_lines.append(f"| {era} | {OSPI_YEAR[ENROLL_YEAR[era]]} | {Dc} | {Do} | {dD} | {Hc} | {Ho} | {dH} | {no} |")
rec_path = os.path.join(FDATA, "ospi", "enrollment_dh_ospi_vs_ccd.md")
open(rec_path, "w", encoding="utf-8").write("\n".join(rec_lines) + "\n")
print("\n" + "\n".join(rec_lines))
print(f"\nSAVED {rec_path}")
