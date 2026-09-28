#!/usr/bin/env python3
"""Download the same Chennai–Mahabalipuram Landsat AOI for 2016 and 2026.

Uses the public Microsoft Planetary Computer STAC API; no EarthExplorer login.
The selected scene is the clearest available scene for the requested year and
satellite. Only the configured AOI is read from the cloud-optimized GeoTIFFs;
pixel values are preserved (no indices, classification, or ML).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import planetary_computer
import pystac_client
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping, shape


ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
DATA_ROOT = ROOT / "data" / "satellite"

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
    2026: ("landsat-9", "2026-01-01T00:00:00Z/2026-12-31T23:59:59Z"),
}


def load_aoi() -> dict:
    with AOI_PATH.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    geometry = shape(geojson["features"][0]["geometry"])
    return mapping(geometry)


def select_scene(year: int, max_cloud: float):
    platform, date_range = YEAR_CONFIG[year]

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1/",
        modifier=planetary_computer.sign_inplace,
    )

    search = catalog.search(
        collections=["landsat-c2-l2"],
        intersects=load_aoi(),
        datetime=date_range,
        query={
            "platform": {"eq": platform},
            "eo:cloud_cover": {"lt": max_cloud},
        },
        max_items=100,
    )

    items = list(search.items())
    if not items:
        raise RuntimeError(
            f"No {platform} Landsat Collection 2 Level-2 scene found for {year} "
            f"with cloud cover < {max_cloud}% over the configured AOI."
        )

    # Prefer low cloud cover, then the most recent acquisition.
    items.sort(
        key=lambda item: (
            float(item.properties.get("eo:cloud_cover", 100.0)),
            -(item.datetime.timestamp() if item.datetime else 0),
        )
    )
    return items[0]


def download_year(year: int, max_cloud: float) -> dict:
    aoi = load_aoi()
    item = select_scene(year, max_cloud)
    out_dir = DATA_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "year": year,
        "scene_id": item.id,
        "platform": item.properties.get("platform"),
        "acquisition_datetime": item.datetime.astimezone(timezone.utc).isoformat()
        if item.datetime
        else None,
        "cloud_cover_percent": item.properties.get("eo:cloud_cover"),
        "collection": "landsat-c2-l2",
        "source": "Microsoft Planetary Computer",
        "aoi_file": str(AOI_PATH.relative_to(ROOT)),
        "bands": {},
    }

    # Save the scene preview for quick inspection when available.
    preview = item.assets.get("rendered_preview") or item.assets.get("thumbnail")
    if preview:
        preview_path = out_dir / "scene_preview.jpg"
        signed = planetary_computer.sign(preview.href)
        import requests

        response = requests.get(signed, timeout=60)
        response.raise_for_status()
        preview_path.write_bytes(response.content)
        metadata["preview"] = preview_path.name

    for name, asset_key in BANDS.items():
        asset = item.assets.get(asset_key)
        if asset is None:
            raise RuntimeError(f"Scene {item.id} is missing asset '{asset_key}'.")

        href = planetary_computer.sign(asset.href)
        out_path = out_dir / f"{name}.tif"

        with rasterio.open(href) as src:
            clipped, transform = mask(src, [aoi], crop=True)
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
        json.dumps(metadata, indent=2), encoding="utf-8"
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

    years = args.year or [2016, 2026]
    for year in years:
        metadata = download_year(year, args.max_cloud)
        print(
            f"{year}: {metadata['scene_id']} | "
            f"{metadata['acquisition_datetime']} | "
            f"cloud={metadata['cloud_cover_percent']}%"
        )


if __name__ == "__main__":
    main()
