# The 2023 Bellevue Elementary Rezoning — Website

Interactive companion site for Lucas's applied mathematics / GIS research on Bellevue School
District's 2023 elementary school closures and attendance-zone rezoning. It presents what the
boundary changes were and, layer by layer, what changed with them (travel, capacity, who lives
where) for the communities affected. Mentored by Prof. Bo Zhao, Humanistic GIS Lab, University
of Washington.

The design goal is to *present information, not to judge*: the map shows what the rezoning did
and leaves the fairness question to the reader.

## Structure

- `index.html` — single-page site; MapLibre GL JS map with a grayscale MapTiler basemap,
  the district boundary, and the 14 elementary attendance zones.
- `styles.css` — styling.
- `data/` — web-ready GeoJSON layers + `build_bellevue_basics.py` to regenerate them.
- `_archive/` — files from the project's earlier (WA redistricting / MCMC) direction, kept for reference.

## Viewing locally

The map fetches GeoJSON, so it must be served over http (not opened as `file://`). From this folder:

```sh
python -m http.server 8000
```

then visit <http://localhost:8000>.

## Notes

- The MapTiler basemap uses a free-tier API key inlined in `index.html`. It is a low-sensitivity
  key for a public base map; keep this repository private (or restrict the key by domain before
  making it public).

## Publishing

Static site. Deployable free via **GitHub Pages** (Settings → Pages → Deploy from branch → `main` / root).
