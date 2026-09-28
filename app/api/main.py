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

    output_path = year_dir / 'aoi_rgb.png'
    if not output_path.exists():
        with rasterio.open(red_path) as red_src, rasterio.open(green_path) as green_src, rasterio.open(blue_path) as blue_src:
            red = red_src.read(1).astype('float32')
            green = green_src.read(1).astype('float32')
            blue = blue_src.read(1).astype('float32')

        stack = np.stack([red, green, blue], axis=-1)
        valid = np.all(np.isfinite(stack) & (stack > 0), axis=-1)
        if not np.any(valid):
            raise HTTPException(status_code=422, detail='RGB data contains no valid pixels')

        rgb = np.zeros_like(stack, dtype='float32')
        for channel in range(3):
            values = stack[:, :, channel][valid]
            low, high = np.percentile(values, [2, 98])
            if high <= low:
                high = low + 1.0
            rgb[:, :, channel] = np.clip(
                (stack[:, :, channel] - low) / (high - low),
                0.0,
                1.0,
            )

        rgb[~valid] = 0.0

        fig = plt.figure(figsize=(7.2, 10.5), dpi=120, frameon=False)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.imshow(rgb, interpolation='nearest')
        ax.axis('off')
        fig.savefig(
            output_path,
            dpi=120,
            bbox_inches='tight',
            pad_inches=0,
            facecolor='black',
        )
        plt.close(fig)

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