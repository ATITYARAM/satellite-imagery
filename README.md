# Coastal Erosion Prediction Platform

## Original Problem Statement

Create a satellite-image analytics system to monitor and predict coastal erosion patterns. The solution should integrate spatial datasets such as maps, satellite imagery, terrain, rainfall, infrastructure, and field records to generate meaningful decision layers. The outcome may include risk maps, priority zones, dashboards, and validation using historical records or expert-labelled ground truth.

## Current study area

The current area of interest is the southern Thiruvananthapuram coast, Kerala, covering the Shanghumugham–Valiyathura–Poonthura stretch. Its initial bounding box is defined in `config/aoi.geojson`; refine this box against an authoritative shoreline before using measurements for scientific claims.

## Current architecture

The complete project will use five independent domains:
1. Satellite Imagery
2. Shoreline History
3. Terrain
4. Rainfall / Weather
5. Ocean Conditions

Each domain will be implemented independently and will later provide a standardized output for the combined ML stage.

Domain data is kept in separate folders. The existing satellite archive remains at `data/satellite/` for compatibility with current scripts; shoreline history is being added at `data/shoreline_history/`. The remaining domain folders will be introduced as those domains are planned.

| Domain | Dataset folder | Current status |
|---|---|---|
| Satellite imagery | `data/satellite/` | Catalogue/sampling workflow committed; local execution required to generate the archive |
| Shoreline history | `data/shoreline_history/` | CoastSat extraction workflow committed; GEE authentication and local execution required |
| Terrain | `data/terrain/` | Planned |
| Rainfall / weather | `data/rainfall_weather/` | Planned |
| Ocean conditions | `data/ocean_conditions/` | Planned |

See [Domain 2: Shoreline History](data/shoreline_history/thiruvananthapuram/README.md) for CoastSat installation, Google Earth Engine setup, and extraction instructions.

## Thiruvananthapuram coastal archive (2010–2025)

The multi-year archive uses the existing coastal study polygon in `config/aoi.geojson` (Shanghumugham–Valiyathura–Poonthura). It does **not** use a city-wide municipal boundary. The sampler queries real Landsat Collection 2 Level-2 and Sentinel-2 Level-2A items from Microsoft Planetary Computer, then selects up to 50 **distinct UTC acquisition dates per year** using fixed seed `20261028`.

From the repository root, activate the project environment and run:

```bash
python scripts/sample_thiruvananthapuram_satellite.py
```

This catalogues scenes and creates the reproducible date selection and annual shortfall report without downloading raster assets. Review `data/satellite/thiruvananthapuram_2010_2025/metadata/annual_coverage.csv` and `catalog/selected_dates.csv`. If the catalogue reports failed queries, rerun the script and do not treat that year's shortfall as confirmed.

To download and clip the selected scene's available optical bands and quality layer for every selected date:

```bash
python scripts/sample_thiruvananthapuram_satellite.py --download
```

Raster outputs go to `data_external/thiruvananthapuram_2010_2025/`, which is ignored by Git. Only code, the selected-date manifest, catalogue metadata, query log, and download log should be committed. The workflow never fabricates missing dates, does not exclude cloudy scenes, and records when a year has fewer than 50 real dates. It selects one best-reported-cloud-cover scene per chosen date; the selected date count is not the same as the scene-product count.

## Satellite data: fetch the new AOI

The committed imagery was downloaded for the previous Chennai study area and must not be reused for Thiruvananthapuram. From the repository root, activate the project's Python environment, then run:

```bash
python scripts/download_landsat_aoi.py
```

This searches Microsoft Planetary Computer for low-cloud Landsat Collection 2 Level-2 scenes acquired in 2016 and 2026, clips all six spectral bands to the current AOI, and writes scene metadata including the AOI bounds. It will report the scene IDs and acquisition dates. If no scene meets the cloud threshold, try `--max-cloud 50`.

Until this script succeeds for both years, the UI intentionally marks the satellite imagery as unavailable and XGBoost refuses to use the old AOI data.

## Local run

1. Install the dependencies from `requirements.txt` in the Python environment.
2. Download the current AOI imagery using the command above.
3. Build the frontend with `npm run build`.
4. Start FastAPI with `uvicorn app.api.main:app --reload`.
5. Open `http://127.0.0.1:8000/dashboard/`.

GitHub is used for source/version control. No GitHub Pages deployment is required.
