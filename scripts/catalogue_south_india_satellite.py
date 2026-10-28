#!/usr/bin/env python3
"""Discover the full Microsoft Planetary Computer satellite catalogue for southern India.

This is a catalogue-first workflow: it does not download raster imagery.
It records real STAC items for Landsat Collection 2 Level-2 and Sentinel-2
Level-2A for 2010-01-01 through 2025-12-31, using state/UT boundaries in the
official Southern Zonal Council scope used by this project.

The GeoBoundaries gbOpen administrative boundary is fetched on first run and
the selected geometries plus source metadata are saved under the archive.
Every query is checkpointed in SQLite, so an interrupted run can be resumed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import json
import logging
import re
import sqlite3
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import requests
from pystac_client import Client
from shapely.geometry import shape, mapping

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "satellite" / "south_india_2010_2025"
AOI_DIR = ARCHIVE / "aoi"
CATALOG_DIR = ARCHIVE / "catalog"
METADATA_DIR = ARCHIVE / "metadata"
WORK_DIR = ARCHIVE / ".work"

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"
GEOB_BOUNDARY_METADATA_URL = "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/"
COLLECTIONS = ("landsat-c2-l2", "sentinel-2-l2a")
START_YEAR_DEFAULT = 2010
END_YEAR_DEFAULT = 2025

# Southern Zonal Council geographic scope used for this project.
# Full administrative geometries are used, not only a coastal buffer.
REGION_MEMBERS = {
    "Andhra Pradesh": {"andhra pradesh"},
    "Karnataka": {"karnataka"},
    "Kerala": {"kerala", "keralam"},
    "Tamil Nadu": {"tamil nadu"},
    "Telangana": {"telangana"},
    "Puducherry": {"puducherry", "pondicherry"},
    "Andaman and Nicobar Islands": {
        "andaman and nicobar islands", "andaman & nicobar islands",
        "andaman and nicobar", "andaman & nicobar",
    },
    "Lakshadweep": {"lakshadweep"},
}


def normalized_name(value: Any) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def get_json(session: requests.Session, url: str, *, attempts: int = 5) -> Any:
    last_error = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=(15, 90))
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 20))
    raise RuntimeError(f"Could not fetch JSON from {url}: {last_error}")


def ensure_dirs() -> None:
    for path in (
        AOI_DIR, CATALOG_DIR, METADATA_DIR, WORK_DIR,
        ARCHIVE / "imagery" / "landsat",
        ARCHIVE / "imagery" / "sentinel2",
    ):
        path.mkdir(parents=True, exist_ok=True)


def load_or_fetch_aoi(session: requests.Session, *, refresh: bool = False):
    """Save a stable AOI copy and provenance; return named Shapely geometries."""
    aoi_path = AOI_DIR / "southern_zonal_council_members.geojson"
    provenance_path = METADATA_DIR / "aoi_source.json"

    if aoi_path.exists() and provenance_path.exists() and not refresh:
        aoi_fc = json.loads(aoi_path.read_text(encoding="utf-8"))
        selected = {}
        for feature in aoi_fc.get("features", []):
            label = feature.get("properties", {}).get("project_region_name")
            if label:
                selected[label] = shape(feature["geometry"])
        missing = sorted(set(REGION_MEMBERS) - set(selected))
        if not missing:
            return selected
        logging.warning("Saved AOI misses members %s; refreshing source boundaries.", missing)

    boundary_metadata = get_json(session, GEOB_BOUNDARY_METADATA_URL)
    geojson_url = boundary_metadata.get("gjDownloadURL") or boundary_metadata.get("simplifiedGeometryGeoJSON")
    if not geojson_url:
        raise RuntimeError(
            "GeoBoundaries response did not include a GeoJSON download URL. "
            f"Response keys were: {sorted(boundary_metadata.keys())}"
        )
    boundary_fc = get_json(session, geojson_url)
    features = boundary_fc.get("features", [])
    selected_features: dict[str, dict[str, Any]] = {}
    available_names = set()

    aliases_to_canonical = {
        normalized_name(alias): canonical
        for canonical, aliases in REGION_MEMBERS.items()
        for alias in aliases
    }
    for feature in features:
        props = feature.get("properties", {})
        candidate_names = [
            props.get("shapeName"),
            props.get("shapeName_en"),
            props.get("shapeNameAlt"),
            props.get("NAME_1"),
            props.get("name"),
            props.get("name_en"),
        ]
        canonical = None
        for candidate in candidate_names:
            norm = normalized_name(candidate)
            if not norm:
                continue
            available_names.add(str(candidate))
            canonical = aliases_to_canonical.get(norm)
            if canonical:
                break
        if canonical and canonical not in selected_features:
            geom = shape(feature["geometry"])
            if not geom.is_valid:
                geom = geom.buffer(0)
            if geom.is_empty:
                raise RuntimeError(f"Empty geometry for administrative unit {canonical}")
            selected_features[canonical] = {
                "type": "Feature",
                "properties": {
                    **props,
                    "project_region_name": canonical,
                    "boundary_source": "geoBoundaries gbOpen India ADM1",
                },
                "geometry": mapping(geom),
            }

    missing = sorted(set(REGION_MEMBERS) - set(selected_features))
    if missing:
        raise RuntimeError(
            "Could not match all intended Southern Zonal Council members in the "
            f"GeoBoundaries ADM1 file. Missing: {missing}. Names seen: {sorted(available_names)}"
        )

    out_fc = {
        "type": "FeatureCollection",
        "name": "Southern Zonal Council members - regional satellite archive AOI",
        "features": [selected_features[name] for name in REGION_MEMBERS],
    }
    aoi_path.write_text(json.dumps(out_fc, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "boundary_provider": "geoBoundaries",
        "boundary_endpoint": GEOB_BOUNDARY_METADATA_URL,
        "release_type": "gbOpen",
        "country_iso3": "IND",
        "boundary_level": "ADM1",
        "boundary_id": boundary_metadata.get("boundaryID"),
        "boundary_name": boundary_metadata.get("boundaryName"),
        "boundary_year_represented": boundary_metadata.get("boundaryYearRepresented"),
        "boundary_source": boundary_metadata.get("boundarySource"),
        "boundary_license": boundary_metadata.get("boundaryLicense"),
        "license_detail": boundary_metadata.get("licenseDetail"),
        "metadata_retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "download_url": geojson_url,
        "saved_aoi": str(aoi_path.relative_to(ROOT)),
        "members": list(REGION_MEMBERS),
        "note": (
            "The selected regions are full ADM1 geometries. They are not a coastal-only "
            "buffer. The boundary metadata and GeoJSON are saved to preserve provenance."
        ),
    }
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return {name: shape(selected_features[name]["geometry"]) for name in REGION_MEMBERS}


def init_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS items (
            collection_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_datetime TEXT,
            platform TEXT,
            cloud_cover REAL,
            matched_states_json TEXT NOT NULL,
            item_json TEXT NOT NULL,
            PRIMARY KEY (collection_id, item_id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            query_key TEXT PRIMARY KEY,
            state_name TEXT NOT NULL,
            year INTEGER NOT NULL,
            collection_id TEXT NOT NULL,
            status TEXT NOT NULL,
            item_count INTEGER NOT NULL DEFAULT 0,
            updated_utc TEXT NOT NULL,
            error TEXT
        )
    """)
    db.commit()
    return db


