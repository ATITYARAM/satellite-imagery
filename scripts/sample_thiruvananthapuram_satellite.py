#!/usr/bin/env python3
"""Catalogue and reproducibly sample Thiruvananthapuram coastal satellite scenes.

Uses the existing config/aoi.geojson polygon, queries real Microsoft Planetary
Computer STAC items, samples up to N distinct acquisition dates per year, and
optionally downloads/clips the selected optical bands and quality layer.

Large raster files are written outside Git by default to data_external/. The
date manifest and catalogue metadata are written inside data/satellite/ so they
can be reviewed and committed. No missing acquisition dates are fabricated.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import logging
import os
import random
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import planetary_computer
import pystac
import pystac_client
import rasterio
import requests
from rasterio.mask import mask
from rasterio.warp import transform_geom
from shapely.geometry import box, shape

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
ARCHIVE = ROOT / "data" / "satellite" / "thiruvananthapuram_2015_2025"
CATALOG_DIR = ARCHIVE / "catalog"
METADATA_DIR = ARCHIVE / "metadata"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"
COLLECTIONS = ("landsat-c2-l2", "sentinel-2-l2a")
START_YEAR = 2015
END_YEAR = 2025
DEFAULT_SEED = 20261028
DEFAULT_TARGET = 7

# Standardized output names -> source asset key, by collection.
BAND_ASSETS = {
    "landsat-c2-l2": {
        "blue": "blue", "green": "green", "red": "red",
        "nir": "nir08", "swir1": "swir16", "swir2": "swir22",
        "qa_pixel": "qa_pixel",
    },
    "sentinel-2-l2a": {
        "blue": "B02", "green": "B03", "red": "B04",
        "nir": "B08", "swir1": "B11", "swir2": "B12",
        "scene_classification": "SCL",
    },
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_aoi() -> tuple[dict[str, Any], Any, list[float]]:
    with AOI_PATH.open("r", encoding="utf-8") as handle:
        feature_collection = json.load(handle)
    features = feature_collection.get("features", [])
    if not features:
        raise RuntimeError(f"No features found in {AOI_PATH}")
    # The configured study AOI currently contains one polygon. Union features
    # if more are added later, without silently replacing the study boundary.
    from shapely.ops import unary_union
    geometry = unary_union([shape(feature["geometry"]) for feature in features])
    if geometry.is_empty or not geometry.is_valid:
        raise RuntimeError("Configured AOI geometry is empty or invalid.")
    return feature_collection, geometry, list(geometry.bounds)


def ensure_dirs() -> None:
    for path in (CATALOG_DIR, METADATA_DIR):
        path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def catalogue_items(aoi_geometry: Any, start_year: int, end_year: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Query by the small AOI bounding box; apply exact geometry filtering locally.

    Searching by bbox avoids sending a large polygon in the STAC POST body.
    """
    catalog = pystac_client.Client.open(STAC_URL)
    bounds = list(aoi_geometry.bounds)
    items_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    query_log: list[dict[str, Any]] = []
    query_total = (end_year - start_year + 1) * len(COLLECTIONS)
    completed = 0

    for year in range(start_year, end_year + 1):
        start = f"{year}-01-01T00:00:00Z"
        end = f"{year}-12-31T23:59:59Z"
        for collection_id in COLLECTIONS:
            completed += 1
            query = {
                "year": year, "collection_id": collection_id,
                "status": "failed", "item_count": 0, "error": "",
            }
            for attempt in range(1, 4):
                try:
                    logging.info("[%d/%d] %s %s (attempt %d)", completed, query_total, year, collection_id, attempt)
                    search = catalog.search(
                        collections=[collection_id],
                        bbox=bounds,
                        datetime=f"{start}/{end}",
                        max_items=None,
                    )
                    count = 0
                    for item in search.items():
                        if not item.datetime or item.datetime.year != year:
                            continue
                        if not item.geometry:
                            continue
                        footprint = shape(item.geometry)
                        if not footprint.intersects(aoi_geometry):
                            continue
                        item_dict = item.to_dict()
                        props = item_dict.get("properties", {})
                        acquired = item.datetime.astimezone(dt.timezone.utc)
                        row = {
                            "year": year,
                            "acquisition_date_utc": acquired.date().isoformat(),
                            "acquisition_datetime_utc": acquired.isoformat(),
                            "collection_id": collection_id,
                            "item_id": item.id,
                            "platform": props.get("platform"),
                            "cloud_cover_percent": props.get("eo:cloud_cover"),
                            "processing_level": props.get("landsat:processing_level") or props.get("processing:level"),
                            "product_id": props.get("landsat:product_id") or props.get("s2:product_uri") or props.get("s2:product_id"),
                            "item_json": item_dict,
                        }
                        items_by_key[(collection_id, item.id)] = row
                        count += 1
                    query["status"] = "complete"
                    query["item_count"] = count
                    query["error"] = ""
                    break
                except Exception as exc:
                    query["error"] = f"{type(exc).__name__}: {exc}"
                    if attempt < 3:
                        time.sleep(2 ** attempt)
            query["updated_utc"] = utc_now()
            query_log.append(query)
            if query["status"] == "failed":
                logging.error("Query failed for %s/%s: %s", year, collection_id, query["error"])
            else:
                logging.info("Found %d intersecting items for %s/%s", query["item_count"], year, collection_id)

    return list(items_by_key.values()), query_log


