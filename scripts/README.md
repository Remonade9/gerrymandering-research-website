# Data acquisition scripts

These eight scripts pull the public source data behind this project and write it into
a local data folder. They are the *acquisition* step only: separate build scripts turn
their output into the map layers this site loads.

**Most people never need to run these.** The processed datasets they produce are
distributed with the paper's replication package, together with the build scripts and
the finished map layers. Run these only to re-pull the source data from scratch.

## Where the data goes

All eight read and write under a single data root:

1. the `BSD_DATA_DIR` environment variable, if it is set; otherwise
2. `final_data/` at the root of this repository.

Inside that root they use fixed subfolders: `census/`, `attendance zone boundaries/`,
`enrollment/`, `routing/`, `programs/`, `schools/`, and `feeder/`. That folder is not
part of this repository; it is created and filled as the scripts run.

## API keys

**No API keys are included in this repository.** Two free keys are needed:

- **US Census** (`get_blocks_2020`, `get_age_2020`, `get_acs_2023`): set `CENSUS_API_KEY`,
  or save the key in `<data root>/census_api_key.txt`.
- **OpenRouteService** (`precompute_routes`, `extend_routes_states`): set `ORS_API_KEY`,
  or save the key in `<data root>/ors_api_key.txt`.

A script that needs a key it cannot find stops immediately and prints where it looked.

## What each script does

| Script | Description |
|---|---|
| `get_blocks_2020.py` | Downloads 2020 TIGER census blocks for King County, clips them to the district, and adds race counts when a Census key is set. |
| `get_age_2020.py` | Pulls 2020 Census table P12 (sex by age) per block to get the school-age population. |
| `get_acs_2023.py` | Pulls ACS 2023 block-group income, home value, rent, and limited-English household counts. |
| `get_enrollment.py` | Pulls per-school NCES enrollment for 2014-15 through 2024-25 via the Urban Institute API. |
| `precompute_routes.py` | Builds drive and walk time/distance matrices from every populated block to every school, using OpenRouteService and the school points in this repo's `data/` folder. |
| `extend_routes_states.py` | Adds the historical-era school sites to those route caches. |
| `derive_feeder.py` | Derives the elementary to middle to high feeder pattern by overlaying attendance zones. |
| `check_zone_school.py` | Sanity check that every attendance-zone name matches a school point. |