def record_item(db: sqlite3.Connection, collection_id: str, state_name: str, item: Any) -> None:
    item_json = item.to_dict()
    props = item_json.get("properties", {})
    item_id = str(item_json.get("id", ""))
    if not item_id:
        return
    item_dt = props.get("datetime") or props.get("start_datetime")
    cloud = props.get("eo:cloud_cover")
    platform = props.get("platform")
    existing = db.execute(
        "SELECT matched_states_json FROM items WHERE collection_id=? AND item_id=?",
        (collection_id, item_id),
    ).fetchone()
    states = set(json.loads(existing[0])) if existing else set()
    states.add(state_name)
    db.execute("""
        INSERT INTO items (
            collection_id, item_id, item_datetime, platform, cloud_cover,
            matched_states_json, item_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(collection_id, item_id) DO UPDATE SET
            item_datetime=excluded.item_datetime,
            platform=excluded.platform,
            cloud_cover=excluded.cloud_cover,
            matched_states_json=excluded.matched_states_json,
            item_json=excluded.item_json
    """, (
        collection_id, item_id, item_dt, platform,
        float(cloud) if cloud is not None else None,
        json.dumps(sorted(states), ensure_ascii=False),
        json.dumps(item_json, ensure_ascii=False, separators=(",", ":")),
    ))