def sample_dates(
    items: list[dict[str, Any]], query_log: list[dict[str, Any]],
    start_year: int, end_year: int, target: int, seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Choose unique dates; for each date select one best scene deterministically."""
    by_year_date: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in items:
        by_year_date[int(row["year"])][row["acquisition_date_utc"]].append(row)

    query_failures_by_year: dict[int, int] = Counter()
    for query in query_log:
        if query["status"] != "complete":
            query_failures_by_year[int(query["year"])] += 1

    selected: list[dict[str, Any]] = []
    annual: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        dates = sorted(by_year_date.get(year, {}).keys())
        rng = random.Random(seed + year)
        if len(dates) > target:
            chosen_dates = sorted(rng.sample(dates, target))
        else:
            chosen_dates = dates

        for date in chosen_dates:
            same_date = by_year_date[year][date]
            def scene_rank(row: dict[str, Any]) -> tuple[float, int, str, str]:
                cloud = row.get("cloud_cover_percent")
                try:
                    cloud_value = float(cloud) if cloud is not None else 100.0
                except (TypeError, ValueError):
                    cloud_value = 100.0
                # Prefer lower reported cloud; then Sentinel-2 at equal cloud
                # because its optical bands have finer spatial resolution.
                collection_priority = 0 if row["collection_id"] == "sentinel-2-l2a" else 1
                return (cloud_value, collection_priority, row["collection_id"], row["item_id"])
            best = sorted(same_date, key=scene_rank)[0]
            selected.append({
                "year": year,
                "acquisition_date_utc": date,
                "acquisition_datetime_utc": best["acquisition_datetime_utc"],
                "collection_id": best["collection_id"],
                "item_id": best["item_id"],
                "platform": best.get("platform"),
                "cloud_cover_percent": best.get("cloud_cover_percent"),
                "product_id": best.get("product_id"),
                "candidate_scenes_on_date": len(same_date),
                "selection_seed": seed,
                "selection_rule": "uniform random sample of unique available UTC dates; best scene per date by cloud cover, then Sentinel-2 tie-break",
            })

        failed_queries = query_failures_by_year[year]
        annual.append({
            "year": year,
            "target_unique_dates": target,
            "catalogued_unique_dates": len(dates),
            "selected_unique_dates": len(chosen_dates),
            "shortfall_vs_target": max(0, target - len(chosen_dates)),
            "catalogue_query_failures": failed_queries,
            "coverage_status": "catalogue_incomplete" if failed_queries else ("target_met" if len(chosen_dates) == target else "real_data_shortfall"),
            "shortfall_is_confirmed": failed_queries == 0,
            "selection_seed": seed,
        })
    return selected, annual


def download_clip(item_row: dict[str, Any], aoi_geojson: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """Download and AOI-clip standardized bands for one selected acquisition date."""
    item = pystac.Item.from_dict(item_row["item_json"])
    collection_id = item_row["collection_id"]
    date = item_row["acquisition_date_utc"]
    folder = output_root / str(item_row["year"]) / date / collection_id / item.id
    folder.mkdir(parents=True, exist_ok=True)
    geometry = aoi_geojson["features"][0]["geometry"]
    band_meta: dict[str, Any] = {}
    mapping = BAND_ASSETS[collection_id]

    for output_name, asset_key in mapping.items():
        asset = item.assets.get(asset_key)
        if asset is None:
            logging.warning("Scene %s has no asset %s; skipping band %s", item.id, asset_key, output_name)
            continue
        out_path = folder / f"{output_name}.tif"
        if out_path.exists() and out_path.stat().st_size > 0:
            band_meta[output_name] = {
                "asset_key": asset_key, "path": str(out_path), "status": "already_downloaded",
                "size_bytes": out_path.stat().st_size,
            }
            continue
        signed_href = planetary_computer.sign(asset.href)
        with rasterio.open(signed_href) as src:
            aoi_in_crs = transform_geom("EPSG:4326", src.crs, geometry, precision=6)
            clipped, transform = mask(src, [aoi_in_crs], crop=True, all_touched=False)
            profile = src.profile.copy()
            profile.update(
                driver="GTiff", height=clipped.shape[1], width=clipped.shape[2],
                transform=transform, count=clipped.shape[0], compress="deflate",
                tiled=True,
            )
            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(clipped)
            band_meta[output_name] = {
                "asset_key": asset_key,
                "path": str(out_path.relative_to(ROOT)) if out_path.is_relative_to(ROOT) else str(out_path),
                "status": "downloaded",
                "size_bytes": out_path.stat().st_size,
                "width": int(clipped.shape[2]),
                "height": int(clipped.shape[1]),
                "crs": str(src.crs),
                "dtype": str(clipped.dtype),
                "nodata": src.nodata,
            }

    return {
        "year": item_row["year"],
        "acquisition_date_utc": date,
        "collection_id": collection_id,
        "item_id": item.id,
        "platform": item.properties.get("platform"),
        "cloud_cover_percent": item.properties.get("eo:cloud_cover"),
        "output_directory": str(folder),
        "bands": band_meta,
        "downloaded_utc": utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=START_YEAR)
    parser.add_argument("--end-year", type=int, default=END_YEAR)
    parser.add_argument("--target-per-year", type=int, default=DEFAULT_TARGET)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--download", action="store_true", help="Download and clip all selected dates to data_external/ (large; not committed to Git).")
    parser.add_argument("--output-dir", default=os.environ.get("SATELLITE_DATA_DIR", str(ROOT / "data_external" / "thiruvananthapuram_2015_2025")),
                        help="Raster output directory; defaults outside tracked Git data.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    if args.start_year < 1980 or args.end_year > 2025 or args.start_year > args.end_year:
        parser.error("Use an inclusive year range within 1980–2025.")
    if args.target_per_year < 1:
        parser.error("--target-per-year must be at least 1.")

    ensure_dirs()
    aoi_fc, aoi_geometry, bounds = load_aoi()
    logging.info("AOI: %s | bounds=%s", aoi_fc["features"][0].get("properties", {}).get("name"), bounds)
    logging.info("Catalogue and sample dates; target=%d/year seed=%d", args.target_per_year, args.seed)

    try:
        items, query_log = catalogue_items(aoi_geometry, args.start_year, args.end_year)
    except Exception as exc:
        logging.exception("Could not open/query Microsoft Planetary Computer STAC: %s", exc)
        return 2

    selected, annual = sample_dates(items, query_log, args.start_year, args.end_year, args.target_per_year, args.seed)
    scene_rows = []
    for row in items:
        scene_rows.append({key: row.get(key) for key in (
            "year", "acquisition_date_utc", "acquisition_datetime_utc", "collection_id",
            "item_id", "platform", "cloud_cover_percent", "processing_level", "product_id",
        )})
    scene_rows.sort(key=lambda row: (row["acquisition_datetime_utc"] or "", row["collection_id"], row["item_id"]))
    write_csv(CATALOG_DIR / "candidate_scenes.csv", [
        "year", "acquisition_date_utc", "acquisition_datetime_utc", "collection_id",
        "item_id", "platform", "cloud_cover_percent", "processing_level", "product_id",
    ], scene_rows)
    write_csv(CATALOG_DIR / "query_log.csv", [
        "year", "collection_id", "status", "item_count", "updated_utc", "error",
    ], query_log)
    write_csv(CATALOG_DIR / "selected_dates.csv", [
        "year", "acquisition_date_utc", "acquisition_datetime_utc", "collection_id",
        "item_id", "platform", "cloud_cover_percent", "product_id",
        "candidate_scenes_on_date", "selection_seed", "selection_rule",
    ], selected)
    write_csv(METADATA_DIR / "annual_coverage.csv", [
        "year", "target_unique_dates", "catalogued_unique_dates", "selected_unique_dates",
        "shortfall_vs_target", "catalogue_query_failures", "coverage_status",
        "shortfall_is_confirmed", "selection_seed",
    ], annual)

    query_failures = sum(row["status"] != "complete" for row in query_log)
    manifest = {
        "created_utc": utc_now(),
        "provider": "Microsoft Planetary Computer",
        "stac_api": STAC_URL,
        "aoi_file": "config/aoi.geojson",
        "aoi_name": aoi_fc["features"][0].get("properties", {}).get("name"),
        "aoi_bounds_wgs84": bounds,
        "date_range_inclusive": {"start": f"{args.start_year}-01-01", "end": f"{args.end_year}-12-31"},
        "collections": list(COLLECTIONS),
        "target_unique_acquisition_dates_per_year": args.target_per_year,
        "random_seed": args.seed,
        "selection_unit": "distinct acquisition date in UTC, not scene count",
        "selected_date_count": len(selected),
        "catalogued_scene_count": len(items),
        "query_count": len(query_log),
        "failed_query_count": query_failures,
        "annual_coverage": annual,
        "outputs": {
            "candidate_scenes": "catalog/candidate_scenes.csv",
            "selected_dates": "catalog/selected_dates.csv",
            "query_log": "catalog/query_log.csv",
            "annual_coverage": "metadata/annual_coverage.csv",
        },
        "imagery_download_requested": bool(args.download),
        "imagery_output_dir": str(Path(args.output_dir).resolve()) if args.download else None,
        "rules": [
            "Only acquisition dates returned by the live STAC catalogue are eligible.",
            "Sample without replacement from distinct UTC dates, separately for each year.",
            "If a year has fewer eligible dates than the target, select all available dates and report the shortfall.",
            "A year with failed catalogue queries is marked catalogue_incomplete; its shortfall is not confirmed.",
            "One scene is chosen per selected date: lowest reported cloud cover, then Sentinel-2 preference for ties, then stable IDs.",
            "Cloudy scenes are not filtered out; cloud cover is retained as quality metadata.",
            "Raster imagery is stored outside ordinary Git history and must not be committed.",
        ],
    }
    manifest_path = METADATA_DIR / "sampling_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    download_log: list[dict[str, Any]] = []
    if args.download:
        output_root = Path(args.output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        item_lookup = {(row["collection_id"], row["item_id"]): row for row in items}
        for index, selection in enumerate(selected, start=1):
            row = item_lookup.get((selection["collection_id"], selection["item_id"]))
            if row is None:
                logging.error("Selected item not found in local catalogue: %s", selection["item_id"])
                continue
            logging.info("Downloading selected date %d/%d: %s %s", index, len(selected), selection["acquisition_date_utc"], selection["item_id"])
            try:
                download_log.append(download_clip(row, aoi_fc, output_root))
            except Exception as exc:
                logging.exception("Download failed for %s: %s", selection["item_id"], exc)
                download_log.append({
                    "year": selection["year"], "acquisition_date_utc": selection["acquisition_date_utc"],
                    "collection_id": selection["collection_id"], "item_id": selection["item_id"],
                    "status": "failed", "error": f"{type(exc).__name__}: {exc}",
                })
        (METADATA_DIR / "download_log.json").write_text(json.dumps({
            "generated_utc": utc_now(), "output_dir": str(output_root),
            "selected_dates": len(selected), "downloaded_scenes": sum("bands" in row for row in download_log),
            "failed_or_incomplete_scenes": sum("status" in row or len(row.get("bands", {})) < 6 for row in download_log),
            "results": download_log,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "catalogued_scenes": len(items),
        "selected_unique_dates": len(selected),
        "failed_catalogue_queries": query_failures,
        "manifest": str(manifest_path.relative_to(ROOT)),
        "annual_coverage": annual,
        "download_requested": bool(args.download),
        "imagery_output_dir": args.output_dir if args.download else None,
    }, ensure_ascii=False, indent=2))
    return 2 if query_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
