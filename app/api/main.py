from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = ROOT / 'dist'
DOCS_DIR = ROOT / 'docs'
AOI_PATH = ROOT / 'config' / 'aoi.geojson'
DATA_ROOT = ROOT / 'data' / 'satellite'

app = FastAPI(title='Coastal Erosion Prediction Platform API', version='0.1.0')

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/project/info')
def project_info():
    return {
        'project': 'Coastal Erosion Prediction Platform',
        'study_area': 'Chennai-Mahabalipuram Coastal Belt',
        'domains': ['Satellite Imagery', 'Shoreline History', 'Terrain', 'Rainfall / Weather', 'Ocean Conditions'],
        'stage': 'clean baseline',
    }

@app.get('/domains')
def domains():
    return ['satellite', 'history', 'terrain', 'weather', 'ocean', 'prediction']

@app.get('/satellite/data')
def satellite_data():
    result = {'source': 'Microsoft Planetary Computer', 'years': {}}
    for year in (2016, 2026):
        year_dir = DATA_ROOT / str(year)
        metadata_path = year_dir / 'metadata.json'
        if not metadata_path.exists():
            result['years'][str(year)] = {'available': False}
            continue
        with metadata_path.open('r', encoding='utf-8') as handle:
            metadata = json.load(handle)
        metadata['available'] = True
        metadata['preview_url'] = f'/satellite/rgb/{year}.png'
        metadata['download_urls'] = {
            name: f'/satellite-data/{year}/{Path(info["path"]).name}'
            for name, info in metadata.get('bands', {}).items()
        }
        metadata['metadata_url'] = f'/satellite-data/{year}/metadata.json'
        result['years'][str(year)] = metadata
    return result

@app.get('/satellite/rgb/{year}.png')
def satellite_rgb(year: int):
    if year not in (2016, 2026):
        raise HTTPException(status_code=404, detail='Satellite year not found')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio

    year_dir = DATA_ROOT / str(year)
    red_path = year_dir / 'B4_red.tif'
    green_path = year_dir / 'B3_green.tif'
    blue_path = year_dir / 'B2_blue.tif'

    if not all(path.exists() for path in (red_path, green_path, blue_path)):
        raise HTTPException(status_code=404, detail='RGB band data not found')

    # Render the original downloaded Landsat C2 L2 bands B4/B3/B2 directly.
    # This is only the physical Level-2 reflectance conversion required to
    # display the satellite measurements as visible RGB; there is no
    # percentile stretching, sharpening, classification, index, or ML.
    output_path = year_dir / 'aoi_raw_true_color.png'

    with rasterio.open(red_path) as red_src:
        red_dn = red_src.read(1).astype('float32')
    with rasterio.open(green_path) as green_src:
        green_dn = green_src.read(1).astype('float32')
    with rasterio.open(blue_path) as blue_src:
        blue_dn = blue_src.read(1).astype('float32')

    red = red_dn * 0.0000275 - 0.2
    green = green_dn * 0.0000275 - 0.2
    blue = blue_dn * 0.0000275 - 0.2

    valid = (red_dn > 0) & (green_dn > 0) & (blue_dn > 0)
    rgb = np.stack([red, green, blue], axis=-1)

    # One fixed physical range for both years. This avoids automatic
    # per-scene contrast changes and keeps the two observations comparable.
    rgb = np.clip(rgb / 0.30, 0.0, 1.0)
    rgb[~valid] = 0.0

    if not np.any(valid):
        raise HTTPException(status_code=422, detail='RGB data contains no valid pixels')

    plt.imsave(output_path, rgb, format='png')

    return FileResponse(output_path, media_type='image/png')

@app.get('/aoi')
def aoi():
    if not AOI_PATH.exists():
        raise HTTPException(status_code=404, detail='AOI not found')
    with AOI_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)

if DATA_ROOT.exists():
    app.mount('/satellite-data', StaticFiles(directory=DATA_ROOT), name='satellite-data')
if DIST_DIR.exists() and (DIST_DIR / 'assets').exists():
    app.mount('/assets', StaticFiles(directory=DIST_DIR / 'assets'), name='assets')
if DOCS_DIR.exists():
    app.mount('/docs_static', StaticFiles(directory=DOCS_DIR), name='docs_static')

@app.get('/', include_in_schema=False)
def root():
    return RedirectResponse('/dashboard/')

@app.get('/dashboard', include_in_schema=False)
@app.get('/dashboard/', include_in_schema=False)
def dashboard():
    index = DIST_DIR / 'index.html'
    if not index.exists():
        raise HTTPException(status_code=503, detail='Frontend build not found. Run npm run build.')
    return FileResponse(index)