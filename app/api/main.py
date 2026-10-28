from __future__ import annotations

import csv
import json
import shutil
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.domains.xgboost_pipeline import RESULT_IMAGE, run_xgboost
from app.domains.forecast_pipeline import forecast_image, run_forecast

ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = ROOT / 'dist'
DOCS_DIR = ROOT / 'docs'
AOI_PATH = ROOT / 'config' / 'aoi.geojson'
DATA_ROOT = ROOT / 'data' / 'satellite'
COMPARISON_ROOT = ROOT / 'data' / 'satellite_comparison'
ARCHIVE_ROOT = ROOT / 'data_external' / 'thiruvananthapuram_2015_2025'
ARCHIVE_CATALOG = ROOT / 'data' / 'satellite' / 'thiruvananthapuram_2015_2025' / 'catalog' / 'selected_dates.csv'

COMPARISON_BANDS = ('red', 'green', 'blue')

def current_aoi_bounds():
    if not AOI_PATH.exists():
        return None
    with AOI_PATH.open('r', encoding='utf-8') as handle:
        geojson = json.load(handle)
    ring = geojson['features'][0]['geometry']['coordinates'][0]
    xs = [point[0] for point in ring]
    ys = [point[1] for point in ring]
    return [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]

app = FastAPI(title='Coastal Erosion Prediction Platform API', version='0.1.0')
XGBOOST_RUN_LOCK = threading.Lock()
FORECAST_RUN_LOCK = threading.Lock()

@app.get('/health')
def health():
    return {'status': 'ok'}

@app.get('/project/info')
def project_info():
    return {
        'project': 'Coastal Erosion Prediction Platform',
        'study_area': 'Thiruvananthapuram Coast, Kerala (Shanghumugham–Valiyathura–Poonthura)',
        'domains': ['Satellite Imagery', 'Shoreline History', 'Terrain', 'Rainfall / Weather', 'Ocean Conditions'],
        'stage': 'clean baseline',
    }

@app.get('/domains')
def domains():
    return ['satellite', 'history', 'terrain', 'weather', 'ocean', 'prediction', 'result']

def _rgb_valid_coverage(directory: Path) -> float | None:
    """Return the fraction of pixels valid in all three display bands."""
    if not _valid_rgb_bands(directory):
        return None
    import numpy as np
    import rasterio

    masks = []
    for band in COMPARISON_BANDS:
        with rasterio.open(directory / f'{band}.tif') as source:
            values = source.read(1)
            valid = np.isfinite(values) & (values > 0)
            if source.nodata is not None:
                valid &= values != source.nodata
            masks.append(valid)
    return float(np.logical_and.reduce(masks).mean())


def _selected_comparison_scene(year: int) -> dict:
    """Read the chosen catalogue record, substituting only for inadequate AOI coverage."""
    if year not in (2015, 2025):
        raise HTTPException(status_code=404, detail='Only 2015 and 2025 comparison images are available.')
    if not ARCHIVE_CATALOG.is_file():
        raise HTTPException(status_code=500, detail='Selected-scene catalogue is missing.')
    try:
        with ARCHIVE_CATALOG.open(newline='', encoding='utf-8') as handle:
            rows = [row for row in csv.DictReader(handle) if row.get('year') == str(year)]
        if not rows:
            raise ValueError(f'No selected {year} scene exists in the catalogue.')
        rows.sort(key=lambda row: row['acquisition_datetime_utc'])
        selected = rows[0] if year == 2015 else rows[-1]
        required = ('collection_id', 'item_id', 'acquisition_date_utc', 'acquisition_datetime_utc')
        if any(not selected.get(key) for key in required):
            raise ValueError(f'Selected {year} catalogue record is incomplete.')
        if year == 2015:
            return selected

        # The last selected 2025 scene is the intended record, but its local
        # clipped RGB coverage is only ~25%. Prefer the nearest earlier
        # selected Landsat scene with >=75% real AOI coverage so the comparison
        # does not imply that nodata is ocean or land.
        original = selected
        for candidate in reversed(rows[:-1]):
            if candidate.get('collection_id') != 'landsat-c2-l2':
                continue
            coverage = _rgb_valid_coverage(_archive_directory(candidate))
            if coverage is not None and coverage >= 0.75:
                candidate = candidate.copy()
                candidate['comparison_selection'] = 'coverage_substitution'
                candidate['original_last_selected_item_id'] = original['item_id']
                candidate['original_last_selected_datetime'] = original['acquisition_datetime_utc']
                candidate['original_last_selected_coverage_percent'] = round((_rgb_valid_coverage(_archive_directory(original)) or 0) * 100, 2)
                return candidate
        selected['comparison_selection'] = 'catalogue_last_selected'
        return selected
    except (OSError, csv.Error, KeyError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f'Could not read selected-scene catalogue: {exc}') from exc