def do_catalogue(
    db: sqlite3.Connection,
    regions: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    refresh: bool = False,
) -> None:
    catalog = Client.open(STAC_URL)
    query_total = len(regions) * (end_year - start_year + 1) * len(COLLECTIONS)
    completed = 0

    for state_name, geom in regions.items():
        for year in range(start_year, end_year + 1):
            start = f"{year}-01-01T00:00:00Z"
            end = f"{year}-12-31T23:59:59Z"
            for collection_id in COLLECTIONS:
                query_key = f"{state_name}|{year}|{collection_id}"
                previous = db.execute(
                    "SELECT status, item_count FROM queries WHERE query_key=?",
                    (query_key,),
                ).fetchone()
                if previous and previous[0] == "complete" and not refresh:
                    completed += 1
                    logging.info("[%d/%d] Already complete: %s (%s items)", completed, query_total, query_key, previous[1])
                    continue

                logging.info("[%d/%d] Querying %s", completed + 1, query_total, query_key)
                item_count = 0
                try:
                    search = catalog.search(
                        collections=[collection_id],
                        intersects=mapping(geom),
                        datetime=f"{start}/{end}",
                        max_items=None,
                    )
                    for item in search.items():
                        record_item(db, collection_id, state_name, item)
                        item_count += 1
                        if item_count % 100 == 0:
                            db.commit()
                    db.execute("""
                        INSERT INTO queries (query_key, state_name, year, collection_id,
                            status, item_count, updated_utc, error)
                        VALUES (?, ?, ?, ?, 'complete', ?, ?, NULL)
                        ON CONFLICT(query_key) DO UPDATE SET
                            status='complete', item_count=excluded.item_count,
                            updated_utc=excluded.updated_utc, error=NULL
                    """, (
                        query_key, state_name, year, collection_id, item_count,
                        dt.datetime.now(dt.timezone.utc).isoformat(),
                    ))
                    db.commit()
                    logging.info("Finished %s: %d matching scene records", query_key, item_count)
                except Exception as exc:
                    db.rollback()
                    message = f"{type(exc).__name__}: {exc}"
                    db.execute("""
                        INSERT INTO queries (query_key, state_name, year, collection_id,
                            status, item_count, updated_utc, error)
                        VALUES (?, ?, ?, ?, 'failed', ?, ?, ?)
                        ON CONFLICT(query_key) DO UPDATE SET
                            status='failed', item_count=excluded.item_count,
                            updated_utc=excluded.updated_utc, error=excluded.error
                    """, (
                        query_key, state_name, year, collection_id, item_count,
                        dt.datetime.now(dt.timezone.utc).isoformat(), message[:2000],
                    ))
                    db.commit()
                    logging.exception("Failed query %s", query_key)
                completed += 1


