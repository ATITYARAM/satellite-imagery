"""XGBoost coastal-change proxy using all 55 selected scenes from 2015–2025.

The target is a spectral-change proxy, not independently validated erosion labels.
Scene rasters are read from data_external and are deliberately not committed.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data" / "satellite"
CATALOG = DATA_ROOT / "thiruvananthapuram_2015_2025" / "catalog" / "selected_dates.csv"
ARCHIVE_ROOT = ROOT / "data_external" / "thiruvananthapuram_2015_2025"
OUTPUT_DIR = ROOT / "outputs" / "xgboost"
RESULT_IMAGE = OUTPUT_DIR / "erosion_change_xgboost.png"
RESULT_JSON = OUTPUT_DIR / "result.json"
YEARS = tuple(range(2015, 2026))
BANDS = ("blue", "green", "red", "nir", "swir1", "swir2")
INDICES = ("ndvi", "ndwi", "mndwi", "savi")
SYNTHETIC_DOMAIN_FILES = {
    "shoreline_history": ROOT / "domains" / "shoreline_history" / "data" / "synthetic" / "shoreline_observations_2015_2025.json",
    "terrain": ROOT / "domains" / "terrain" / "data" / "synthetic" / "terrain_grid_2015_2025.json",
    "rainfall_weather": ROOT / "domains" / "rainfall_weather" / "data" / "synthetic" / "rainfall_weather_monthly_2015_2025.json",
    "ocean_conditions": ROOT / "domains" / "ocean_conditions" / "data" / "synthetic" / "ocean_conditions_monthly_2015_2025.json",
}


def _safe_index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    denominator = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(denominator) > 1e-6, (a - b) / denominator, np.nan)


def _catalogue() -> list[dict[str, str]]:
    if not CATALOG.is_file():
        raise FileNotFoundError(f"Selected-date catalogue not found: {CATALOG}")
    with CATALOG.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows = [row for row in rows if 2015 <= int(row["year"]) <= 2025]
    rows.sort(key=lambda row: (row["acquisition_datetime_utc"], row["item_id"]))
    counts = {year: sum(int(row["year"]) == year for row in rows) for year in YEARS}
    if len(rows) != 55 or any(counts[year] != 5 for year in YEARS):
        raise RuntimeError(f"Expected exactly 55 selected dates (5 per year, 2015–2025); found {len(rows)} rows: {counts}")
    return rows


def _scene_dir(row: dict[str, str]) -> Path:
    return ARCHIVE_ROOT / row["year"] / row["acquisition_date_utc"] / row["collection_id"] / row["item_id"]


def _available_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Return only scenes with a complete, readable six-band input set.

    A partial archive must never be padded with invented raster values.  The
    omitted catalogue records are returned verbatim enough for the UI/result
    provenance to make the reduced coverage clear.
    """
    available, unavailable = [], []
    for row in rows:
        folder = _scene_dir(row)
        missing = [band for band in BANDS if not (folder / f"{band}.tif").is_file() or (folder / f"{band}.tif").stat().st_size == 0]
        if missing:
            unavailable.append({"date": row["acquisition_date_utc"], "item_id": row["item_id"], "missing_bands": missing})
        else:
            available.append(row)
    return available, unavailable