def _comparison_directory(scene: dict) -> Path:
    return COMPARISON_ROOT / scene['year'] / scene['item_id']


def _archive_directory(scene: dict) -> Path:
    return (
        ARCHIVE_ROOT / scene['year'] / scene['acquisition_date_utc'] /
        scene['collection_id'] / scene['item_id']
    )


def _valid_rgb_bands(directory: Path) -> bool:
    return all((directory / f'{band}.tif').is_file() and (directory / f'{band}.tif').stat().st_size > 0 for band in COMPARISON_BANDS)


def _comparison_metadata(scene: dict) -> dict:
    metadata = {
        'source': 'Microsoft Planetary Computer',
        'collection': scene['collection_id'],
        'item_id': scene['item_id'],
        'acquisition_date': scene['acquisition_date_utc'],
        'acquisition_datetime': scene['acquisition_datetime_utc'],
        'platform': scene.get('platform'),
        'cloud_cover_percent': float(scene['cloud_cover_percent']) if scene.get('cloud_cover_percent') else None,
        'year': int(scene['year']),
        'study_area': 'config/aoi.geojson',
        'bands': [f'{band}.tif' for band in COMPARISON_BANDS],
    }
    if scene.get('comparison_selection') == 'coverage_substitution':
        metadata['selection_note'] = (
            'The catalogue last-selected 2025 scene has insufficient AOI coverage; '
            'the nearest earlier selected Landsat scene with adequate cached coverage is displayed.'
        )
        metadata['original_last_selected_item_id'] = scene['original_last_selected_item_id']
        metadata['original_last_selected_datetime'] = scene['original_last_selected_datetime']
        metadata['original_last_selected_coverage_percent'] = scene['original_last_selected_coverage_percent']
    return metadata


def _download_comparison_scene(year: int) -> tuple[Path, dict]:
    """Use the selected archive scene, downloading only when its RGB cache is absent."""
    import planetary_computer
    import pystac_client
    import rasterio
    from rasterio.mask import mask
    from rasterio.warp import transform_geom

    scene = _selected_comparison_scene(year)
    collection, item_id = scene['collection_id'], scene['item_id']
    output_dir = _comparison_directory(scene)
    output_dir.mkdir(parents=True, exist_ok=True)
    band_paths = [output_dir / f'{name}.tif' for name in COMPARISON_BANDS]
    if _valid_rgb_bands(output_dir):
        return output_dir, _comparison_metadata(scene)

    # The catalogue downloader has already clipped the exact selected scene.
    # Populate the designated comparison cache from it before contacting MPC.
    archive_dir = _archive_directory(scene)
    if _valid_rgb_bands(archive_dir):
        for band_name, out_path in zip(COMPARISON_BANDS, band_paths):
            shutil.copy2(archive_dir / f'{band_name}.tif', out_path)
        metadata = _comparison_metadata(scene)
        (output_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        return output_dir, metadata

    if not AOI_PATH.is_file():
        raise HTTPException(status_code=500, detail="Study-area file config/aoi.geojson is missing.")
    with AOI_PATH.open("r", encoding="utf-8") as handle:
        aoi = json.load(handle)
    geometry = aoi["features"][0]["geometry"]

    try:
        catalog = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1/")
        search = catalog.search(collections=[collection], ids=[item_id], max_items=1)
        items = list(search.items())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'Microsoft Planetary Computer request failed for {item_id}: {exc}') from exc
    if not items:
        raise HTTPException(status_code=502, detail=f"Microsoft Planetary Computer did not return scene {item_id}.")
    item = planetary_computer.sign(items[0])

    for band_name in ("red", "green", "blue"):
        asset = item.assets.get(band_name)
        if asset is None:
            raise HTTPException(status_code=502, detail=f"Scene {item_id} has no {band_name} asset.")
        out_path = output_dir / f"{band_name}.tif"
        try:
            with rasterio.open(asset.href) as source:
                geometry_in_crs = transform_geom("EPSG:4326", source.crs, geometry, precision=6)
                clipped, transform = mask(source, [geometry_in_crs], crop=True)
                if clipped.size == 0:
                    raise ValueError('AOI clipping produced no pixels')
                profile = source.profile.copy()
                profile.update(driver="GTiff", height=clipped.shape[1], width=clipped.shape[2], transform=transform, count=1)
                with rasterio.open(out_path, "w", **profile) as target:
                    target.write(clipped[0], 1)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f'Could not download or clip {band_name} for {item_id}: {exc}') from exc

    metadata = _comparison_metadata(scene)
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output_dir, metadata