def export_catalogue(db: sqlite3.Connection, *, start_year: int, end_year: int) -> dict[str, Any]:
    csv_path = CATALOG_DIR / "scene_catalog.csv"
    gzip_path = CATALOG_DIR / "stac_items.jsonl.gz"
    query_log_path = CATALOG_DIR / "query_log.csv"
    run_path = METADATA_DIR / "catalogue_run.json"

    fieldnames = [
        "collection_id", "item_id", "acquisition_datetime_utc", "acquisition_date_utc",
        "platform", "instruments", "sensor", "eo_cloud_cover_percent",
        "processing_level", "product_id", "landsat_wrs_path", "landsat_wrs_row",
        "sentinel_mgrs_tile", "proj_epsg", "bbox_json", "intersecting_region_members",
        "item_self_url", "asset_urls_json", "asset_details_json",
    ]
    item_rows = db.execute("""
        SELECT collection_id, item_id, item_datetime, platform, cloud_cover,
               matched_states_json, item_json
        FROM items ORDER BY item_datetime, collection_id, item_id
    """).fetchall()

    summary_by_year: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "scene_products": 0, "unique_acquisition_dates": set(), "by_collection": Counter()
    })
    collection_counts = Counter()
    state_counts = Counter()
    with csv_path.open("w", newline="", encoding="utf-8") as handle, gzip.open(gzip_path, "wt", encoding="utf-8") as gz:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for collection_id, item_id, item_dt, platform, cloud, states_json, item_json_text in item_rows:
            item = json.loads(item_json_text)
            props = item.get("properties", {})
            assets = item.get("assets", {})
            date_utc = str(item_dt or "")[:10]
            if len(date_utc) >= 4 and date_utc[:4].isdigit():
                year = date_utc[:4]
                summary_by_year[year]["scene_products"] += 1
                summary_by_year[year]["by_collection"][collection_id] += 1
                summary_by_year[year]["unique_acquisition_dates"].add(date_utc)
            collection_counts[collection_id] += 1
            states = json.loads(states_json)
            for state in states:
                state_counts[state] += 1
            asset_urls = {}
            asset_details = {}
            for key, asset in assets.items():
                asset_urls[key] = asset.get("href")
                asset_details[key] = {
                    "href": asset.get("href"),
                    "type": asset.get("type"),
                    "roles": asset.get("roles"),
                    "title": asset.get("title"),
                    "file:size": asset.get("file:size"),
                    "raster:bands": asset.get("raster:bands"),
                    "eo:bands": asset.get("eo:bands"),
                }
            self_url = next((link.get("href") for link in item.get("links", []) if link.get("rel") == "self"), None)
            row = {
                "collection_id": collection_id,
                "item_id": item_id,
                "acquisition_datetime_utc": item_dt,
                "acquisition_date_utc": date_utc,
                "platform": platform,
                "instruments": json.dumps(props.get("instruments"), ensure_ascii=False),
                "sensor": props.get("instruments", [None])[0] if props.get("instruments") else platform,
                "eo_cloud_cover_percent": cloud,
                "processing_level": props.get("landsat:processing_level") or props.get("processing:level"),
                "product_id": props.get("landsat:product_id") or props.get("s2:product_uri") or props.get("s2:product_id"),
                "landsat_wrs_path": props.get("landsat:wrs_path"),
                "landsat_wrs_row": props.get("landsat:wrs_row"),
                "sentinel_mgrs_tile": props.get("s2:mgrs_tile"),
                "proj_epsg": props.get("proj:epsg"),
                "bbox_json": json.dumps(item.get("bbox"), ensure_ascii=False),
                "intersecting_region_members": json.dumps(states, ensure_ascii=False),
                "item_self_url": self_url,
                "asset_urls_json": json.dumps(asset_urls, ensure_ascii=False, separators=(",", ":")),
                "asset_details_json": json.dumps(asset_details, ensure_ascii=False, separators=(",", ":")),
            }
            writer.writerow(row)
            gz.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")

    with query_log_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["query_key", "state_name", "year", "collection_id", "status", "item_count", "updated_utc", "error"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in db.execute("""
            SELECT query_key, state_name, year, collection_id, status, item_count, updated_utc, error
            FROM queries ORDER BY year, state_name, collection_id
        """):
            writer.writerow(dict(zip(fields, row)))

    query_counts = Counter()
    for row in db.execute("SELECT status, COUNT(*) FROM queries GROUP BY status"):
        query_counts[row[0]] = row[1]
    summary = {
        "catalogue_status": "partial" if query_counts.get("failed", 0) else "complete",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "provider": "Microsoft Planetary Computer",
        "stac_api": STAC_URL,
        "collections": list(COLLECTIONS),
        "date_range_inclusive": {
            "start": f"{start_year}-01-01T00:00:00Z",
            "end": f"{end_year}-12-31T23:59:59Z",
        },
        "region_members": list(REGION_MEMBERS),
        "scene_product_count": len(item_rows),
        "scene_products_by_collection": dict(collection_counts),
        "scene_products_by_region_member_intersect": dict(state_counts),
        "queries_by_status": dict(query_counts),
        "yearly_coverage": {
            year: {
                "scene_products": values["scene_products"],
                "unique_acquisition_dates": len(values["unique_acquisition_dates"]),
                "scene_products_by_collection": dict(values["by_collection"]),
            }
            for year, values in sorted(summary_by_year.items())
        },
        "outputs": {
            "scene_catalog_csv": str(csv_path.relative_to(ROOT)),
            "full_stac_items_jsonl_gzip": str(gzip_path.relative_to(ROOT)),
            "query_log_csv": str(query_log_path.relative_to(ROOT)),
        },
        "scientific_notes": [
            "Catalogue includes all returned matching scene products, including cloudy scenes.",
            "The inventory is not a count of clear or scientifically usable dates.",
            "The 50-date/year sampling target is not applied during discovery.",
            "Different sensors and overlapping scenes are retained as separate products.",
            "No raster imagery has been downloaded by this catalogue script.",
        ],
    }
    run_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=START_YEAR_DEFAULT)
    parser.add_argument("--end-year", type=int, default=END_YEAR_DEFAULT)
    parser.add_argument("--refresh-aoi", action="store_true", help="Refresh the saved administrative boundary geometry.")
    parser.add_argument("--refresh-queries", action="store_true", help="Repeat completed queries as well as failed/incomplete queries.")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(message)s")

    if args.start_year < 1980 or args.end_year > 2025 or args.start_year > args.end_year:
        parser.error("Use a valid inclusive range within 1980–2025 (project default: 2010–2025).")

    ensure_dirs()
    session = requests.Session()
    session.headers.update({"User-Agent": "coastal-erosion-satellite-catalogue/1.0"})
    try:
        regions = load_or_fetch_aoi(session, refresh=args.refresh_aoi)
    except Exception as exc:
        logging.error("AOI preparation failed: %s", exc)
        return 2

    db = init_db(WORK_DIR / "catalogue.sqlite")
    try:
        do_catalogue(
            db, regions,
            start_year=args.start_year,
            end_year=args.end_year,
            refresh=args.refresh_queries,
        )
        summary = export_catalogue(db, start_year=args.start_year, end_year=args.end_year)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        failed = db.execute("SELECT COUNT(*) FROM queries WHERE status='failed'").fetchone()[0]
        return 2 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
