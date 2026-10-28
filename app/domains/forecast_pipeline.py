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
        raise ValueError("Expected explicitly synthetic shoreline development fixture")
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
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    aoi = json.loads(AOI.read_text(encoding="utf-8"))
    ring = np.asarray(aoi["features"][0]["geometry"]["coordinates"][0])
    colours = {"low": "#38a169", "moderate": "#f6ad55", "high": "#e53e3e"}
    fig, ax = plt.subplots(figsize=(10.8, 8.2), dpi=160, facecolor="white")
    ax.set_facecolor("#eef3f5")
    ax.fill(ring[:, 0], ring[:, 1], color="#f8fafc", zorder=0)
    ax.plot(ring[:, 0], ring[:, 1], "--", color="#172554", linewidth=1.5, label="Study-area boundary")
    for item in transects:
        color = colours[item["risk_category"]]
        ax.scatter(item["lon"], item["lat"], s=90, color=color, edgecolor="#0f172a", linewidth=.7, zorder=3)
        ax.annotate(f"{item['transect_id']}\n{item['forecast_displacement_m']:+.1f} m", (item["lon"], item["lat"]), xytext=(5, 6), textcoords="offset points", fontsize=7, zorder=4)
    ax.set_xlim(ring[:, 0].min(), ring[:, 0].max()); ax.set_ylim(ring[:, 1].min(), ring[:, 1].max())
    ax.set_xlabel("Longitude (WGS 84)"); ax.set_ylabel("Latitude (WGS 84)")
    ax.grid(True, alpha=.25)
    ax.set_title(f"{year} synthetic development preview — shoreline trend baseline", fontweight="bold")
    ax.text(.02, .98, "NOT A REAL FORECAST\nSynthetic fixture locations and positions\nNegative displacement = retreat", transform=ax.transAxes, va="top", fontsize=9, fontweight="bold", color="#7f1d1d", bbox={"facecolor":"#fff1f2", "edgecolor":"#fb7185", "boxstyle":"round,pad=.4"})
    handles = [Line2D([], [], marker="o", linestyle="", color=c, markeredgecolor="#0f172a", label=label.title()) for label, c in colours.items()]
    handles.append(Line2D([], [], color="#172554", linestyle="--", label="Study-area boundary"))
    ax.legend(handles=handles, title="Illustrative retreat-rate risk", loc="lower right", fontsize=8)
    fig.text(.5, .012, "Development fixture only. Replace with reviewed transect intersections from genuine shoreline observations before scientific forecasting.", ha="center", fontsize=8, color="#7f1d1d")
    fig.tight_layout(rect=(0,.035,1,1)); fig.savefig(output, facecolor="white"); plt.close(fig)


def run_forecast(year: int, force: bool = False) -> dict[str, Any]:
    if year not in (2026, 2027):
        raise ValueError("Forecast year must be 2026 or 2027")
    records, metadata = _fixture_records()
    signature = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output, result_path = OUTPUT_DIR / f"forecast_{year}_development.png", OUTPUT_DIR / f"forecast_{year}.json"
    if not force and output.is_file() and result_path.is_file():
        cached = json.loads(result_path.read_text(encoding="utf-8"))
        if cached.get("input_signature") == signature:
            return cached
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record["transect_id"])].append(record)
    transects = [_fit_trend(rows, year) for _, rows in sorted(grouped.items())]
    retreat = [item for item in transects if item["forecast_annual_rate_m_yr"] < 0]
    _render_preview(year, transects, output)
    result = {
        "status": "ok", "forecast_year": year, "forecast_origin": "2025-12-31",
        "data_mode": "synthetic_development_preview", "scientific_forecast_available": False,
        "model": {"trend_baseline": "development fixture OLS per transect", "xgboost_regression": "unavailable: no genuine aligned shoreline targets"},
        "target": "cross-shore shoreline displacement (m); negative means retreat",
        "image_url": f"/forecast/{year}/map.png", "transects": transects,
        "summary": {"transect_count": len(transects), "retreating_transect_count": len(retreat), "mean_displacement_m": float(np.mean([x['forecast_displacement_m'] for x in transects])), "mean_retreat_rate_m_yr": float(np.mean([x['forecast_annual_rate_m_yr'] for x in transects]))},
        "risk_thresholds": {"high": "rate <= -2 m/year", "moderate": "-2 < rate <= -1 m/year", "low": "rate > -1 m/year"},
        "validation": {"available": False, "reason": "No genuine held-out shoreline measurements are available; metrics are intentionally not calculated."},
        "real_data_status": {"reviewed_shoreline_observations_available": REAL_SHORELINES.is_file(), "reason": "No reviewed CoastSat/transect-intersection target series is committed."},
        "limitations": ["This is a synthetic development preview, not a coastal forecast.", "Synthetic fixture records are never used as real targets or to validate XGBoost.", "A real forecast requires reviewed shoreline detections, fixed transects, tide/quality handling, and chronological backtesting."],
        "input_signature": signature,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def forecast_image(year: int) -> Path:
    run_forecast(year)
    path = OUTPUT_DIR / f"forecast_{year}_development.png"
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("Forecast map was not created")
    return path