@app.get('/satellite/archive-data/{year}')
def satellite_archive_data(year: int):
    directory, metadata = _download_comparison_scene(year)
    coverage = _rgb_valid_coverage(directory)
    if coverage is None:
        raise HTTPException(status_code=422, detail=f'No valid RGB pixels are available for {year}.')
    return {
        **metadata,
        'valid_pixel_coverage_percent': round(coverage * 100, 2),
        'nodata_pixel_percent': round((1 - coverage) * 100, 2),
        'image_url': f'/satellite/archive-preview/{year}.png',
    }


@app.get('/satellite/archive-preview/{year}.png')
def satellite_archive_preview(year: int):
    """Show first selected 2015 and last selected 2025 scenes, downloaded separately from Microsoft."""
    if year not in (2015, 2025):
        raise HTTPException(status_code=404, detail="Only 2015 and 2025 comparison images are available.")

    year_dir, _ = _download_comparison_scene(year)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio

    output_path = year_dir / f"{year}_rgb_preview_rgba_v2.png"
    if output_path.is_file() and output_path.stat().st_size > 0:
        return FileResponse(output_path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    # Compute one robust per-band display range across both comparison dates.
    # This keeps their brightness comparable while excluding all nodata values.
    comparison_dirs = {year: year_dir}
    for other_year in (2015, 2025):
        if other_year != year:
            comparison_dirs[other_year], _ = _download_comparison_scene(other_year)

    display_ranges = []
    for band_name in COMPARISON_BANDS:
        valid_values = []
        for directory in comparison_dirs.values():
            with rasterio.open(directory / f'{band_name}.tif') as source:
                values = source.read(1).astype('float32')
                valid = np.isfinite(values) & (values > 0)
                if source.nodata is not None:
                    valid &= values != source.nodata
                if np.any(valid):
                    valid_values.append(values[valid])
        if not valid_values:
            raise HTTPException(status_code=422, detail=f'No valid pixels in comparison {band_name} bands.')
        combined = np.concatenate(valid_values)
        low, high = np.percentile(combined, (2, 98))
        display_ranges.append((float(low), float(high)))

    scaled_bands, valid_masks = [], []
    for band_name, (low, high) in zip(COMPARISON_BANDS, display_ranges):
        with rasterio.open(year_dir / f'{band_name}.tif') as source:
            values = source.read(1).astype('float32')
            valid = np.isfinite(values) & (values > 0)
            if source.nodata is not None:
                valid &= values != source.nodata
        scaled = np.zeros_like(values, dtype='float32')
        scaled[valid] = np.clip((values[valid] - low) / max(high - low, 1e-6), 0.0, 1.0)
        scaled_bands.append(scaled)
        valid_masks.append(valid)

    rgb_valid = np.logical_and.reduce(valid_masks)
    if not np.any(rgb_valid):
        raise HTTPException(status_code=422, detail=f'No common valid RGB pixels in {year} imagery.')
    rgba = np.dstack([*scaled_bands, rgb_valid.astype('float32')])
    plt.imsave(output_path, rgba, format="png")
    return FileResponse(output_path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})


