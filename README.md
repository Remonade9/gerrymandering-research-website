# One District, Three Maps — Bellevue School District Boundaries

Interactive companion site for Lucas Xue's research on the Bellevue School District's
elementary attendance-boundary changes of 2018 and 2023. It maps the district's attendance
zones in three periods (pre-2018, 2018–2023, 2023–now) and reports what measurably changed
with them: zone shape, enrollment and capacity, who lives where, travel to school, and access
to programs. Every measure is computed once per period from the same fixed 2020 census
population, so differences between periods reflect the boundaries, not population change.

The design goal is to *present information, not to judge*: no color or number on the map is a
fairness score. The site shows what the boundary changes did and leaves the fairness question
to the reader.

Created by Lucas Xue.

**Acknowledgements.** Developed under the mentorship of Prof. Bo Zhao, Humanistic GIS
Laboratory, University of Washington.

## Pages

- `index.html` — the map tool: three boundary periods by three school levels, per-zone
  metrics, map coloring by any measure, layers (neighborhoods, race by census block), address
  lookup and route measurement, District overview, and Graph mode. A short built-in tutorial
  (`tutorial.js`) opens on a fresh visit.
- `changes.html` — Boundary changes: animates exactly which territory moved between schools
  in 2018 and 2023, with school and program moves.
- `analysis.html`, `methods.html`, `definitions.html` — the written analysis, how every number
  was computed, and plain-language definitions with yardsticks. Each has a Chinese twin
  (`*.zh.html`); the two map pages translate in place.
- `intro.js` — the entry screens (title page and descriptive-use notice) and the shared
  language switch. `config.js` — API keys (see below). `styles.css` — styling.

## Folders

- `data/` — the web-ready GeoJSON and JSON layers the pages load, plus the Python scripts that
  build them from the source data (`build_state.py`, `build_changes.py`, `compute_*.py`).
  `data/README.md` describes each layer.
- `scripts/` — the scripts that fetched the raw inputs (census blocks and ages, ACS,
  enrollment, route precomputation) and derived the feeder patterns; see `scripts/README.md`.
- `img/` — figures used on the Analysis page.
- `vendor/` — MapLibre GL JS (CSP build).
- `_archive/` — files from the project's earlier direction, kept for reference only.

## Viewing locally

The pages fetch GeoJSON, so serve the folder over http rather than opening the files directly:

```sh
python -m http.server 8000
```

then visit <http://localhost:8000>. With the shipped key, use `localhost` rather than
`127.0.0.1`: the MapTiler key is locked to approved origins, and `localhost` is one of them.

## API keys (if you run your own copy)

Both map pages load their keys from **`config.js`**, the one place to change them. The two
services are free:

- **MapTiler** (basemap tiles + address search): get a key at <https://cloud.maptiler.com/> and
  lock it to your domain in the MapTiler dashboard ("allowed origins"). A locked key does nothing
  on anyone else's site.
- **openrouteservice** (routes + travel times): get a key at <https://openrouteservice.org/dev/>.
  ORS keys cannot be domain-locked, so if you fork this site, replace it before deploying rather
  than spending the original author's daily quota.

Every precomputed travel number on the site ships in the data files; the keys are only used live
for the basemap, address search, and the pins and routes a visitor places.

## Publishing

A static site with no build step, so any static host works. The live site deploys automatically
from the `main` branch of this repository on Railway.
