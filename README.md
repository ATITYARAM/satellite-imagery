# Coastal Erosion Prediction Platform

## Original Problem Statement

Create a satellite-image analytics system to monitor and predict coastal erosion patterns. The solution should integrate spatial datasets such as maps, satellite imagery, terrain, rainfall, infrastructure, and field records to generate meaningful decision layers. The outcome may include risk maps, priority zones, dashboards, and validation using historical records or expert-labelled ground truth.

## Current architecture

The complete project will use five independent domains:
1. Satellite Imagery
2. Shoreline History
3. Terrain
4. Rainfall / Weather
5. Ocean Conditions

Each domain will be implemented independently and will later provide a standardized output for the combined ML stage.

## Current clean state

Only the common application shell and study-area AOI are retained in the UI. Domain outputs are added one section at a time, beginning with Satellite Imagery.

## Local run

1. Activate the Python environment.
2. Build the frontend with npm run build.
3. Start FastAPI with uvicorn app.api.main:app --reload.
4. Open http://127.0.0.1:8000/.

GitHub is used only for source/version control. No GitHub Pages deployment is required.