def _input_signature(rows: list[dict[str, str]], unavailable: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(CATALOG.read_bytes())
    for row in rows:
        folder = _scene_dir(row)
        for band in (*BANDS,):
            path = folder / f"{band}.tif"
            if path.is_file() and path.stat().st_size > 0:
                stat = path.stat()
                digest.update(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode())
        for qa in ("qa_pixel.tif", "scene_classification.tif"):
            path = folder / qa
            if path.is_file():
                stat = path.stat()
                digest.update(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    digest.update(json.dumps(unavailable, sort_keys=True).encode())
    return digest.hexdigest()


def _load_synthetic_domains() -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    """Load supplied synthetic datasets and create date-joinable summaries.

    Monthly weather/ocean records are joined by acquisition year/month;
    shoreline is averaged by year and terrain is an explicitly spatial-grid
    average. These values are marked synthetic and are contextual covariates,
    never targets or observed erosion measurements.
    """
    datasets: dict[str, list[dict[str, Any]]] = {}
    for name, path in SYNTHETIC_DOMAIN_FILES.items():
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError(f"Synthetic {name} dataset has no records")
        datasets[name] = records
    weather = {(r["year"], r["month"]): r for r in datasets["rainfall_weather"]}
    ocean = {(r["year"], r["month"]): r for r in datasets["ocean_conditions"]}
    shoreline_by_year: dict[int, list[float]] = {}
    for record in datasets["shoreline_history"]:
        if record.get("annual_rate_m_yr") is not None:
            shoreline_by_year.setdefault(int(record["year"]), []).append(float(record["annual_rate_m_yr"]))
    terrain = datasets["terrain"]
    terrain_means = {key: float(statistics.fmean(float(r[key]) for r in terrain)) for key in ("elevation_m", "slope_deg", "coastal_proximity_m", "roughness_m")}
    joined: dict[str, dict[str, float]] = {}
    for year in YEARS:
        for month in range(1, 13):
            w, o = weather.get((year, month)), ocean.get((year, month))
            if not w or not o:
                continue
            joined[f"{year}-{month:02d}"] = {
                "synthetic_shoreline_annual_rate_m_yr": float(statistics.fmean(shoreline_by_year.get(year, [0.0]))),
                "synthetic_rainfall_mm": float(w["rainfall_mm"]), "synthetic_wind_speed_kmh": float(w["wind_speed_kmh"]),
                "synthetic_wave_power_kw_per_m": float(o["wave_power_kw_per_m"]), "synthetic_hs_mean_m": float(o["Hs_mean_m"]),
                **{f"synthetic_terrain_{key}": value for key, value in terrain_means.items()},
            }
    coverage = {name: {"record_count": len(records), "data_origin": "SYNTHETIC", "synthetic": True} for name, records in datasets.items()}
    coverage["join_method"] = "weather/ocean: acquisition year-month; shoreline: yearly transect mean; terrain: mean of supplied grid"
    return coverage, joined


def _reference_grid(first_band: Path) -> dict[str, Any]:
    import rasterio
    from affine import Affine
    with rasterio.open(first_band) as src:
        scale = max(1.0, math.sqrt((src.height * src.width) / 30_000))
        height = max(1, int(round(src.height / scale)))
        width = max(1, int(round(src.width / scale)))
        return {
            "shape": (height, width),
            "transform": src.transform * Affine.scale(src.width / width, src.height / height),
            "crs": src.crs,
        }


def _read_scene(row: dict[str, str], reference: dict[str, Any]) -> dict[str, np.ndarray]:
    import rasterio
    from rasterio.warp import Resampling, reproject

    folder = _scene_dir(row)
    height, width = reference["shape"]
    output: dict[str, np.ndarray] = {}
    valid = np.ones((height, width), dtype=bool)
    for band in BANDS:
        with rasterio.open(folder / f"{band}.tif") as src:
            raw = src.read(1).astype("float32")
            raw_valid = np.isfinite(raw) & (raw > 0)
            if src.nodata is not None:
                raw_valid &= raw != src.nodata
            cleaned = np.where(raw_valid, raw, np.nan).astype("float32")
            destination = np.full((height, width), np.nan, dtype="float32")
            reproject(
                source=cleaned, destination=destination,
                src_transform=src.transform, src_crs=src.crs, src_nodata=np.nan,
                dst_transform=reference["transform"], dst_crs=reference["crs"],
                dst_nodata=np.nan, resampling=Resampling.bilinear,
            )
        # Landsat Collection 2 Level-2 scale/offset vs Sentinel-2 L2A reflectance.
        if row["collection_id"] == "sentinel-2-l2a":
            output[band] = destination * 0.0001
        else:
            output[band] = destination * 0.0000275 - 0.2
        valid &= np.isfinite(destination)

    folder = _scene_dir(row)
    qa_path, scl_path = folder / "qa_pixel.tif", folder / "scene_classification.tif"
    if qa_path.is_file():
        qa = np.zeros((height, width), dtype="float32")
        with rasterio.open(qa_path) as src:
            reproject(source=rasterio.band(src, 1), destination=qa,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=reference["transform"], dst_crs=reference["crs"],
                resampling=Resampling.nearest, dst_nodata=0)
        bits = qa.astype("uint16")
        cloudy = np.zeros_like(valid)
        for bit in (1, 2, 3, 4, 5):
            cloudy |= (bits & (1 << bit)) != 0
        valid &= ~cloudy
    elif scl_path.is_file():
        scl = np.zeros((height, width), dtype="float32")
        with rasterio.open(scl_path) as src:
            reproject(source=rasterio.band(src, 1), destination=scl,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=reference["transform"], dst_crs=reference["crs"],
                resampling=Resampling.nearest, dst_nodata=0)
        valid &= ~np.isin(scl.astype("uint8"), [0, 1, 3, 8, 9, 10, 11])
    for band in BANDS:
        output[band][~valid] = np.nan
    return output


def _add_indices(scene: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    ndvi = _safe_index(scene["nir"], scene["red"])
    ndwi = _safe_index(scene["green"], scene["nir"])
    mndwi = _safe_index(scene["green"], scene["swir1"])
    with np.errstate(divide="ignore", invalid="ignore"):
        savi = 1.5 * (scene["nir"] - scene["red"]) / (scene["nir"] + scene["red"] + 0.5)
    savi[~np.isfinite(savi)] = np.nan
    return {"ndvi": ndvi, "ndwi": ndwi, "mndwi": mndwi, "savi": savi}


def _build_features(scenes: list[dict[str, np.ndarray]], dates: list[str], domain_values: dict[str, dict[str, float]]):
    indexed = [{**scene, **_add_indices(scene)} for scene in scenes]
    arrays: list[np.ndarray] = []
    names: list[str] = []
    common_observed = np.ones_like(scenes[0]["blue"], dtype=bool)
    for feature in (*BANDS, *INDICES):
        stack = np.stack([scene[feature] for scene in indexed])
        median = np.nanmedian(stack, axis=0)
        common_observed &= np.isfinite(stack).any(axis=0)
        for i, date in enumerate(dates):
            arrays.append(np.where(np.isfinite(stack[i]), stack[i], median))
            names.append(f"{feature}_{date}")
        if feature in INDICES:
            for i in range(len(dates) - 1):
                arrays.append(stack[i + 1] - stack[i])
                names.append(f"delta_{feature}_{dates[i]}_{dates[i+1]}")
    # Contextual synthetic-domain covariates are time joined, then broadcast
    # across the raster. They support reproducible development exploration but
    # cannot create spatial evidence or turn this proxy into a validated model.
    for i, date in enumerate(dates):
        values = domain_values.get(date[:7], {})
        for key, value in values.items():
            arrays.append(np.full_like(scenes[0]["blue"], value, dtype="float32"))
            names.append(f"{key}_{date}")
    stacked = np.stack(arrays, axis=-1).astype("float32")
    # XGBoost natively routes missing feature values. Retaining them is more
    # honest than filling temporal gaps with synthetic raster observations.
    valid = common_observed
    # Individual acquisitions do not share a universal valid footprint (tiles,
    # clouds and nodata differ). Use robust early/late composites rather than
    # requiring the final scene to be valid everywhere.
    early = {key: np.nanmedian(np.stack([scene[key] for scene in indexed[:min(5, len(indexed))]]), axis=0) for key in (*BANDS, *INDICES)}
    late = {key: np.nanmedian(np.stack([scene[key] for scene in indexed[-min(5, len(indexed)):]]), axis=0) for key in (*BANDS, *INDICES)}
    signal = (late["mndwi"] - early["mndwi"]) - 0.5 * (late["ndvi"] - early["ndvi"])
    valid &= np.isfinite(signal)
    return stacked.reshape(-1, stacked.shape[-1]), valid.reshape(-1), names, signal, late


def run_xgboost(force: bool = False) -> dict[str, Any]:
    catalogue_rows = _catalogue()
    rows, unavailable = _available_rows(catalogue_rows)
    if len(rows) < 2:
        raise FileNotFoundError("No usable complete six-band satellite scenes are available in the archive.")
    domain_coverage, domain_values = _load_synthetic_domains()
    signature = _input_signature(rows, unavailable)
    if not force and RESULT_JSON.exists() and RESULT_IMAGE.exists():
        try:
            cached = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
            if cached.get("input_signature") == signature:
                return cached
        except (OSError, ValueError, TypeError):
            pass

    import rasterio
    from sklearn.model_selection import train_test_split
    from xgboost import XGBClassifier

    first_band = _scene_dir(rows[0]) / "blue.tif"
    reference = _reference_grid(first_band)
    scenes = [_read_scene(row, reference) for row in rows]
    dates = [row["acquisition_date_utc"] for row in rows]
    features, valid, feature_names, signal, latest_scene = _build_features(scenes, dates, domain_values)
    valid_indices = np.flatnonzero(valid)
    signal_valid = signal.reshape(-1)[valid]
    finite_signal = np.isfinite(signal_valid)
    valid_indices = valid_indices[finite_signal]
    signal_valid = signal_valid[finite_signal]
    if signal_valid.size < 100:
        raise RuntimeError(f"Too few valid pixels for all-date XGBoost: {signal_valid.size}")

    low, high = np.nanpercentile(signal_valid, [45, 55])
    target = np.full(signal_valid.shape, -1, dtype=np.int8)
    target[signal_valid <= low] = 0
    target[signal_valid >= high] = 1
    keep = target >= 0
    x, y = features[valid_indices[keep]], target[keep]
    if np.unique(y).size < 2:
        raise RuntimeError("The spectral change proxy produced only one class.")
    if len(y) > 90_000:
        rng = np.random.default_rng(42)
        chosen = rng.choice(len(y), 90_000, replace=False)
        x, y = x[chosen], y[chosen]
    x_train, _, y_train, _ = train_test_split(x, y, test_size=0.2, random_state=42, stratify=y)
    model = XGBClassifier(n_estimators=180, max_depth=4, learning_rate=0.05,
        subsample=0.85, colsample_bytree=0.85, objective="binary:logistic",
        eval_metric="logloss", tree_method="hist", n_jobs=2, random_state=42)
    model.fit(x_train, y_train)
    all_valid = features[valid]
    probabilities = np.full(features.shape[0], np.nan, dtype="float32")
    probabilities[np.flatnonzero(valid)] = model.predict_proba(all_valid)[:, 1]
    prob_map = probabilities.reshape(reference["shape"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_result_image(latest_scene, prob_map, RESULT_IMAGE)
    importance = np.asarray(model.feature_importances_, dtype=float)
    top_idx = np.argsort(importance)[::-1][:12]
    top_features = [{"name": feature_names[int(i)], "importance": float(importance[int(i)])}
        for i in top_idx if importance[int(i)] > 0]
    pixels = int(np.isfinite(prob_map).sum())
    high_pixels = int(np.sum(prob_map >= 0.70))
    full_archive = not unavailable and len(rows) == len(catalogue_rows)
    result = {
        "status": "ok", "model": "XGBoost", "classifier": "XGBClassifier",
        "model_mode": "full_55_scene" if full_archive else "development_partial_archive",
        "data_mode": "real_satellite_plus_synthetic_domain_context" if not full_archive else "real_satellite_plus_synthetic_domain_context",
        "study_area": "Thiruvananthapuram Coast, Kerala",
        "analysis_period": "2015–2025", "input_years": list(YEARS), "input_dates": dates, "scene_count": len(rows),
        "catalogue_scene_count": len(catalogue_rows), "unavailable_scenes": unavailable,
        "satellite_coverage": {"available_scene_count": len(rows), "catalogue_scene_count": len(catalogue_rows), "real_satellite": True},
        "domain_coverage": domain_coverage,
        "scene_dates_by_year": {str(year): [row["acquisition_date_utc"] for row in rows if int(row["year"]) == year] for year in YEARS},
        "input_sensors": sorted({row.get("platform", "") for row in rows}),
        "feature_count": int(len(feature_names)), "n_estimators": 180,
        "pixels_analyzed": pixels, "training_samples": int(len(y)),
        "pseudo_positive_percent": float(np.mean(y) * 100),
        "high_score_percent": float(high_pixels / max(1, pixels) * 100),
        "mean_probability": float(np.nanmean(prob_map)) if pixels else 0.0,
        "pseudo_label": "MNDWI/NDVI first-to-last spectral-change proxy; not ground-truth erosion labels or a validated erosion probability",
        "limitations": [
            "Output is a spectral-change proxy, not a measured or validated erosion prediction.",
            "Shoreline, terrain, rainfall/weather, and ocean datasets supplied to this development run are synthetic contextual inputs and not observations.",
            *( [f"Partial archive: {len(unavailable)} selected scene(s) were excluded because required real satellite bands are unavailable."] if unavailable else []),
        ],
        "image_url": "/xgboost/result.png", "run_id": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "input_signature": signature, "top_features": top_features,
    }
    RESULT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _write_result_image(
    new: dict[str, np.ndarray],
    probability: np.ndarray,
    output_path: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    red = new["red"]
    green = new["green"]
    blue = new["blue"]
    rgb_bands = []
    for band in (red, green, blue):
        finite = np.isfinite(band)
        if not np.any(finite):
            rgb_bands.append(np.zeros_like(band, dtype="float32"))
            continue
        low, high = np.nanpercentile(band, [2, 98])
        rgb_bands.append(np.clip((band - low) / max(high - low, 1e-6), 0.0, 1.0))

    base = np.stack(rgb_bands, axis=-1)
    finite = np.isfinite(probability)
    safe_probability = np.where(finite, probability, 0.0)
    cmap = plt.get_cmap("RdYlGn_r")
    overlay = cmap(safe_probability)[..., :3].astype("float32")

    alpha = np.where(finite, 0.18 + 0.72 * safe_probability, 0.0).astype("float32")
    composite = base * (1.0 - alpha[..., None]) + overlay * alpha[..., None]
    composite[~finite] = 0.0

    plt.imsave(output_path, composite, format="png")
