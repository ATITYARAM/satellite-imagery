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
    signature = _input_signature(rows, unavailable) + "|satellite-scenario-overlay-v1"
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
    _write_result_image(prob_map, reference, RESULT_IMAGE)
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


def _write_result_image(probability: np.ndarray, reference: dict[str, Any], output_path: Path) -> None:
    """Render a satellite RGB basemap with separate 2026/2027 scenario overlays.

    The underlying XGBoost spectral-change calculations and result JSON are
    preserved. Scenario overlays are explicitly illustrative until real
    shoreline detections and landward normals are available.
    """
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from pyproj import Transformer

    aoi = json.loads((ROOT / "config" / "aoi.geojson").read_text(encoding="utf-8"))
    geometry = aoi["features"][0]["geometry"]
    ring_geo = np.asarray(geometry["coordinates"][0], dtype=float)
    west_lon, south_lat = ring_geo.min(axis=0)
    east_lon, north_lat = ring_geo.max(axis=0)

    archive = ROOT / "data_external" / "thiruvananthapuram_2015_2025"
    rows = []
    if CATALOG.is_file():
        with CATALOG.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    scene = None
    for row in sorted(rows, key=lambda r: r.get("acquisition_datetime_utc", ""), reverse=True):
        folder = archive / row["year"] / row["acquisition_date_utc"] / row["collection_id"] / row["item_id"]
        if all((folder / f"{band}.tif").is_file() for band in ("red", "green", "blue")):
            try:
                with rasterio.open(folder / "red.tif") as src:
                    if src.crs and src.width > 1 and src.height > 1:
                        scene = (folder, row["acquisition_date_utc"], src.crs, src.bounds)
                        break
            except Exception:
                continue

    fig, ax = plt.subplots(figsize=(12, 9), dpi=170, facecolor="#f8fafc")
    fig.subplots_adjust(left=.09, right=.97, top=.89, bottom=.12)
    ax.set_facecolor("#dbeafe")
    if scene:
        folder, scene_date, scene_crs, bounds = scene
        rgb = []
        alpha = None
        for band in ("red", "green", "blue"):
            with rasterio.open(folder / f"{band}.tif") as src:
                shape = (max(1, min(1400, src.height)), max(1, min(1400, src.width)))
                arr = src.read(1, out_shape=shape, resampling=Resampling.bilinear).astype("float32")
                valid = np.isfinite(arr)
                if src.nodata is not None:
                    valid &= arr != src.nodata
                valid &= arr > 0
                alpha = valid if alpha is None else alpha & valid
                vals = arr[valid]
                if vals.size:
                    lo, hi = np.percentile(vals, [2, 98])
                    arr = np.clip((arr - lo) / max(float(hi - lo), 1e-6), 0, 1)
                else:
                    arr[:] = 0
                rgb.append(arr)
        # Ensure RGB channels share one shape, even if a malformed archive scene differs.
        common_h = min(channel.shape[0] for channel in rgb)
        common_w = min(channel.shape[1] for channel in rgb)
        image = np.dstack([channel[:common_h, :common_w] for channel in rgb])
        if alpha is not None:
            image = np.dstack([image, alpha[:common_h, :common_w].astype("float32")])
        extent = (bounds.left, bounds.right, bounds.bottom, bounds.top)
        ax.imshow(image, extent=extent, origin="upper", interpolation="bilinear", zorder=0)
        try:
            projected_aoi = transform_bounds("EPSG:4326", scene_crs, west_lon, south_lat, east_lon, north_lat, densify_pts=21)
            ax.set_xlim(max(projected_aoi[0], extent[0]), min(projected_aoi[2], extent[1]))
            ax.set_ylim(max(projected_aoi[1], extent[2]), min(projected_aoi[3], extent[3]))
        except Exception:
            ax.set_xlim(extent[0], extent[1]); ax.set_ylim(extent[2], extent[3])
        transformer = Transformer.from_crs("EPSG:4326", scene_crs, always_xy=True)
        reverse = Transformer.from_crs(scene_crs, "EPSG:4326", always_xy=True)
        ax.set_xlabel(f"Map easting ({scene_crs})", fontsize=9)
        ax.set_ylabel("Map northing (metres)", fontsize=9)
    else:
        # Never manufacture a satellite background when the RGB archive is absent.
        scene_date, scene_crs = None, None
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        reverse = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        ax.fill(ring_geo[:, 0], ring_geo[:, 1], color="#f8fafc", zorder=0)
        ax.plot(ring_geo[:, 0], ring_geo[:, 1], color="#334155", linewidth=1.6, zorder=1)
        ax.set_xlim(west_lon, east_lon); ax.set_ylim(south_lat, north_lat)
        ax.set_xlabel("Longitude (WGS 84)", fontsize=9)
        ax.set_ylabel("Latitude (WGS 84)", fontsize=9)

    # Read the same deterministic scenario pipeline used by the forecast panel.
    try:
        from app.domains.forecast_pipeline import run_forecast
        forecast_2026 = run_forecast(2026)
        forecast_2027 = run_forecast(2027)
        years = [(2026, forecast_2026.get("transects", []), "#ef4444", "-"),
                 (2027, forecast_2027.get("transects", []), "#facc15", "--")]
    except Exception:
        years = []

    # Convert scenario points to the basemap CRS. Draw small metre-length
    # displacement ticks; direction is illustrative because no surveyed
    # shoreline normal is currently available in the source records.
    for year, transects, colour, linestyle in years:
        projected = []
        for item in sorted(transects, key=lambda row: row.get("transect_id", "")):
            x, y = transformer.transform(float(item["lon"]), float(item["lat"]))
            projected.append({**item, "x": x, "y": y})
        for i, item in enumerate(projected):
            prev_item = projected[max(0, i - 1)]
            next_item = projected[min(len(projected) - 1, i + 1)]
            tx = next_item["x"] - prev_item["x"]
            ty = next_item["y"] - prev_item["y"]
            norm = math.hypot(tx, ty) or 1.0
            nx, ny = -ty / norm, tx / norm
            metres = abs(float(item.get("forecast_displacement_m", 0.0)))
            # Prevent scenario fixtures from drawing oversized, implausible lines.
            metres = min(metres, 10.0)
            x0, y0 = item["x"], item["y"]
            x1, y1 = x0 + nx * metres, y0 + ny * metres
            ax.plot([x0, x1], [y0, y1], color=colour, linewidth=2.7 if year == 2026 else 2.2,
                    linestyle=linestyle, solid_capstyle="round", zorder=5)
            ax.scatter([x0], [y0], s=20, color="white", edgecolor=colour, linewidth=1.2, zorder=6)
            if year == 2026:
                ax.annotate(f'{item["transect_id"]}  {metres:.1f} m',
                            (x1, y1), xytext=(5, 5), textcoords="offset points",
                            fontsize=7.5, color="#991b1b", fontweight="bold", zorder=7,
                            bbox={"boxstyle":"round,pad=.2","facecolor":"white","edgecolor":"#fecaca","alpha":.94})

    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    if scene and scene_crs and getattr(scene_crs, "is_projected", False):
        bar_x, bar_y = xmin + (xmax-xmin)*.05, ymin + (ymax-ymin)*.07
        ax.plot([bar_x, bar_x+2000], [bar_y, bar_y], color="white", linewidth=5, zorder=8)
        ax.plot([bar_x, bar_x+2000], [bar_y, bar_y], color="#111827", linewidth=2.2, zorder=9)
        ax.text(bar_x+1000, bar_y+(ymax-ymin)*.012, "2 km", ha="center", va="bottom",
                fontsize=8, fontweight="bold", color="#111827",
                bbox={"facecolor":"white","edgecolor":"none","alpha":.85,"pad":2}, zorder=9)
        ax.annotate("N", xy=(xmax-(xmax-xmin)*.07, ymax-(ymax-ymin)*.08),
                    xytext=(xmax-(xmax-xmin)*.07, ymax-(ymax-ymin)*.16),
                    ha="center", fontsize=10, fontweight="bold",
                    arrowprops={"arrowstyle":"-|>","color":"white","lw":2}, zorder=9)
        ax.text(.01, .015, f"Satellite acquisition: {scene_date}",
                transform=ax.transAxes, fontsize=8, color="white", va="bottom",
                bbox={"facecolor":"#0f172a","edgecolor":"none","alpha":.75,"pad":3}, zorder=10)

    handles = [
        Line2D([], [], color="#ef4444", linewidth=2.7, linestyle="-", label="2026 scenario displacement"),
        Line2D([], [], color="#facc15", linewidth=2.2, linestyle="--", label="2027 scenario displacement"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=True, framealpha=.96,
              facecolor="white", edgecolor="#cbd5e1", fontsize=8)
    ax.set_title("Thiruvananthapuram Coast — Satellite Map & Retreat Scenarios",
                 loc="left", fontsize=14, fontweight="bold", color="#0f172a", pad=15)
    subtitle = "Coloured lines show illustrative displacement in metres; direction is not surveyed"
    if not scene:
        subtitle += " • RGB satellite scene unavailable locally; boundary-only fallback shown"
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=8.5, color="#475569", va="bottom")
    fig.text(.09, .035,
             "Scenario overlay is not a validated erosion forecast. The underlying XGBoost score remains a spectral-change proxy, not measured erosion.",
             fontsize=8, color="#475569", ha="left", va="bottom", wrap=True)
    fig.savefig(output_path, format="png", transparent=False, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
