import requests
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
payload = {
    "collections": ["landsat-c2-l2"],
    "bbox": [80.1, 12.6, 80.3, 13.3],
    "limit": 1
}
resp = requests.post(STAC_URL, json=payload).json()
if "features" in resp and len(resp["features"]) > 0:
    assets = resp["features"][0]["assets"]
    print("Assets:", list(assets.keys()))
else:
    print("No features")
