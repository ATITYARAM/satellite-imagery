#!/usr/bin/env python3
"""Retrieve imagery and extract Thiruvananthapuram shorelines with CoastSat.

Reads the study polygon from config/aoi.geojson. Raw satellite imagery and
CoastSat's intermediate files are written outside ordinary Git history by
default. The extracted shoreline GeoJSON and run metadata are written under
data/shoreline_history/thiruvananthapuram/.

Install CoastSat in its recommended conda/mamba environment and set
COASTSAT_PATH to the local CoastSat repository if it is not on PYTHONPATH.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
OUTPUT_DIR = ROOT / "data" / "shoreline_history" / "thiruvananthapuram"
EXTERNAL_ROOT = Path(os.environ.get(
    "COASTSAT_DATA_DIR",
    str(ROOT / "data_external" / "shoreline_history" / "thiruvananthapuram"),
)).expanduser().resolve()
DEFAULT_START = "2015-01-01"
DEFAULT_END_EXCLUSIVE = "2026-01-01"
DEFAULT_EPSG = 32643  # UTM zone 43N, suitable for this longitude range.


def load_aoi() -> tuple[dict[str, Any], list[list[list[float]]]]:
    with AOI_PATH.open("r", encoding="utf-8") as handle:
        feature_collection = json.load(handle)
    features = feature_collection.get("features", [])
    if len(features) != 1:
        raise ValueError(
            f"Expected one AOI feature in {AOI_PATH}, found {len(features)}. "
            "CoastSat's polygon input should be split into separate runs for multiple features."
        )
    geometry = features[0].get("geometry", {})
    if geometry.get("type") != "Polygon":
        raise ValueError("The current CoastSat runner expects a Polygon AOI in config/aoi.geojson.")
    coordinates = geometry.get("coordinates", [])
    if not coordinates or len(coordinates[0]) < 4:
        raise ValueError("AOI polygon has no valid exterior ring.")
    # CoastSat input format is [outer_ring], with each point [longitude, latitude].
    polygon = [coordinates[0]]
    return feature_collection, polygon


def import_coastsat():
    """Import CoastSat from an optional local clone path."""
    candidates = []
    env_path = os.environ.get("COASTSAT_PATH")
    if env_path:
        candidates.append(Path(env_path).expanduser().resolve())
    candidates.append(ROOT / "tools" / "CoastSat")
    for candidate in candidates:
        if candidate.exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
    try:
        from coastsat import SDS_download, SDS_shoreline, SDS_tools
    except ImportError as exc:
        raise RuntimeError(
            "Could not import CoastSat. Install its dependencies in a dedicated "
            "conda/mamba environment, clone https://github.com/kvos/CoastSat, "
            "then set COASTSAT_PATH to that clone (or add it to PYTHONPATH). "
            "See data/shoreline_history/thiruvananthapuram/README.md."
        ) from exc
    return SDS_download, SDS_shoreline, SDS_tools


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default=DEFAULT_START, help="Inclusive start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", default=DEFAULT_END_EXCLUSIVE,
                        help="Exclusive end date (YYYY-MM-DD); use 2026-01-01 to cover all of 2025.")
    parser.add_argument("--cloud-thresh", type=float, default=0.5,
                        help="Maximum cloudy fraction allowed by CoastSat (0–1; default 0.5).")
    parser.add_argument("--dist-clouds", type=float, default=300,
                        help="Buffer around masked clouds in metres (default 300).")
    parser.add_argument("--output-epsg", type=int, default=DEFAULT_EPSG)
    parser.add_argument("--review", action="store_true",
                        help="Open interactive per-image shoreline review (recommended for the first run).")
    parser.add_argument("--adjust", action="store_true",
                        help="Allow manual shoreline threshold adjustment; requires interactive review.")
    parser.add_argument("--target-per-year", type=int, default=7,
                        help="Target number of distinct available acquisition dates per year (default 7).")
    parser.add_argument("--seed", type=int, default=20261028,
                        help="Deterministic per-year date-sampling seed.")
    parser.add_argument("--sitename", default="Thiruvananthapuram_Coast_2015_2025_7peryear")
    args = parser.parse_args()

    if not (0 < args.cloud_thresh <= 1):
        parser.error("--cloud-thresh must be greater than 0 and at most 1.")
    if args.adjust and not args.review:
        parser.error("--adjust requires --review.")
    try:
        start = dt.date.fromisoformat(args.start_date)
        end = dt.date.fromisoformat(args.end_date)
    except ValueError:
        parser.error("Dates must use YYYY-MM-DD.")
    if start >= end:
        parser.error("--start-date must be earlier than --end-date.")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    aoi_fc, polygon = load_aoi()
    SDS_download, SDS_shoreline, SDS_tools = import_coastsat()

    EXTERNAL_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = {
        "polygon": polygon,
        "dates": [args.start_date, args.end_date],
        # Landsat 5/7 provide early-period coverage; Landsat 8/9 and Sentinel-2
        # contribute when available. CoastSat/GEE determines actual availability.
        "sat_list": ["L5", "L7", "L8", "L9", "S2"],
        "sitename": args.sitename,
        "filepath": str(EXTERNAL_ROOT),
    }

    logging.info("AOI: %s", aoi_fc["features"][0].get("properties", {}).get("name"))
    logging.info("Date range: %s through %s (end exclusive)", args.start_date, args.end_date)
    logging.info("Raw imagery/intermediates: %s", EXTERNAL_ROOT)
    logging.info("Authenticating to Google Earth Engine via CoastSat")
    # Current CoastSat documentation recommends an Earth Engine Cloud project.
    project = os.environ.get("EARTHENGINE_PROJECT")
    if project:
        SDS_download.authenticate_and_initialize(project)
    else:
        raise RuntimeError(
            "Set EARTHENGINE_PROJECT to your registered Google Earth Engine Cloud project ID. "
            "Complete GEE/Google Cloud authentication first; see the domain README."
        )

    if args.target_per_year < 1:
        parser.error("--target-per-year must be at least 1.")

    # Query available images one calendar year at a time, then download only
    # the selected dates. CoastSat's retrieve_images() otherwise downloads
    # every eligible scene in the full date range.
    selected_dates: list[str] = []
    annual_sampling: list[dict[str, Any]] = []
    for year in range(start.year, (end - dt.timedelta(days=1)).year + 1):
        year_start = max(start, dt.date(year, 1, 1))
        year_end = min(end, dt.date(year + 1, 1, 1))
        if year_start >= year_end:
            continue
        year_inputs = dict(inputs)
        year_inputs["dates"] = [year_start.isoformat(), year_end.isoformat()]
        logging.info("Checking available shoreline imagery for %d", year)
        # Query the Tier-1 collections directly instead of check_images_available(),
        # which removes already-downloaded dates and would make reruns select new dates.
        collection_ids = {
            "L5": "LANDSAT/LT05/C02/T1_TOA",
            "L7": "LANDSAT/LE07/C02/T1_TOA",
            "L8": "LANDSAT/LC08/C02/T1_TOA",
            "L9": "LANDSAT/LC09/C02/T1_TOA",
            "S2": "COPERNICUS/S2_HARMONIZED",
        }
        available_dates: set[str] = set()
        for sat in inputs["sat_list"]:
            images = SDS_download.get_image_info(
                collection_ids[sat], sat, polygon, year_inputs["dates"]
            )
            if sat == "S2":
                images = SDS_download.filter_S2_collection(images)
            for image in images:
                timestamp = image.get("properties", {}).get("system:time_start")
                if timestamp is None:
                    continue
                acquired = dt.datetime.fromtimestamp(timestamp / 1000, tz=dt.timezone.utc).date()
                if year_start <= acquired < year_end:
                    available_dates.add(acquired.isoformat())
        ordered_dates = sorted(available_dates)
        rng = random.Random(args.seed + year)
        chosen = sorted(rng.sample(ordered_dates, min(args.target_per_year, len(ordered_dates))))
        selected_dates.extend(chosen)
        annual_sampling.append({
            "year": year,
            "available_unique_dates": len(ordered_dates),
            "target_unique_dates": args.target_per_year,
            "selected_unique_dates": len(chosen),
            "shortfall": max(0, args.target_per_year - len(chosen)),
            "selected_dates": chosen,
        })
        logging.info("%d: %d available dates; selected %d", year, len(ordered_dates), len(chosen))

    if not selected_dates:
        raise RuntimeError("CoastSat found no available acquisition dates in the requested period.")

    retrieval_failures: list[dict[str, str]] = []
    for index, selected_date in enumerate(selected_dates, start=1):
        date_end = (dt.date.fromisoformat(selected_date) + dt.timedelta(days=1)).isoformat()
        date_inputs = dict(inputs)
        date_inputs["dates"] = [selected_date, date_end]
        logging.info("Retrieving selected date %d/%d: %s", index, len(selected_dates), selected_date)
        try:
            SDS_download.retrieve_images(date_inputs)
        except Exception as exc:
            logging.exception("CoastSat retrieval failed for %s", selected_date)
            retrieval_failures.append({
                "date": selected_date,
                "error": f"{type(exc).__name__}: {exc}",
            })

    # Reload metadata from the site folder so the extraction includes every
    # selected date that was successfully downloaded, including resumed files.
    metadata = SDS_download.get_metadata(inputs)
    if not metadata or not any(metadata.get(sat, {}).get("filenames") for sat in inputs["sat_list"]):
        raise RuntimeError("CoastSat downloaded no images for the selected dates.")

    settings = {
        "cloud_thresh": args.cloud_thresh,
        "dist_clouds": args.dist_clouds,
        "output_epsg": args.output_epsg,
        "check_detection": bool(args.review),
        "adjust_detection": bool(args.adjust),
        "save_figure": True,
        "cloud_mask_issue": False,
        "sand_color": "default",
        "pan_off": False,
        "s2cloudless_prob": 60,
        "inputs": inputs,
    }
    logging.info("Extracting shorelines; interactive review=%s", args.review)
    output = SDS_shoreline.extract_shorelines(metadata, settings)
    if not output or not output.get("shorelines"):
        raise RuntimeError("CoastSat returned no accepted shorelines. Inspect cloud masks and detection figures.")

    # Keep CoastSat's native output and downloaded assets outside Git. Export a
    # GIS-friendly line layer in WGS84 for interoperability.
    gdf = SDS_tools.output_to_gdf(output, geomtype="lines")
    if gdf is None or gdf.empty:
        raise RuntimeError("No shoreline line features were available to export.")
    gdf = gdf.set_crs(epsg=args.output_epsg, allow_override=True)
    geojson_path = OUTPUT_DIR / "shoreline_lines.geojson"
    gdf.to_crs("EPSG:4326").to_file(geojson_path, driver="GeoJSON")

    dates = []
    for value in output.get("dates", []):
        try:
            dates.append(value.isoformat() if hasattr(value, "isoformat") else str(value))
        except Exception:
            dates.append(str(value))
    run_metadata = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_tool": "CoastSat",
        "source_repository": "https://github.com/kvos/CoastSat",
        "aoi_file": "config/aoi.geojson",
        "aoi_name": aoi_fc["features"][0].get("properties", {}).get("name"),
        "date_range": {"start_inclusive": args.start_date, "end_exclusive": args.end_date},
        "satellite_missions_requested": inputs["sat_list"],
        "target_unique_dates_per_year": args.target_per_year,
        "sampling_seed": args.seed,
        "annual_sampling": annual_sampling,
        "selected_acquisition_dates": selected_dates,
        "retrieval_failures": retrieval_failures,
        "output_epsg_for_extraction": args.output_epsg,
        "cloud_thresh": args.cloud_thresh,
        "dist_clouds_m": args.dist_clouds,
        "interactive_review_enabled": args.review,
        "manual_adjustment_enabled": args.adjust,
        "shoreline_feature_count": int(len(gdf)),
        "detected_dates_from_output": dates,
        "shoreline_geojson": str(geojson_path.relative_to(ROOT)),
        "raw_data_directory": str(EXTERNAL_ROOT),
        "caveats": [
            "Requested missions do not guarantee observations for every year; use the actual detection dates.",
            "Automated shoreline detections require visual quality control before scientific use.",
            "CoastSat is optimized for sandy beaches; rocky shore or seawalls may need a different method.",
            "Shoreline position can vary with tide, season, wave run-up and image georeferencing.",
            "The AOI is the existing rectangular coastal study polygon, not a municipal boundary.",
        ],
    }
    metadata_path = OUTPUT_DIR / "extraction_metadata.json"
    metadata_path.write_text(json.dumps(run_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Wrote %s", geojson_path)
    logging.info("Wrote %s", metadata_path)
    logging.info("Shoreline line features: %d", len(gdf))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        logging.exception("CoastSat shoreline workflow failed: %s", exc)
        raise SystemExit(2)
