# Coastal Erosion Prediction Platform

## Problem Statement
"Create a satellite-image analytics system to monitor and predict coastal erosion patterns. The solution should integrate spatial datasets such as maps, satellite imagery, terrain, rainfall, infrastructure, and field records to generate meaningful decision layers. The outcome may include risk maps, priority zones, dashboards, and validation using historical records or expert-labelled ground truth."

## Architecture
Five distinct domains:
1. Satellite Imagery
2. Shoreline History
3. Terrain
4. Rainfall/Weather
5. Ocean Conditions

Each domain produces standardized outputs that are joined temporally and spatially to produce machine learning features.

## How to Start the System

1. Activate the environment:
```bash
source venv/bin/activate
```

2. Run the synthetic pipeline:
```bash
python scripts/run_demo.py
```

3. Start the backend:
```bash
uvicorn app.api.main:app --reload
```

4. Open the dashboard in your browser:
[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Project Components
- **API**: The backend server powered by FastAPI. Serves both JSON data endpoints and the UI.
- **Dashboard**: The local interactive HTML/JS application served by the API.
- **Synthetic Pipeline**: The data generation and ML training simulated workflow currently representing Phase 1.
- **Generated Outputs**: Results like model metrics, geojson maps, and feature CSVs created by the pipeline.
- **Future Real-Data Adapters**: The planned migration (Phases 2-6) to replace synthetic generation with real external data pipelines.
