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
