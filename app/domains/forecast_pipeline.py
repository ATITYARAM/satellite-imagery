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
OUTPUT_DIR = ROOT / "outputs/forecasts"
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
    """Render a clean, geographic scenario map without modifying the proxy map."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Rectangle

    aoi = json.loads(AOI.read_text(encoding="utf-8"))
    ring = np.asarray(aoi["features"][0]["geometry"]["coordinates"][0], dtype=float)
    min_lon, min_lat = ring.min(axis=0)
    max_lon, max_lat = ring.max(axis=0)
    mean_lat = float((min_lat + max_lat) / 2)
    # Approximate local scale in longitude degrees at the AOI latitude.
    km_per_lon_degree = 111.32 * math.cos(math.radians(mean_lat))
    scale_2km_lon = 2.0 / km_per_lon_degree

    colours = {"low": "#16803c", "moderate": "#d97706", "high": "#dc2626"}
    fig, ax = plt.subplots(figsize=(12, 9), dpi=180, facecolor="#f8fafc")
    fig.subplots_adjust(left=.10, right=.97, top=.90, bottom=.13)
    ax.set_facecolor("#edf4f7")

    # AOI mask/background: explicitly show the study boundary, not an invented coastline.
    ax.fill(ring[:, 0], ring[:, 1], color="#f8fafc", zorder=0)
    ax.plot(ring[:, 0], ring[:, 1], color="#334155", linewidth=1.8, zorder=1, label="Study-area boundary")

    # Draw a restrained, labelled geographic grid.
    ax.set_xlim(min_lon, max_lon)
    ax.set_ylim(min_lat, max_lat)
    ax.set_xticks(np.linspace(min_lon, max_lon, 6))
    ax.set_yticks(np.linspace(min_lat, max_lat, 6))
    ax.grid(True, color="#94a3b8", linewidth=.6, alpha=.45, zorder=0)
    ax.tick_params(labelsize=8, colors="#334155")

    # Show forecast locations only; do not imply that points are a measured shoreline.
    for item in sorted(transects, key=lambda row: row["transect_id"]):
        color = colours[item["risk_category"]]
        ax.scatter(item["lon"], item["lat"], s=115, color=color, edgecolor="white",
                   linewidth=1.4, zorder=4)
        ax.annotate(
            f'{item["transect_id"]}  {item["forecast_displacement_m"]:+.1f} m',
            (item["lon"], item["lat"]), xytext=(7, 7), textcoords="offset points",
            fontsize=8, color="#0f172a", fontweight="semibold", zorder=5,
            bbox={"boxstyle": "round,pad=.25", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": .94},
        )

    # Approximate 2 km scale bar, appropriate for this small geographic extent.
    bar_x = min_lon + (max_lon - min_lon) * .055
    bar_y = min_lat + (max_lat - min_lat) * .065
    ax.plot([bar_x, bar_x + scale_2km_lon], [bar_y, bar_y], color="#0f172a",
            linewidth=4, solid_capstyle="butt", zorder=6)
    ax.plot([bar_x, bar_x], [bar_y - .0007, bar_y + .0007], color="#0f172a", linewidth=1.5, zorder=6)
    ax.plot([bar_x + scale_2km_lon, bar_x + scale_2km_lon],
            [bar_y - .0007, bar_y + .0007], color="#0f172a", linewidth=1.5, zorder=6)
    ax.text(bar_x + scale_2km_lon / 2, bar_y + .0016, "2 km (approx.)",
            ha="center", va="bottom", fontsize=8, color="#0f172a", fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": .85, "pad": 2}, zorder=7)

    # North arrow.
    arrow_x = max_lon - (max_lon - min_lon) * .075
    arrow_y = max_lat - (max_lat - min_lat) * .12
    ax.annotate("N", xy=(arrow_x, arrow_y), xytext=(arrow_x, arrow_y - .012),
                ha="center", va="center", fontsize=10, fontweight="bold",
                arrowprops={"arrowstyle": "-|>", "color": "#0f172a", "lw": 1.5}, zorder=7)

    handles = [
        Line2D([], [], marker="o", linestyle="", color=colours["low"], markeredgecolor="white", label="Lower scenario rate"),
        Line2D([], [], marker="o", linestyle="", color=colours["moderate"], markeredgecolor="white", label="Moderate scenario rate"),
        Line2D([], [], marker="o", linestyle="", color=colours["high"], markeredgecolor="white", label="Higher scenario rate"),
        Line2D([], [], color="#334155", linewidth=1.8, label="Study-area boundary"),
    ]
    ax.legend(handles=handles, loc="upper left", frameon=True, framealpha=.97,
              facecolor="white", edgecolor="#cbd5e1", fontsize=8, title="Map key", title_fontsize=9)

    ax.set_xlabel("Longitude (WGS 84)", fontsize=9, labelpad=8)
    ax.set_ylabel("Latitude (WGS 84)", fontsize=9, labelpad=8)
    ax.set_title(f"Thiruvananthapuram Coast — {year} Shoreline Scenario",
                 loc="left", fontsize=15, fontweight="bold", color="#0f172a", pad=18)
    ax.text(0, 1.015,
            "Scenario locations and trend estimates • Forecast origin: end of 2025 • Negative displacement = retreat",
            transform=ax.transAxes, fontsize=9, color="#475569", va="bottom")
    fig.text(.10, .045,
             "Illustrative scenario, not a real-time observation or validated erosion forecast. "
             "The boundary is the configured study area; no coastline is inferred.",
             fontsize=8, color="#475569", ha="left", va="bottom", wrap=True)
    fig.savefig(output, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)

def run_forecast(year: int, force: bool = False) -> dict[str, Any]:
    if year not in (2026, 2027):
        raise ValueError("Forecast year must be 2026 or 2027")
    records, metadata = _fixture_records()
    signature = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
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
