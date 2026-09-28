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

@app.get('/aoi')
def aoi():
    if not AOI_PATH.exists():
        raise HTTPException(status_code=404, detail='AOI not found')
    with AOI_PATH.open('r', encoding='utf-8') as handle:
        return json.load(handle)

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