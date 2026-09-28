import os
import json
import random
import datetime
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)

def generate_data():
    print("1. Generating synthetic 5-domain data...")
    segments = [f"SEG_{str(i).zfill(3)}" for i in range(1, 101)]
    base_date = datetime.date(2020, 1, 1)
    dates = [base_date + datetime.timedelta(days=30*i) for i in range(24)]

    data_satellite = []
    data_shoreline = []
    data_terrain = []
    data_weather = []
    data_ocean = []

    for seg in segments:
        # Terrain is static
        elevation = random.uniform(0.5, 10.0)
        slope = random.uniform(0.1, 5.0)
        dist_to_shore = random.uniform(0, 100)
        data_terrain.append({
            "segment_id": seg,
            "elevation_m": elevation,
            "slope_deg": slope,
            "distance_to_shore_m": dist_to_shore
        })
        
        for date in dates:
            # Shared time variables
            is_monsoon = date.month in [10, 11, 12]
            storm_factor = random.random() if is_monsoon else random.random() * 0.2
            
            # Satellite
            data_satellite.append({
                "segment_id": seg,
                "observation_date": date.isoformat(),
                "sat_ndvi": random.uniform(-0.1, 0.4),
                "sat_ndwi": random.uniform(-0.5, 0.5),
                "sat_mndwi": random.uniform(-0.3, 0.6),
                "sat_savi": random.uniform(-0.1, 0.3),
                "sat_quality": "GOOD"
            })
            
            # Shoreline History
            data_shoreline.append({
                "segment_id": seg,
                "observation_date": date.isoformat(),
                "shoreline_change_m": random.uniform(-2.0, 1.0) - (storm_factor * 0.5),
                "nsm_m": random.uniform(-10.0, 5.0),
                "epr_m_per_year": random.uniform(-1.5, 0.5)
            })
            
            # Weather
            data_weather.append({
                "segment_id": seg,
                "observation_date": date.isoformat(),
                "rainfall_30d_mm": random.uniform(0, 50) + (300 if is_monsoon else 0),
                "wind_speed_ms": random.uniform(2, 10) + (5 if storm_factor > 0.8 else 0)
            })
            
            # Ocean
            data_ocean.append({
                "segment_id": seg,
                "observation_date": date.isoformat(),
                "wave_height_m": random.uniform(0.5, 2.0) + (storm_factor * 2),
                "storm_surge_m": random.uniform(0, 0.2) + (storm_factor * 0.8)
            })

    # Save to data/synthetic
    pd.DataFrame(data_satellite).to_csv("data/synthetic/01_satellite_output.csv", index=False)
    pd.DataFrame(data_shoreline).to_csv("data/synthetic/02_shoreline_history_output.csv", index=False)
    pd.DataFrame(data_terrain).to_csv("data/synthetic/03_terrain_output.csv", index=False)
    pd.DataFrame(data_weather).to_csv("data/synthetic/04_rainfall_weather_output.csv", index=False)
    pd.DataFrame(data_ocean).to_csv("data/synthetic/05_ocean_conditions_output.csv", index=False)
    
    print("Synthetic data generated.")
    
def combine_and_model():
    print("2. Combining datasets...")
    sat = pd.read_csv("data/synthetic/01_satellite_output.csv")
    shore = pd.read_csv("data/synthetic/02_shoreline_history_output.csv")
    terr = pd.read_csv("data/synthetic/03_terrain_output.csv")
    weath = pd.read_csv("data/synthetic/04_rainfall_weather_output.csv")
    ocean = pd.read_csv("data/synthetic/05_ocean_conditions_output.csv")

    df = sat.merge(shore, on=["segment_id", "observation_date"])
    df = df.merge(weath, on=["segment_id", "observation_date"])
    df = df.merge(ocean, on=["segment_id", "observation_date"])
    df = df.merge(terr, on=["segment_id"])
    
    # Sort by time to create future target
    df = df.sort_values(["segment_id", "observation_date"])
    
    # Target: next period shoreline change
    df["future_shoreline_change_m"] = df.groupby("segment_id")["shoreline_change_m"].shift(-1)
    
    # Drop rows with NaN target (the last date for each segment)
    df = df.dropna(subset=["future_shoreline_change_m"])
    
    # Save combined
    df.to_csv("data/synthetic/06_combined_ml_inputs.csv", index=False)
    print("Combined data shape:", df.shape)
    
    print("3. Training Models...")
    features = ["sat_ndvi", "sat_ndwi", "sat_mndwi", "sat_savi", "shoreline_change_m", "nsm_m", 
                "epr_m_per_year", "rainfall_30d_mm", "wind_speed_ms", "wave_height_m", 
                "storm_surge_m", "elevation_m", "slope_deg", "distance_to_shore_m"]
    
    X = df[features]
    y = df["future_shoreline_change_m"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Random Forest
    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    rf_preds = rf.predict(X_test)
    
    # XGBoost
    xgb_model = xgb.XGBRegressor(n_estimators=100, random_state=42)
    xgb_model.fit(X_train, y_train)
    xgb_preds = xgb_model.predict(X_test)
    
    print("4. Evaluating Models...")
    metrics = {
        "RandomForest": {
            "MAE": mean_absolute_error(y_test, rf_preds),
            "RMSE": np.sqrt(mean_squared_error(y_test, rf_preds)),
            "R2": r2_score(y_test, rf_preds)
        },
        "XGBoost": {
            "MAE": mean_absolute_error(y_test, xgb_preds),
            "RMSE": np.sqrt(mean_squared_error(y_test, xgb_preds)),
            "R2": r2_score(y_test, xgb_preds)
        }
    }
    
    with open("outputs/model_metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)
        
    print(json.dumps(metrics, indent=4))
    
    # Feature Importance
    importance = pd.DataFrame({
        "Feature": features,
        "Importance": xgb_model.feature_importances_
    }).sort_values("Importance", ascending=False)
    importance.to_csv("outputs/feature_importance.csv", index=False)
    
    # Generate Priority Zones (mock based on predictions)
    df_latest = df.groupby("segment_id").last().reset_index()
    X_latest = df_latest[features]
    latest_preds = xgb_model.predict(X_latest)
    
    df_latest["predicted_change"] = latest_preds
    df_latest["priority_score"] = -latest_preds + (df_latest["storm_surge_m"] * 0.5)
    df_latest["priority_class"] = pd.qcut(df_latest["priority_score"], 3, labels=["Low", "Medium", "High"])
    
    df_latest[["segment_id", "predicted_change", "priority_score", "priority_class"]].to_csv("outputs/priority_zones.csv", index=False)
    
    print("5. Generating Map/GeoJSON Output...")
    geojson = {
        "type": "FeatureCollection",
        "features": []
    }
    # Mocking coordinates for segments roughly in Chennai
    for idx, row in df_latest.iterrows():
        lat = 13.0 - (idx * 0.005)
        lon = 80.2 + (idx * 0.001)
        geojson["features"].append({
            "type": "Feature",
            "properties": {
                "segment_id": row["segment_id"],
                "predicted_change": float(row["predicted_change"]),
                "priority_class": str(row["priority_class"])
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        })
        
    with open("outputs/map_data.geojson", "w") as f:
        json.dump(geojson, f)

    print("End-to-End Synthetic Pipeline Finished Successfully!")
    print("Outputs written to data/synthetic/ and outputs/")
    
if __name__ == "__main__":
    set_seed()
    os.makedirs("data/synthetic", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    generate_data()
    combine_and_model()
