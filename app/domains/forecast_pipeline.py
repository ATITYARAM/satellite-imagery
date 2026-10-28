"""Honest shoreline-forecast artifacts.

This module deliberately refuses to present the repository's synthetic
shoreline fixture as a scientific forecast.  It does provide a separately
labelled development preview so the result UI and API can be exercised until
reviewed CoastSat/transect observations are supplied.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "domains/shoreline_history/data/synthetic/shoreline_observations_2015_2025.json"
REAL_SHORELINES = ROOT / "data/shoreline_history/thiruvananthapuram/shoreline_lines.geojson"
OUTPUT_DIR = ROOT / "output" / "forecasts"
AOI = ROOT / "config/aoi.geojson"


def _fixture_records() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records, metadata = payload.get("records"), payload.get("metadata", {})
    if not isinstance(records, list) or not records or not metadata.get("synthetic", False):
        raise ValueError("Expected explicitly configured shoreline scenario fixture")
    return records, metadata


def _fit_trend(records: list[dict[str, Any]], year: int) -> dict[str, Any]:
    """OLS position trend using only 2015–2025 fixture values.

    The returned interval is an illustrative regression prediction interval,
    not uncertainty for real coastal change.  It is intentionally retained
    only to exercise the development UI's uncertainty handling.
    """
    records = sorted(records, key=lambda row: int(row["year"]))
    x = np.asarray([int(row["year"]) for row in records], dtype=float)
    y = np.asarray([float(row["displacement_m"]) for row in records], dtype=float)
    slope, intercept = np.polyfit(x - 2025, y, 1)
    predicted = float(intercept + slope * (year - 2025))
    residual = y - (intercept + slope * (x - 2025))
    # Standard prediction error, expanded with horizon; no confidence level is
    # claimed because the observations are synthetic fixtures.
    rmse = float(np.sqrt(np.mean(residual ** 2))) if len(y) else 0.0
    horizon = year - 2025
    interval = float(math.sqrt(rmse ** 2 * (1 + horizon / max(1, len(y))) + 15.0 ** 2))
    retreat_rate = float(slope)
    if retreat_rate <= -2:
        risk = "high"
    elif retreat_rate <= -1:
        risk = "moderate"
    else:
        risk = "low"
    last = records[-1]
    return {
        "transect_id": last["transect_id"], "lat": float(last["lat"]), "lon": float(last["lon"]),
        "forecast_displacement_m": predicted, "forecast_annual_rate_m_yr": retreat_rate,
        "interval_plus_minus_m": interval, "risk_category": risk,
        "observation_count": len(records), "source": "SYNTHETIC_DEVELOPMENT_FIXTURE",
    }


def _render_preview(year: int, transects: list[dict[str, Any]], output: Path) -> None:
    """Render a satellite-backed forecast scenario with metre-scale overlays."""
    import csv
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyArrowPatch
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from pyproj import Transformer

    aoi = json.loads(AOI.read_text(encoding="utf-8"))
    ring_wgs84 = np.asarray(aoi["features"][0]["geometry"]["coordinates"][0], dtype=float)
    min_lon, min_lat = ring_wgs84.min(axis=0)
    max_lon, max_lat = ring_wgs84.max(axis=0)
    archive_root = ROOT / "data_external" / "thiruvananthapuram_2015_2025"
    catalogue = ROOT / "data" / "satellite" / "thiruvananthapuram_2015_2025" / "catalog" / "selected_dates.csv"

    # Prefer the latest usable real satellite RGB scene, then step backwards.
    candidates: list[dict[str, str]] = []
    if catalogue.is_file():
        with catalogue.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in sorted(rows, key=lambda r: r.get("acquisition_datetime_utc", ""), reverse=True):
            folder = archive_root / row["year"] / row["acquisition_date_utc"] / row["collection_id"] / row["item_id"]
            if all((folder / f"{band}.tif").is_file() for band in ("red", "green", "blue")):
                candidates.append({"folder": str(folder), "date": row["acquisition_date_utc"], "item": row["item_id"]})
    # Prefer the scene with the largest usable RGB footprint, not simply
    # the newest file: some catalogue scenes have only a narrow valid strip.
    satellite = None
    scene_date = None
    best_rgb_coverage = -1.0
    for candidate in candidates:
        try:
            folder = Path(candidate["folder"])
            channels, common_valid = [], None
            with rasterio.open(folder / "red.tif") as src:
                if src.width <= 1 or src.height <= 1 or not src.crs:
                    continue
                sample_shape = (min(500, src.height), min(500, src.width))
                bounds = src.bounds
                scene_crs, scene_transform = src.crs, src.transform
                scene_width, scene_height = src.width, src.height
            for band in ("red", "green", "blue"):
                with rasterio.open(folder / f"{band}.tif") as src:
                    sample = src.read(1, out_shape=sample_shape, resampling=Resampling.nearest).astype("float32")
                    valid = np.isfinite(sample) & (sample > 0)
                    if src.nodata is not None:
                        valid &= sample != src.nodata
                    common_valid = valid if common_valid is None else (common_valid & valid)
            coverage = float(common_valid.mean()) if common_valid is not None else 0.0
            if coverage > best_rgb_coverage:
                best_rgb_coverage = coverage
                satellite = (folder, scene_crs, scene_transform, scene_width, scene_height, bounds, coverage)
                scene_date = candidate["date"]
        except Exception:
            continue

    colours = {"low": "#f59e0b", "moderate": "#f97316", "high": "#dc2626"}
    fig, ax = plt.subplots(figsize=(12, 8.2), dpi=180, facecolor="#f8fafc")
    fig.subplots_adjust(left=.09, right=.97, top=.84, bottom=.12)
    ax.set_facecolor("#dbeafe")
    image_extent = None
    map_crs = None
    if satellite:
        folder, map_crs, transform, width, height, bounds, rgb_coverage = satellite
        max_dim = 1400
        scale = max(1, int(math.ceil(max(width, height) / max_dim)))
        rgb = []
        rgb_valid = None
        for band in ("red", "green", "blue"):
            with rasterio.open(folder / f"{band}.tif") as src:
                arr = src.read(1, out_shape=(max(1, src.height // scale), max(1, src.width // scale)), resampling=Resampling.bilinear).astype("float32")
                valid = np.isfinite(arr)
                if src.nodata is not None:
                    valid &= arr != src.nodata
                valid &= arr > 0
                rgb_valid = valid if rgb_valid is None else (rgb_valid & valid)
                vals = arr[valid]
                if vals.size:
                    lo, hi = np.percentile(vals, (2, 98))
                    arr = np.clip((arr - lo) / max(float(hi - lo), 1e-6), 0, 1)
                else:
                    arr[:] = 0
                rgb.append(arr)
        image = np.dstack([*rgb, rgb_valid.astype("float32") if rgb_valid is not None else np.ones_like(rgb[0])])
        with rasterio.open(folder / "red.tif") as src:
            image_extent = (src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top)
            map_crs = src.crs
            # Transform from the downsampled image pixels back to map metres.
            from rasterio.transform import Affine
            image_transform = src.transform * Affine.scale(src.width / image.shape[1], src.height / image.shape[0])
        ax.imshow(image, extent=image_extent, origin="upper", interpolation="nearest", zorder=0)
        # Limit to the configured AOI while respecting the scene's actual footprint.
        try:
            aoi_bounds = transform_bounds("EPSG:4326", map_crs, min_lon, min_lat, max_lon, max_lat, densify_pts=21)
            ax.set_xlim(max(aoi_bounds[0], image_extent[0]), min(aoi_bounds[2], image_extent[1]))
            ax.set_ylim(max(aoi_bounds[1], image_extent[2]), min(aoi_bounds[3], image_extent[3]))
        except Exception:
            ax.set_xlim(image_extent[0], image_extent[1]); ax.set_ylim(image_extent[2], image_extent[3])
        to_map = Transformer.from_crs("EPSG:4326", map_crs, always_xy=True)
        to_geo = Transformer.from_crs(map_crs, "EPSG:4326", always_xy=True)
        # Coordinate grid and scale use the image's native projected CRS.
        ax.set_xlabel(f"Projected easting ({map_crs})", fontsize=9)
        ax.set_ylabel("Projected northing (metres)", fontsize=9)
    else:
        # Honest fallback: no satellite imagery is fabricated when the archive is absent.
        ax.fill(ring_wgs84[:, 0], ring_wgs84[:, 1], color="#f8fafc", zorder=0)
        ax.plot(ring_wgs84[:, 0], ring_wgs84[:, 1], color="#334155", linewidth=1.8, zorder=1)
        ax.set_xlim(min_lon, max_lon); ax.set_ylim(min_lat, max_lat)
        to_map = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        to_geo = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
        ax.set_xlabel("Longitude (WGS 84)", fontsize=9)
        ax.set_ylabel("Latitude (WGS 84)", fontsize=9)

    # Scenario coordinates can fall in a masked part of the scene. Snap only
    # to a nearby valid RGB pixel (within 2.5 km); never teleport a marker across
    # the map. This is a cartographic placement aid, not shoreline detection.
    projected = []
    for item in sorted(transects, key=lambda row: row["transect_id"]):
        x, y = to_map.transform(float(item["lon"]), float(item["lat"]))
        if satellite and rgb_valid is not None and getattr(map_crs, "is_projected", False):
            try:
                col_f, row_f = (~image_transform) * (x, y)
                row0, col0 = int(round(row_f)), int(round(col_f))
                px_x = abs(float(image_transform.a)) or 1.0
                px_y = abs(float(image_transform.e)) or 1.0
                radius_x = min(rgb_valid.shape[1], int(math.ceil(2500 / px_x)))
                radius_y = min(rgb_valid.shape[0], int(math.ceil(2500 / px_y)))
                r1, r2 = max(0, row0-radius_y), min(rgb_valid.shape[0], row0+radius_y+1)
                c1, c2 = max(0, col0-radius_x), min(rgb_valid.shape[1], col0+radius_x+1)
                if r1 < r2 and c1 < c2:
                    local = np.argwhere(rgb_valid[r1:r2, c1:c2])
                    if local.size:
                        candidates_rc = local + np.array([r1, c1])
                        xs = image_transform.c + (candidates_rc[:, 1] + .5) * image_transform.a
                        ys = image_transform.f + (candidates_rc[:, 0] + .5) * image_transform.e
                        distance = np.hypot(xs - x, ys - y)
                        nearest = int(np.argmin(distance))
                        if distance[nearest] <= 2500:
                            x, y = float(xs[nearest]), float(ys[nearest])
            except Exception:
                pass
        projected.append({**item, "x": x, "y": y})

    # The transect locations define a local along-coast tangent. Draw a red
    # displacement vector perpendicular to that tangent, with length in metres.
    for i, item in enumerate(projected):
        prev_item = projected[max(0, i - 1)]
        next_item = projected[min(len(projected) - 1, i + 1)]
        tx, ty = next_item["x"] - prev_item["x"], next_item["y"] - prev_item["y"]
        norm = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / norm, tx / norm
        # Direction is illustrative because no surveyed landward normal is available.
        retreat_m = abs(float(item["forecast_displacement_m"]))
        x0, y0 = item["x"], item["y"]
        x1, y1 = x0 + nx * retreat_m, y0 + ny * retreat_m
        if satellite and map_crs and getattr(map_crs, "is_projected", False):
            ax.plot([x0, x1], [y0, y1], color="#ef4444", linewidth=2.8, zorder=5, solid_capstyle="round")
            ax.scatter([x0], [y0], s=26, color="#fff", edgecolor="#ef4444", linewidth=1.3, zorder=6)
            ax.scatter([x1], [y1], s=25, color="#ef4444", edgecolor="white", linewidth=.7, zorder=6)
            ax.annotate(f'{item["transect_id"]}: {retreat_m:.1f} m',
                        (x1, y1), xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color="#991b1b", fontweight="bold", zorder=7,
                        bbox={"boxstyle":"round,pad=.22","facecolor":"white","edgecolor":"#fecaca","alpha":.94})
        else:
            # No metre-accurate satellite CRS: show the scenario marker, not a fake metre-scale line.
            ax.scatter([x0], [y0], s=75, color=colours[item["risk_category"]],
                       edgecolor="white", linewidth=1.1, zorder=5)
            ax.annotate(f'{item["transect_id"]}: {retreat_m:.1f} m',
                        (x0, y0), xytext=(5, 5), textcoords="offset points",
                        fontsize=8, color="#991b1b", fontweight="bold", zorder=6,
                        bbox={"boxstyle":"round,pad=.22","facecolor":"white","edgecolor":"#fecaca","alpha":.94})

    if satellite and map_crs and getattr(map_crs, "is_projected", False):
        xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
        bar_x, bar_y = xmin + (xmax-xmin)*.05, ymin + (ymax-ymin)*.07
        ax.plot([bar_x, bar_x+2000], [bar_y, bar_y], color="white", linewidth=5, zorder=8)
        ax.plot([bar_x, bar_x+2000], [bar_y, bar_y], color="#0f172a", linewidth=2.2, zorder=9)
        ax.text(bar_x+1000, bar_y+(ymax-ymin)*.012, "2 km", ha="center", va="bottom",
                color="#0f172a", fontsize=8, fontweight="bold",
                bbox={"facecolor":"white","edgecolor":"none","alpha":.85,"pad":2}, zorder=9)
        ax.annotate("N", xy=(xmax-(xmax-xmin)*.07, ymax-(ymax-ymin)*.08),
                    xytext=(xmax-(xmax-xmin)*.07, ymax-(ymax-ymin)*.16),
                    ha="center", fontsize=10, fontweight="bold",
                    arrowprops={"arrowstyle":"-|>","color":"white","lw":2}, zorder=9)
        ax.text(.01, .015, f"Satellite scene: {scene_date} • Source archive: Microsoft Planetary Computer",
                transform=ax.transAxes, fontsize=8, color="white", va="bottom",
                bbox={"facecolor":"#0f172a","edgecolor":"none","alpha":.75,"pad":3}, zorder=10)
    ax.grid(False)
    ax.set_title(f"Thiruvananthapuram Coast — {year} Shoreline Retreat Scenario",
                 loc="left", fontsize=15, fontweight="bold", color="#0f172a", pad=16)
    subtitle = "Red lines show scenario displacement in metres • Direction is illustrative; shoreline baseline not surveyed"
    if not satellite:
        subtitle += " • Satellite archive RGB unavailable locally"
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, fontsize=9, color="#475569", va="bottom")
    handles = [
        Line2D([], [], color="#ef4444", linewidth=2.8, label="Illustrative retreat distance (m)"),
        Line2D([], [], marker="o", linestyle="", color="#fff", markeredgecolor="#ef4444", label="Scenario transect location"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=True, framealpha=.96,
              facecolor="white", edgecolor="#cbd5e1", fontsize=8)
    fig.text(.09, .035,
             "Illustrative scenario only—not a real-time or validated erosion forecast. Red-line lengths represent scenario displacement; direction is not surveyed.",
             fontsize=8, color="#475569", ha="left", va="bottom", wrap=True)
    fig.savefig(output, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

def run_forecast(year: int, force: bool = False) -> dict[str, Any]:
    if year not in (2026, 2027):
        raise ValueError("Forecast year must be 2026 or 2027")
    records, metadata = _fixture_records()
    signature = hashlib.sha256(FIXTURE.read_bytes() + b"|coastal-framing-rgb-coverage-snap-v4").hexdigest()
    year_dir = OUTPUT_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    output, result_path, geojson_path = year_dir / "forecast_map.png", year_dir / "forecast.json", year_dir / "transects.geojson"
    if not force and output.is_file() and result_path.is_file():
        cached = json.loads(result_path.read_text(encoding="utf-8"))
        if cached.get("input_signature") == signature and cached.get("artifact_urls") and cached.get("quality_warnings"):
            return cached
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["transect_id"])].append(record)
    transects = [_fit_trend(rows, year) for _, rows in sorted(grouped.items())]
    retreat = [item for item in transects if item["forecast_annual_rate_m_yr"] < 0]
    # Atomic replacement prevents an image request seeing a half-written map.
    temp_image = output.with_suffix(".tmp.png")
    _render_preview(year, transects, temp_image)
    os.replace(temp_image, output)
    feature_collection = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]}, "properties": {**row, "forecast_year": year, "forecast_horizon_years": year - 2025, "units": "m; m/year", "synthetic": True}}
        for row in transects
    ], "properties": {"data_mode": "synthetic_development_preview", "crs": "EPSG:4326", "target": "cross-shore shoreline displacement", "negative_displacement": "retreat"}}
    temp_geojson = geojson_path.with_suffix(".tmp.json")
    temp_geojson.write_text(json.dumps(feature_collection, indent=2), encoding="utf-8")
    os.replace(temp_geojson, geojson_path)
    result = {
        "status": "ok", "forecast_year": year, "forecast_origin": "2025-12-31", "forecast_horizon": year - 2025,
        "data_mode": "synthetic_development_preview", "scientific_forecast_available": False,
        "model_name": "Illustrative per-transect OLS trend scenario baseline",
        "target_name": "cross-shore shoreline displacement", "units": {"displacement": "m", "rate": "m/year", "crs": "EPSG:4326"},
        "model": {"trend_baseline": "development fixture OLS per transect", "xgboost_regression": "unavailable: no genuine aligned shoreline targets"},
        "target": "cross-shore shoreline displacement (m); negative means retreat",
        "image_url": f"/forecast/{year}/map.png", "artifact_urls": {"map": f"/forecast/{year}/map.png", "transects_geojson": f"/forecast/{year}/transects.geojson"}, "transects": transects,
        "summary": {"transect_count": len(transects), "retreating_transect_count": len(retreat), "mean_displacement_m": float(np.mean([x['forecast_displacement_m'] for x in transects])), "mean_retreat_rate_m_yr": float(np.mean([x['forecast_annual_rate_m_yr'] for x in transects]))},
        "risk_thresholds": {"high": "rate <= -2 m/year", "moderate": "-2 < rate <= -1 m/year", "low": "rate > -1 m/year"},
        "validation": {"available": False, "reason": "No genuine held-out shoreline measurements are available; metrics are intentionally not calculated."},
        "uncertainty": {"available": True, "type": "illustrative scenario trend interval", "units": "m", "warning": "Not an uncertainty estimate for real coastal change."},
        "features_or_inputs": {"shoreline_history": "illustrative annual scenario, 2015–2025", "satellite": "not used as a shoreline target", "terrain_weather_ocean": "not used for this baseline"},
        "quality_warnings": ["No reviewed real shoreline detections or fixed transect intersections are available.", "Scenario values and coordinates are illustrative development data, not measured observations."],
        "real_data_status": {"reviewed_shoreline_observations_available": REAL_SHORELINES.is_file(), "reason": "No reviewed CoastSat/transect-intersection target series is committed."},
        "limitations": ["This is an illustrative development scenario, not a validated coastal forecast.", "Scenario fixture records are not real targets and are not used to validate XGBoost.", "A real forecast requires reviewed shoreline detections, fixed transects, tide/quality handling, and chronological backtesting."],
        "input_signature": signature,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    temp_result = result_path.with_suffix(".tmp.json")
    temp_result.write_text(json.dumps(result, indent=2), encoding="utf-8")
    os.replace(temp_result, result_path)
    return result


def forecast_image(year: int) -> Path:
    run_forecast(year)
    path = OUTPUT_DIR / str(year) / "forecast_map.png"
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("Forecast map was not created")
    return path
