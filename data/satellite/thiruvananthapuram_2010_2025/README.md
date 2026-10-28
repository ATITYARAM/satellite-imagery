# Thiruvananthapuram Coastal Satellite Archive (2010–2025)

## Scope

- AOI: the existing `config/aoi.geojson` coastal study polygon around Shanghumugham, Valiyathura, and Poonthura. This is not the full municipal boundary.
- Provider: Microsoft Planetary Computer STAC API.
- Collections: `landsat-c2-l2` and `sentinel-2-l2a`.
- Period: inclusive 2010-01-01 through 2025-12-31.
- Sampling target: up to 50 unique acquisition dates per year.
- Default seed: `20261028`; use `--seed` to choose a different seed.
- Sampling unit: distinct acquisition date in UTC, not number of products or tiles.

## Workflow

Run from the repository root with the project Python environment activated:

```bash
python scripts/sample_thiruvananthapuram_satellite.py
```

The script queries the catalogue, filters bbox results against the exact AOI geometry, and writes:

- `catalog/candidate_scenes.csv`: matching scene products and acquisition metadata.
- `catalog/selected_dates.csv`: one selected real scene for each sampled date.
- `catalog/query_log.csv`: success/failure for every year/collection query.
- `metadata/annual_coverage.csv`: target, dates available/selected, and shortfall status.
- `metadata/sampling_manifest.json`: parameters, seed, AOI, collection, rules, and output inventory.

A year with fewer than 50 distinct dates selects all available dates and reports the shortfall. If a year has failed catalogue queries, its coverage status is `catalogue_incomplete` and the shortfall is not confirmed. Never infer missing observations or invent dates. Cloudy scenes remain eligible; their reported cloud cover is metadata used to choose one scene when multiple products share a date.

## Download raster data

```bash
python scripts/sample_thiruvananthapuram_satellite.py --download
```

The default output directory is `data_external/thiruvananthapuram_2010_2025/`. Override it with `--output-dir /path/to/storage` or the `SATELLITE_DATA_DIR` environment variable. Downloads are clipped to the configured AOI and include available optical bands plus the collection's quality layer. Re-running is resumable for existing non-empty band files. The script writes `metadata/download_log.json` after a download run.

## Git and data-storage policy

Commit scripts and the generated catalogue/sampling/metadata files. Do **not** commit the raster files in `data_external/`; that directory is ignored by `.gitignore`. This keeps large imagery out of ordinary Git history. Keep the manifests and download log in Git so every selected date and local download can be audited.

## Important limitations

- Fifty dates per year is a target, not a guarantee. Early years may have fewer distinct observations because only the available Landsat archive contributes.
- A successful STAC query confirms catalogue records, not that every asset download will succeed.
- The AOI is the project's initial rectangular coastal study area; it should be refined against an authoritative shoreline before making scientific erosion measurements.
- The sampler performs no cloud masking, shoreline extraction, NDVI calculation, or erosion prediction.
