#!/usr/bin/env python3
"""Download real Landsat Collection 2 Level-2 imagery clipped to the configured AOI.

Fetches one low-cloud Landsat 8/9 scene for each requested year through the
public Microsoft Planetary Computer STAC API. The AOI in config/aoi.geojson
is the source of truth; outputs are clipped and tagged with its bounds so a
later study-area change cannot silently reuse imagery from another coastline.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

import planetary_computer
import pystac_client
import rasterio
import requests
from rasterio.mask import mask
from rasterio.warp import transform_geom

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
DATA_ROOT = ROOT / "data" / "satellite"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/"

BANDS = {
    "B2_blue": "blue",
    "B3_green": "green",
    "B4_red": "red",
    "B5_nir": "nir08",
    "B6_swir1": "swir16",
    "B7_swir2": "swir22",
}
PLATFORMS = {
    2015: ("landsat-8",),
    2016: ("landsat-8",),
    2025: ("landsat-9", "landsat-8"),
    2026: ("landsat-9", "landsat-8"),
}


def load_aoi() -> tuple[dict, list[float]]:
    with AOI_PATH.open("r", encoding="utf-8") as handle:
        geojson = json.load(handle)
    geometry = geojson["features"][0]["geometry"]
    coords = geometry["coordinates"][0]
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    bounds = [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]
    return geojson, bounds


def select_scene(year: int, max_cloud: float):
    now = dt.datetime.now(dt.timezone.utc)
    start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    stop = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
    if stop < start:
        raise RuntimeError(f"No imagery can exist for future year {year} yet.")

    _, bbox = load_aoi()
    catalog = pystac_client.Client.open(
        STAC_URL,
        modifier=planetary_computer.sign_inplace,
    )
    search = catalog.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=f"{start.isoformat()}/{stop.isoformat()}",
        limit=100,
    )
    items = list(search.items())
    candidates = [
        item for item in items
        if item.properties.get("platform") in PLATFORMS[year]
        and item.datetime is not None
        and item.datetime.year == year
        and float(item.properties.get("eo:cloud_cover", 100.0)) < max_cloud
    ]
    if not candidates:
        raise RuntimeError(
            f"No Landsat 8/9 Collection 2 Level-2 scene was found for the configured "
            f"Thiruvananthapuram AOI in {year} with cloud cover < {max_cloud}%. "
            "Try increasing --max-cloud."
        )

    # Prefer the clearest image; for similar clarity, choose the newest.
    candidates.sort(
        key=lambda item: (
            float(item.properties.get("eo:cloud_cover", 100.0)),
            -(item.datetime.timestamp() if item.datetime else 0),
        )
    )
    return candidates[0]


def download_year(year: int, max_cloud: float) -> dict:
    geojson, bounds = load_aoi()
    item = select_scene(year, max_cloud)
    out_dir = DATA_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "year": year,
        "scene_id": item.id,
        "platform": item.properties.get("platform"),
        "acquisition_datetime": item.datetime.isoformat() if item.datetime else None,
        "cloud_cover_percent": item.properties.get("eo:cloud_cover"),
        "collection": "landsat-c2-l2",
        "source": "Microsoft Planetary Computer",
        "aoi_file": str(AOI_PATH.relative_to(ROOT)),
        "aoi_name": geojson["features"][0].get("properties", {}).get("name"),
        "aoi_bounds": bounds,
        "bands": {},
    }

    preview = item.assets.get("rendered_preview") or item.assets.get("thumbnail")
    if preview:
        response = requests.get(planetary_computer.sign(preview.href), timeout=60)
        response.raise_for_status()
        (out_dir / "scene_preview.jpg").write_bytes(response.content)
        metadata["preview"] = "scene_preview.jpg"

    geometry = geojson["features"][0]["geometry"]
    for name, asset_key in BANDS.items():
        asset = item.assets.get(asset_key)
        if asset is None:
            raise RuntimeError(f"Scene {item.id} is missing asset '{asset_key}'.")

        out_path = out_dir / f"{name}.tif"
        with rasterio.open(planetary_computer.sign(asset.href)) as src:
            aoi_in_raster_crs = transform_geom("EPSG:4326", src.crs, geometry, precision=6)
            clipped, transform = mask(src, [aoi_in_raster_crs], crop=True)
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

    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, action="append", choices=sorted(PLATFORMS),
                        help="Year to download; repeat to fetch both. Default: 2016 and 2026.")
    parser.add_argument("--max-cloud", type=float, default=35.0,
                        help="Maximum scene cloud cover percentage (default: 35).")
    args = parser.parse_args()

    years = args.year or [2016, 2026]
    for year in years:
        metadata = download_year(year, args.max_cloud)
        print(
            f"{year}: {metadata['scene_id']} | {metadata['acquisition_datetime']} | "
            f"cloud={metadata['cloud_cover_percent']}% | AOI={metadata['aoi_name']}"
        )


if __name__ == "__main__":
    main()
