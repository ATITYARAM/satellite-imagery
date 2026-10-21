# Coastal Erosion Prediction Platform

## Requirements

- Python 3.10+
- Node.js 22+
- npm
- Internet access for Landsat downloads and map tiles

## Setup

```bash
git clone -b anti https://github.com/ATITYARAM/satellite-imagery.git
cd satellite-imagery

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

npm ci
```

## Configure the study area

Edit `config/aoi.geojson`.

Current AOI: Thiruvananthapuram coast, Kerala — Shanghumugham, Valiyathura and Poonthura.

## Download satellite data

From the repository root, with the Python virtual environment active:

```bash
python scripts/download_landsat_aoi.py
```

The script downloads Landsat Collection 2 Level-2 bands for 2016 and 2026 and writes the data and scene metadata to `data/satellite/<year>/`.

If no scene meets the default cloud threshold:

```bash
python scripts/download_landsat_aoi.py --max-cloud 50
```

## Build and run

```bash
npm run build
uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

Open: http://127.0.0.1:8000/dashboard/

Keep the terminal running while using the application. To stop the server, press `Ctrl+C`.

## Run checks

```bash
npm run lint
npm run build
python -m compileall app scripts
```

## Key paths

- `config/aoi.geojson` — area of interest
- `scripts/download_landsat_aoi.py` — Landsat download and AOI clipping
- `data/satellite/2016/`, `data/satellite/2026/` — downloaded imagery and metadata
- `app/domains/xgboost_pipeline.py` — paired-image XGBoost prototype
- `app/api/main.py` — API and dashboard server
- `src/` — React frontend

## Result API

- `GET /health`
- `GET /aoi`
- `GET /satellite/data`
- `GET /xgboost/result`
- `GET /xgboost/result?force=true`
- `GET /xgboost/result.png`

The current XGBoost output uses a paired-image change proxy from the 2016 and 2026 satellite observations. It is not a ground-truth-validated erosion prediction model.
