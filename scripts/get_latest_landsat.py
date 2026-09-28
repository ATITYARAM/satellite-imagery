from pystac_client import Client
import planetary_computer

CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"

BBOX = [80.1, 12.6, 80.3, 13.1]

catalog = Client.open(CATALOG_URL)

search = catalog.search(
    collections=[COLLECTION],
    bbox=BBOX,
    query={"eo:cloud_cover": {"lte": 20}},
    max_items=20,
)

items = sorted(
    search.item_collection(),
    key=lambda item: item.datetime,
    reverse=True,
)

if not items:
    raise RuntimeError("No Landsat scene found with cloud cover <= 20%")

item = planetary_computer.sign(items[0])

print("Scene:", item.id)
print("Date:", item.datetime)
print("Cloud:", item.properties.get("eo:cloud_cover"))

for name in ["blue", "green", "red", "nir08", "swir16", "swir22"]:
    asset = item.assets.get(name)
    if asset:
        print(f"{name}: {asset.href}")