@app.get('/satellite/data')
def satellite_data():
    result = {'source': 'Microsoft Planetary Computer', 'years': {}}
    for year in (2015, 2025):
        year_dir = DATA_ROOT / str(year)
        metadata_path = year_dir / 'metadata.json'
        if not metadata_path.exists():
            result['years'][str(year)] = {'available': False}
            continue
        with metadata_path.open('r', encoding='utf-8') as handle:
            metadata = json.load(handle)
        expected_bounds = current_aoi_bounds()
        band_files_present = all(
            (year_dir / f"{name}.tif").exists()
            for name in ('B2_blue', 'B3_green', 'B4_red', 'B5_nir', 'B6_swir1', 'B7_swir2')
        )
        metadata_bounds = metadata.get('aoi_bounds')
        metadata['available'] = bool(
            band_files_present
            and expected_bounds is not None
            and metadata_bounds == expected_bounds
        )
        if not metadata['available']:
            metadata['unavailable_reason'] = (
                'Satellite data has not yet been downloaded for the current study area. '
                'Run: python scripts/download_landsat_aoi.py'
            )
        metadata['preview_url'] = f'/satellite/rgb/{year}.png'
        metadata['color_preview_url'] = f'/satellite/color/{year}.png'
        metadata['download_urls'] = {
            name: f'/satellite-data/{year}/{Path(info["path"]).name}'
            for name, info in metadata.get('bands', {}).items()
        }
        metadata['metadata_url'] = f'/satellite-data/{year}/metadata.json'
        result['years'][str(year)] = metadata
    return result

@app.get('/satellite/rgb/{year}.png')
def satellite_rgb(year: int):
    if year not in (2015, 2025):
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


@app.get('/satellite/color/{year}.png')
def satellite_color(year: int):
    if year not in (2015, 2025):
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

    output_path = year_dir / 'aoi_color_true_color.png'

    # The PNG is only a display rendering of the clipped, georeferenced AOI
    # GeoTIFFs. Keep the source bands untouched and reuse the cached rendering.
    if output_path.is_file() and output_path.stat().st_size > 0:
        return FileResponse(output_path, media_type='image/png')

    bands = []
    for path in (red_path, green_path, blue_path):
        with rasterio.open(path) as src:
            dn = src.read(1).astype('float32')
        reflectance = dn * 0.0000275 - 0.2
        valid = dn > 0
        values = reflectance[valid]
        if values.size == 0:
            raise HTTPException(status_code=422, detail='RGB data contains no valid pixels')
        low, high = np.percentile(values, (2, 98))
        band = np.clip((reflectance - low) / max(high - low, 1e-6), 0.0, 1.0)
        band[~valid] = 0.0
        bands.append(band)

    rgb = np.stack(bands, axis=-1)
    plt.imsave(output_path, rgb, format='png')
    return FileResponse(output_path, media_type='image/png')


SHORELINE_DIR = ROOT / 'data' / 'shoreline_history' / 'thiruvananthapuram'
SHORELINE_GEOJSON = SHORELINE_DIR / 'shoreline_lines.geojson'
SHORELINE_METADATA = SHORELINE_DIR / 'extraction_metadata.json'


