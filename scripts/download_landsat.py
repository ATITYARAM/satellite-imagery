"""Download the latest low-cloud Landsat bands for the configured AOI.

For the app's paired 2016/2026 analysis, use download_landsat_aoi.py instead.
This helper stores the latest full-scene bands under data/satellite/raw.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.request

import planetary_computer
from pystac_client import Client

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"

with AOI_PATH.open("r", encoding="utf-8") as handle:
    geojson = json.load(handle)
ring = geojson["features"][0]["geometry"]["coordinates"][0]
xs = [point[0] for point in ring]
ys = [point[1] for point in ring]
BBOX = [min(xs), min(ys), max(xs), max(ys)]

OUT_DIR = ROOT / "data" / "satellite" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)

catalog = Client.open(CATALOG_URL)
search = catalog.search(
    collections=[COLLECTION],
    bbox=BBOX,
    query={"eo:cloud_cover": {"lte": 20}},
    sortby=[{"field": "datetime", "direction": "desc"}],
    max_items=1,
)
item = next(search.items(), None)
if item is None:
    raise RuntimeError("No suitable Landsat scene found for the current AOI.")

item = planetary_computer.sign(item)
print("AOI:", geojson["features"][0].get("properties", {}).get("name"))
print("Scene:", item.id)
print("Date:", item.datetime)
print("Cloud:", item.properties.get("eo:cloud_cover"))

bands = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir08": "nir08",
    "swir16": "swir16",
    "swir22": "swir22",
}


def download_band(name, asset_name):
    asset = item.assets[asset_name]
    output = OUT_DIR / f"{name}.tif"
    print(f"Downloading {name}...")
    urllib.request.urlretrieve(asset.href, output)
    print(f"Saved: {output}")


with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(download_band, name, asset_name) for name, asset_name in bands.items()]
    for future in futures:
        future.result()

print("DONE")
