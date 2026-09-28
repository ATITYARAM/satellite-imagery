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
satellite_status = "Idle"


def run_pipeline_task():
    global pipeline_status
    pipeline_status = "Running"
    python_exec = "./venv/bin/python" if os.path.exists("./venv/bin/python") else "python3"
    result = os.system(f"{python_exec} scripts/run_demo.py")
    pipeline_status = "Completed" if result == 0 else "Failed"


def run_satellite_task():
    global satellite_status
    satellite_status = "Running"
    python_exec = "./venv/bin/python" if os.path.exists("./venv/bin/python") else "python3"
    result = os.system(f"{python_exec} scripts/run_satellite.py")
    satellite_status = "Completed" if result == 0 else "Failed"


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


@app.post("/satellite/run")
def run_satellite(background_tasks: BackgroundTasks):
    global satellite_status
    if satellite_status == "Running":
        return {"status": "Running", "message": "Satellite pipeline is already running."}
    background_tasks.add_task(run_satellite_task)
    satellite_status = "Running"
    return {"status": "started", "message": "Satellite domain execution triggered."}


@app.get("/satellite/status")
def get_satellite_status():
    return {"status": satellite_status}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/project/info")
def info():
    return {
        "project": "Coastal Erosion Prediction Platform",
        "study_area": "Chennai-Mahabalipuram Coastal Belt",
        "domains": ["Satellite", "Shoreline", "Terrain", "Weather", "Ocean"],
    }


@app.get("/domains")
def domains():
    return ["satellite", "shoreline", "terrain", "weather", "ocean"]


def read_json_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
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
            "total_segments": int(df["segment_id"].nunique()),
            "total_observations": int(len(df)),
            "number_of_features": int(len(df.columns)),
            "date_range": f"{df['observation_date'].min()} to {df['observation_date'].max()}",
            "latest_observation": df["observation_date"].max(),
            "valid_observations": int(df.notna().all(axis=1).sum()),
            "missing_observations": int(df.isna().sum().sum()),
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/domain-data/{domain}")
def get_domain_data(domain: str):
    domain_map = {
        "satellite": "outputs/satellite_domain_output.csv",
        "shoreline": "data/synthetic/02_shoreline_history_output.csv",
        "terrain": "data/synthetic/03_terrain_output.csv",
        "weather": "data/synthetic/04_rainfall_weather_output.csv",
        "ocean": "data/synthetic/05_ocean_conditions_output.csv",
    }
    if domain not in domain_map:
        return {"error": "Invalid domain"}
    return {
        "records": len(read_csv_to_dict(domain_map[domain])) if isinstance(read_csv_to_dict(domain_map[domain]), list) else 0,
        "data": read_csv_to_dict(domain_map[domain]),
    }


@app.get("/satellite/output")
def get_satellite_output():
    return read_csv_to_dict("outputs/satellite_domain_output.csv")


@app.get("/satellite/summary")
def get_satellite_summary():
    data = read_json_file("outputs/satellite_run.json")
    if "error" in data:
        return data
    return data


@app.get("/satellite-map")
def get_satellite_map():
    return read_json_file("outputs/satellite_map.geojson")


os.makedirs("dist", exist_ok=True)
os.makedirs("docs", exist_ok=True)
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")
app.mount("/docs_static", StaticFiles(directory="docs"), name="docs_static")


@app.get("/")
def read_root():
    return RedirectResponse(url="/dashboard/")


@app.get("/dashboard")
@app.get("/dashboard/")
def read_dashboard():
    return FileResponse("dist/index.html")
