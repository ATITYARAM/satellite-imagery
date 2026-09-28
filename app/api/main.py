import os
import json
import pandas as pd
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Coastal Erosion Platform API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_status = "Idle"

def run_pipeline_task():
    global pipeline_status
    pipeline_status = "Running"
    # Using the existing venv python if available
    python_exec = "./venv/bin/python" if os.path.exists("./venv/bin/python") else "python3"
    result = os.system(f"{python_exec} scripts/run_demo.py")
    if result == 0:
        pipeline_status = "Completed"
    else:
        pipeline_status = "Failed"

@app.post("/pipeline/run")
def run_pipeline(background_tasks: BackgroundTasks):
    global pipeline_status
    if pipeline_status == "Running":
        return {"status": "Running", "message": "Pipeline is already running."}
    background_tasks.add_task(run_pipeline_task)
    pipeline_status = "Running"
    return {"status": "started", "message": "Pipeline execution triggered."}

@app.get("/pipeline-status")
def get_pipeline_status():
    return {"status": pipeline_status}

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

def read_json_file(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": f"{path} not found. Run the pipeline first."}

def read_csv_to_dict(path):
    try:
        df = pd.read_csv(path)
        return df.to_dict(orient="records")
    except FileNotFoundError:
        return {"error": f"{path} not found. Run the pipeline first."}

@app.get("/metrics")
def get_metrics():
    return read_json_file("outputs/model_metrics.json")

@app.get("/map-data")
def get_map_data():
    return read_json_file("outputs/map_data.geojson")

@app.get("/feature-importance")
def get_feature_importance():
    return read_csv_to_dict("outputs/feature_importance.csv")

@app.get("/priority-zones")
def get_priority_zones():
    return read_csv_to_dict("outputs/priority_zones.csv")

@app.get("/data-summary")
def get_data_summary():
    try:
        df = pd.read_csv("data/synthetic/06_combined_ml_inputs.csv")
        return {
            "total_segments": int(df['segment_id'].nunique()),
            "total_observations": int(len(df)),
            "number_of_features": int(len(df.columns)),
            "date_range": f"{df['observation_date'].min()} to {df['observation_date'].max()}",
            "latest_observation": df['observation_date'].max(),
            "valid_observations": int(len(df.dropna())),
            "missing_observations": int(df.isna().sum().sum())
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/domain-data/{domain}")
def get_domain_data(domain: str):
    domain_map = {
        "satellite": "01_satellite_output.csv",
        "shoreline": "02_shoreline_history_output.csv",
        "terrain": "03_terrain_output.csv",
        "weather": "04_rainfall_weather_output.csv",
        "ocean": "05_ocean_conditions_output.csv"
    }
    if domain not in domain_map:
        return {"error": "Invalid domain"}
    try:
        df = pd.read_csv(f"data/synthetic/{domain_map[domain]}")
        return {
            "records": len(df),
            "columns": list(df.columns),
            "sample": df.head(5).to_dict(orient="records")
        }
    except Exception as e:
        return {"error": str(e)}

# Serve static dashboard
os.makedirs("dashboard", exist_ok=True)
app.mount("/dashboard_static", StaticFiles(directory="dashboard", html=True), name="dashboard_static")
app.mount("/docs_static", StaticFiles(directory="docs"), name="docs_static")

@app.get("/")
def read_root():
    return RedirectResponse(url="/dashboard/")

@app.get("/dashboard")
@app.get("/dashboard/")
def read_dashboard():
    return FileResponse("dashboard/index.html")
