# Map data

GeoJSON layers loaded by the map in `index.html`. The map fetches these files by
name, so keep the filenames exactly as listed.

| File              | What it is                          | Source                         | Status |
|-------------------|-------------------------------------|--------------------------------|--------|
| `counties.geojson`| WA county boundaries (39 polygons)  | geo.wa.gov                     | ✅ in repo |
| `districts.geojson`| Enacted 2022 districts (base layer)| WA Redistricting Commission    | ⬜ convert from shapefile |
| `water.geojson`   | Water bodies (Puget Sound, lakes)   | WA DNR Hydrography             | ⬜ simplify before adding |

## Preparing files (use https://mapshaper.org)

- **Shapefiles → GeoJSON:** drag the unzipped `.shp` (+ `.dbf`, `.prj`, `.shx`)
  into mapshaper, then Export → GeoJSON.
- **Big files → simplify:** use the *Simplify* button (try 2–10%) before export so
  the browser stays fast. The raw water file is ~200 MB and must be simplified
  hard (aim for a few MB).

Keep raw downloads and zips OUT of this folder — they live in
`../../Main - Gerrymandering/Data/`. Only put web-ready GeoJSON here.
