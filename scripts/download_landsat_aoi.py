#!/usr/bin/env python3
"""Download comparable Landsat AOI data for 2016 and 2026.

Uses the public Microsoft Planetary Computer STAC API without EarthExplorer.
The STAC collection-items endpoint is used directly to avoid the slow QUERY
extension path. Pixel values are preserved; no indices, classification, or ML
are applied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import planetary_computer
import pystac
import rasterio
import requests
from rasterio.mask import mask
from rasterio.warp import transform_geom


ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
DATA_ROOT = ROOT / "data" / "satellite"
STAC_ITEMS_URL = (
    "https://planetarycomputer.microsoft.com/api/stac/v1/"
    "collections/landsat-c2-l2/items"
)

BANDS = {
    "B2_blue": "blue",
    "B3_green": "green",
    "B4_red": "red",
    "B5_nir": "nir08",
    "B6_swir1": "swir16",
    "B7_swir2": "swir22",
}

YEAR_CONFIG = {
    2016: ("landsat-8", "2016-01-01T00:00:00Z/2016-12-31T23:59:59Z"),
    2026: ("landsat-9", "2026-01-01T00:00:00Z/2026-09-28T23:59:59Z"),
}


def load_aoi_geometry() -> dict:
    with AOI_PATH.open("r", encoding="utf-8") as f:
        geojson = json.load(f)
    return geojson["features"][0]["geometry"]


def load_aoi_bbox() -> list[float]:
    geometry = load_aoi_geometry()
    coords = geometry["coordinates"][0]
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    return [min(xs), min(ys), max(xs), max(ys)]


def select_scene(year: int, max_cloud: float) -> pystac.Item:
    platform, date_range = YEAR_CONFIG[year]

    params = {
        "bbox": ",".join(str(v) for v in load_aoi_bbox()),
        "datetime": date_range,
        "limit": 100,
    }

    response = requests.get(
        STAC_ITEMS_URL,
        params=params,
        timeout=(15, 60),
    )
    response.raise_for_status()
    payload = response.json()

    items = [
        pystac.Item.from_dict(feature)
        for feature in payload.get("features", [])
    ]

    candidates = [
        item
        for item in items
        if item.properties.get("platform") == platform
        and float(item.properties.get("eo:cloud_cover", 100.0)) < max_cloud
    ]

    if not candidates:
        raise RuntimeError(
            f"No {platform} Landsat Collection 2 Level-2 scene found for {year} "
            f"with cloud cover < {max_cloud}% over the configured AOI."
        )

    candidates.sort(
        key=lambda item: (
            float(item.properties.get("eo:cloud_cover", 100.0)),
            -(item.datetime.timestamp() if item.datetime else 0),
        )
    )
    return candidates[0]


def download_year(year: int, max_cloud: float) -> dict:
    item = select_scene(year, max_cloud)
    out_dir = DATA_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "year": year,
        "scene_id": item.id,
        "platform": item.properties.get("platform"),
        "acquisition_datetime": item.datetime.isoformat()
        if item.datetime
        else None,
        "cloud_cover_percent": item.properties.get("eo:cloud_cover"),
        "collection": "landsat-c2-l2",
        "source": "Microsoft Planetary Computer",
        "aoi_file": str(AOI_PATH.relative_to(ROOT)),
        "bands": {},
    }

    preview = item.assets.get("rendered_preview") or item.assets.get("thumbnail")
    if preview:
        response = requests.get(
            planetary_computer.sign(preview.href),
            timeout=60,
        )
        response.raise_for_status()
        (out_dir / "scene_preview.jpg").write_bytes(response.content)
        metadata["preview"] = "scene_preview.jpg"

    aoi_geometry = load_aoi_geometry()

    for name, asset_key in BANDS.items():
        asset = item.assets.get(asset_key)
        if asset is None:
            raise RuntimeError(f"Scene {item.id} is missing asset '{asset_key}'.")

        out_path = out_dir / f"{name}.tif"

        with rasterio.open(planetary_computer.sign(asset.href)) as src:
            aoi_in_raster_crs = transform_geom(
                "EPSG:4326",
                src.crs,
                aoi_geometry,
                precision=6,
            )

            clipped, transform = mask(
                src,
                [aoi_in_raster_crs],
                crop=True,
            )

            profile = src.profile.copy()
            profile.update(
                driver="GTiff",
                height=clipped.shape[1],
                width=clipped.shape[2],
                transform=transform,
                count=1,
            )

            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(clipped[0], 1)

            metadata["bands"][name] = {
                "asset": asset_key,
                "path": str(out_path.relative_to(ROOT)),
                "dtype": str(clipped.dtype),
                "width": int(clipped.shape[2]),
                "height": int(clipped.shape[1]),
                "crs": str(src.crs),
                "resolution_m": float(abs(src.transform.a)),
                "nodata": src.nodata,
            }

    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--year",
        type=int,
        action="append",
        choices=sorted(YEAR_CONFIG),
        help="Year to download; repeat for multiple years. Default: 2016 and 2026.",
    )
    parser.add_argument(
        "--max-cloud",
        type=float,
        default=35.0,
        help="Maximum scene cloud cover percentage (default: 35).",
    )
    args = parser.parse_args()

    for year in args.year or [2016, 2026]:
        metadata = download_year(year, args.max_cloud)
        print(
            f"{year}: {metadata['scene_id']} | "
            f"{metadata['acquisition_datetime']} | "
            f"cloud={metadata['cloud_cover_percent']}%"
        )


if __name__ == "__main__":
    main()
