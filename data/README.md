# Map data

Web-ready GeoJSON layers loaded by `index.html` (all EPSG:4326). The map fetches
these by name, so keep the filenames exactly as listed.

> **Citations:** the complete, citation-ready inventory of every dataset the site uses
> (source, vintage, pipeline) is in **`../../Main - Gerrymandering/Final_Data/DATA_SOURCES.md`** —
> that file is the backbone of the future Methods & Sources tab. (This README's table below is
> outdated; the build scripts now produce many more files than listed.)

| File | What it is | Source |
|------|------------|--------|
| `bellevue_district.geojson` | Bellevue School District outline (1 polygon) | City of Bellevue Open Data |
| `bellevue_elementary_zones.geojson` | 14 post-2023 elementary attendance zones (`name` + geometry) | City of Bellevue Open Data |
| `bellevue_elementary_labels.geojson` | 1 point per zone, for school-name labels | derived (zone representative points) |

## Regenerating

```sh
python data/build_bellevue_basics.py
```

Reads the authoritative boundaries from `../../Main - Gerrymandering/Final_Data/attendance zone boundaries/`,
slims properties, rounds coordinates to 5 decimals (~1 m) to keep files small, title-cases the
ALL-CAPS zone names, and writes the three files above.

## Notes
- Only web-ready GeoJSON belongs here. Raw downloads and the full data pipeline live under
  `../../Main - Gerrymandering/Final_Data/`.
- Older files from the project's earlier (WA redistricting / MCMC) direction were moved to
  `../_archive/`. They are kept for reference and preserved in git history.