@app.get('/shoreline/data')
def shoreline_data():
    """Return extracted CoastSat shoreline GeoJSON and its provenance."""
    if not SHORELINE_GEOJSON.is_file():
        return {
            'available': False,
            'source': 'CoastSat',
            'geojson': {'type': 'FeatureCollection', 'features': []},
            'metadata': None,
            'message': (
                'Real shoreline data is not available yet. '
                'Run scripts/extract_thiruvananthapuram_shorelines.py '
                'after configuring CoastSat and Earth Engine.'
            ),
        }

    try:
        with SHORELINE_GEOJSON.open('r', encoding='utf-8') as handle:
            geojson = json.load(handle)

        if geojson.get('type') != 'FeatureCollection' or not isinstance(
            geojson.get('features'), list
        ):
            raise ValueError('Expected a GeoJSON FeatureCollection')

        metadata = None
        if SHORELINE_METADATA.is_file():
            with SHORELINE_METADATA.open('r', encoding='utf-8') as handle:
                metadata = json.load(handle)

        return {
            'available': True,
            'source': 'CoastSat',
            'geojson': geojson,
            'metadata': metadata,
            'feature_count': len(geojson['features']),
            'message': (
                'Extracted shoreline features are available; visual quality '
                'review is required before scientific interpretation.'
            ),
        }
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f'Could not read shoreline extraction output: {exc}',
        ) from exc


def _run_xgboost_response(force: bool = False):
    # The result page can request metadata and the PNG at the same time, and
    # React may issue both GET /result and POST /run on mount. Queue duplicate
    # requests instead of returning 409 while the first expensive model run is
    # still working. Only the request that acquires the lock immediately may
    # force a fresh run; queued requests reuse the cache created by that run.
    acquired_immediately = XGBOOST_RUN_LOCK.acquire(blocking=False)
    if not acquired_immediately:
        XGBOOST_RUN_LOCK.acquire()
    try:
        return run_xgboost(force=bool(force and acquired_immediately))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'XGBoost run failed: {exc}') from exc
    finally:
        XGBOOST_RUN_LOCK.release()


@app.get('/xgboost/result')
def xgboost_result(force: bool = False):
    """Return the cached result or generate a reproducible result on demand."""
    return _run_xgboost_response(force)


@app.post('/xgboost/run')
def xgboost_run(force: bool = True):
    """Explicit run endpoint used by the result-page action."""
    return _run_xgboost_response(force)


@app.get('/xgboost/result.png')
def xgboost_result_image():
    """Serve the cached map without starting a second model run.

    The result JSON endpoint can trigger training while the browser requests
    the PNG immediately afterwards. Calling run_xgboost here as well races the
    run lock and turns a valid map request into a 500. Only generate a result
    when the image is genuinely absent.
    """
    try:
        if not RESULT_IMAGE.is_file() or RESULT_IMAGE.stat().st_size == 0:
            _run_xgboost_response(force=False)
        if not RESULT_IMAGE.is_file() or RESULT_IMAGE.stat().st_size == 0:
            raise FileNotFoundError('XGBoost result image was not created')
        return FileResponse(
            RESULT_IMAGE,
            media_type='image/png',
            headers={'Cache-Control': 'no-cache, must-revalidate'},
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'XGBoost result image failed: {exc}') from exc


def _forecast_response(year: int, force: bool = False):
    if not FORECAST_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='A forecast artifact is already being generated. Please retry shortly.')
    try:
        return run_forecast(year, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Forecast generation failed: {exc}') from exc
    finally:
        FORECAST_RUN_LOCK.release()


@app.get('/forecast/{year}')
def forecast_result(year: int):
    return _forecast_response(year)


@app.post('/forecast/{year}/run')
def forecast_run(year: int):
    return _forecast_response(year, force=True)


@app.get('/forecast/{year}/map.png')
def forecast_map(year: int):
    if not FORECAST_RUN_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='Forecast artifact is being generated. Please retry shortly.')
    try:
        path = forecast_image(year)
        return FileResponse(path, media_type='image/png', headers={'Cache-Control': 'no-store'})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Forecast map failed: {exc}') from exc
    finally:
        FORECAST_RUN_LOCK.release()


@app.get('/forecast/{year}/transects.geojson')
def forecast_transects(year: int):
    result = _forecast_response(year)
    path = ROOT / 'output' / 'forecasts' / str(year) / 'transects.geojson'
    if not path.is_file():
        raise HTTPException(status_code=500, detail='Forecast transect GeoJSON was not created.')
    return FileResponse(path, media_type='application/geo+json', headers={'Cache-Control': 'no-store'})


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
