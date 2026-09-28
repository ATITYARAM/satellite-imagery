from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request

import planetary_computer
from pystac_client import Client

CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
BBOX = [80.1, 12.6, 80.3, 13.1]

OUT_DIR = Path("data/satellite/raw")
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
    raise RuntimeError("No suitable Landsat scene found.")

item = planetary_computer.sign(item)

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
    futures = [
        executor.submit(download_band, name, asset_name)
        for name, asset_name in bands.items()
    ]
    for future in futures:
        future.result()

print("DONE")