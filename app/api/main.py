from fastapi import FastAPI
import json
import os

app = FastAPI(title="Coastal Erosion Platform API")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/project/info")
def info():
    return {
        "project": "Coastal Erosion Prediction Platform",
        "study_area": "Chennai-Mahabalipuram Coastal Belt",
        "domains": ["Satellite", "Shoreline", "Terrain", "Weather", "Ocean"]
    }

@app.get("/domains")
def domains():
    return ["satellite", "shoreline", "terrain", "weather", "ocean"]

@app.post("/pipeline/run")
def run_pipeline():
    # In a real setup, this would trigger the run_demo.py asynchronously
    os.system("python scripts/run_demo.py")
    return {"status": "started", "message": "Pipeline execution triggered."}

@app.get("/metrics")
def get_metrics():
    try:
        with open("outputs/model_metrics.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Metrics not found. Run the pipeline first."}

@app.get("/map-data")
def get_map_data():
    try:
        with open("outputs/map_data.geojson", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Map data not found. Run the pipeline first."}
