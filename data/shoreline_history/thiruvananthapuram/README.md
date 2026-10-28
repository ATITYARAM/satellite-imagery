# Domain 2 — Shoreline History: Thiruvananthapuram

## Method selected

This domain uses [CoastSat](https://github.com/kvos/CoastSat), which retrieves available Landsat/Sentinel-2 imagery from Google Earth Engine and extracts satellite-derived shoreline vectors. CoastSat supports Landsat 5, 7, 8, 9 and Sentinel-2; actual coverage depends on sensor availability, image quality, cloud masking, and successful extraction.

The study AOI is read from `config/aoi.geojson` (the existing coastal rectangle around Shanghumugham, Valiyathura and Poonthura). It is not a full municipal boundary.

## Output layout

- `shoreline_lines.geojson` — extracted line geometries in WGS84 (created after a successful run).
- `extraction_metadata.json` — run parameters, actual output count, dates, and limitations.
- Raw image tiles, CoastSat intermediate files, and native output are stored outside Git under `data_external/shoreline_history/thiruvananthapuram/`.
- This README and the extraction script are source-controlled; large imagery is not.

No output dataset is committed yet. Run the workflow to create the actual observations.

## Install CoastSat in a separate environment

Use the current official CoastSat installation instructions. The project recommends a dedicated Mamba/Conda environment, Python 3.11, and the geospatial dependencies below. This is preferable to mixing CoastSat's GDAL/GeoPandas dependencies into the main project virtual environment.

```bash
mamba create -n coastsat
mamba activate coastsat
mamba install python=3.11 geopandas gdal -y
mamba install earthengine-api scikit-image matplotlib astropy notebook -y
pip install pyqt5 imageio-ffmpeg
mamba install pyfes pyyaml -y
```

Clone the official CoastSat repository outside the five domain data folders:

```bash
mkdir -p tools
git clone https://github.com/kvos/CoastSat.git tools/CoastSat
export COASTSAT_PATH="$PWD/tools/CoastSat"
```

If you use a different clone location, set `COASTSAT_PATH` to that directory. The script expects the repository's `coastsat/` package to be importable.

## Google Earth Engine setup

CoastSat retrieves imagery through Google Earth Engine (GEE). You need an eligible GEE account and a registered Google Cloud project. Follow the current [official CoastSat installation/authentication guide](https://github.com/kvos/CoastSat#installation) and the [Google Earth Engine authentication guide](https://developers.google.com/earth-engine/guides/auth).

After completing the required account/project setup and local authentication, set your project ID in the shell:

```bash
export EARTHENGINE_PROJECT="your-registered-ee-project-id"
```

Replace the placeholder with your real project ID. Do not commit credentials, tokens, or private keys.

## Run extraction for 2010–2025

From the repository root with the CoastSat environment activated:

```bash
python scripts/extract_thiruvananthapuram_shorelines.py
```

The default period is `2010-01-01` inclusive through `2026-01-01` exclusive, so the full 2025 calendar year is included. CoastSat requests Landsat 5/7/8/9 and Sentinel-2, but does not guarantee a detection for each year.

For the first run, interactive visual review is recommended:

```bash
python scripts/extract_thiruvananthapuram_shorelines.py --review
```

To permit manual threshold adjustment as well:

```bash
python scripts/extract_thiruvananthapuram_shorelines.py --review --adjust
```

Cloud threshold is a fraction between 0 and 1; default is 0.5. You may need to tune it after inspecting the actual imagery. Review should not be skipped for scientific results.

## Data quality and interpretation

- The workflow records dates actually returned by CoastSat; it does not invent annual observations.
- A successful run does not mean all detections are correct. Inspect saved detection figures and use manual review for initial quality control.
- CoastSat is designed primarily for sandy shorelines. Rocky coast, seawalls, river mouths, and built-up shoreline segments may need separate methods.
- A satellite-derived water/sand boundary is influenced by tide, season, wave run-up, and georeferencing error. Tide correction and uncertainty assessment should be implemented before deriving final erosion rates.
- The current AOI is a simple rectangular coastal study area and should be refined against an authoritative shoreline for final scientific measurements.
- The current script extracts shoreline lines only. Transect construction, shoreline intersections, tide correction, annual/seasonal aggregation, and erosion/accretion rates are follow-on processing steps.

## Official references

- CoastSat source and documentation: https://github.com/kvos/CoastSat
- Google Earth Engine: https://earthengine.google.com/
- Google Earth Engine authentication: https://developers.google.com/earth-engine/guides/auth
- ISRO Shoreline Change Atlas: https://vedas.sac.gov.in/en/Shoreline_Change_Atlas.html
