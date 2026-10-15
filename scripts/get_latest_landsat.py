"""Print the clearest recent Landsat scene covering the configured project AOI."""
import json
from pathlib import Path

import planetary_computer
from pystac_client import Client

ROOT = Path(__file__).resolve().parents[1]
AOI_PATH = ROOT / "config" / "aoi.geojson"
CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"


with AOI_PATH.open("r", encoding="utf-8") as handle:
    geojson = json.load(handle)
ring = geojson["features"][0]["geometry"]["coordinates"][0]
xs = [p[0] for p in ring]
ys = [p[1] for p in ring]
BBOX = [min(xs), min(ys), max(xs), max(ys)]

catalog = Client.open(CATALOG_URL)
search = catalog.search(
    collections=[COLLECTION],
    bbox=BBOX,
    query={"eo:cloud_cover": {"lte": 20}},
    sortby=[{"field": "datetime", "direction": "desc"}],
    max_items=20,
)
items = sorted(search.item_collection(), key=lambda item: item.datetime, reverse=True)
if not items:
    raise RuntimeError("No Landsat scene found with cloud cover <= 20% for the current AOI.")

item = planetary_computer.sign(items[0])
print("AOI:", geojson["features"][0].get("properties", {}).get("name"))
print("Scene:", item.id)
print("Date:", item.datetime)
print("Cloud:", item.properties.get("eo:cloud_cover"))
for name in ["blue", "green", "red", "nir08", "swir16", "swir22"]:
    asset = item.assets.get(name)
    if asset:
        print(f"{name}: {asset.href}")
