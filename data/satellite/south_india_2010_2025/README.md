# Southern India Satellite Archive (2010–2025)

This folder is the dedicated archive area for Domain 1: satellite imagery in the Coastal Erosion Monitoring and Prediction Platform. It is separate from the legacy example datasets directly under data/satellite/ (including 2016, 2026 and raw).

## Scope

- Inclusive period: 2010-01-01 through 2025-12-31.
- Provider: Microsoft Planetary Computer STAC catalogue.
- Landsat: landsat-c2-l2 (Collection 2 Level-2).
- Sentinel-2: sentinel-2-l2a (Level-2A surface reflectance).
- Geographic scope: the eight members used here for the Southern Zonal Council: Andhra Pradesh, Karnataka, Kerala, Tamil Nadu, Telangana, Puducherry, Andaman and Nicobar Islands, and Lakshadweep.
- Boundary source: geoBoundaries gbOpen India ADM1; selected geometries and source attribution are saved under aoi/ and metadata/ on the first catalogue run.

This scope uses full administrative geometries, not a coast-only buffer. Later, imagery can be filtered or clipped to coastal analysis zones, but the discovery catalogue remains auditable.

## Collection stages

1. Discover and catalogue all matching scene products. Do not apply the 50-date target or cloud exclusion at this stage.
2. Review actual counts and coverage by year, acquisition date, collection, and regional member.
3. Choose up to 50 well-distributed eligible acquisition dates per year where the catalogue supports them. Keep the random seed and selection rules in a sampling log; do not invent dates if the archive has fewer eligible observations.
4. Approve the asset/band list and estimate storage from actual asset sizes.
5. Download selected products in resumable batches, preserve QA bands and source metadata, validate files, and then build analysis-ready clips.

## Catalogue command

From the repository root, install or activate the project environment with the dependencies in requirements.txt, then run:

    python scripts/catalogue_south_india_satellite.py

The script discovers the regional AOI and queries every region member, year and collection. Query results are checkpointed in .work/catalogue.sqlite; interrupted or failed queries can be retried by rerunning the same command. The catalogue includes cloudy scenes: cloud percentage is metadata, not an exclusion filter.

Outputs produced by the script:

- catalog/scene_catalog.csv — one row per scene product, with acquisition timestamp, platform, product/path/tile fields where available, bounds, region intersections, and asset URLs.
- catalog/stac_items.jsonl.gz — compressed original STAC items for full provenance.
- catalog/query_log.csv — status of every regional-member/year/collection query.
- metadata/catalogue_run.json — summary counts and coverage by year.
- aoi/southern_zonal_council_members.geojson and metadata/aoi_source.json — AOI geometry and source attribution.

Important: these catalogue files are generated outputs. Their absence before the script runs means discovery has not yet completed. No scene counts are asserted until the query finishes.

## Storage policy

The repository should retain the AOI, catalogue, query log, sampling records and metadata. Do not put a large multi-year stack of TIFF/JP2 assets into ordinary Git history. After scene counts and sizes are known, choose Git LFS with an explicit size/budget limit or a separate data store for actual imagery. Keep source asset URLs and checksums in the catalogue either way.

## Scientific/provenance rules

- Original acquisition timestamps remain in UTC and are never replaced with download dates.
- Different scenes/sensors and overlapping footprints remain separate products even when dates match.
- Retain cloudy scenes in the inventory; assess per-pixel QA and local shoreline visibility later.
- Preserve original band assets and quality masks. Derived indices and clipped/harmonized products are separate processing outputs.
- Never create synthetic observations for missing dates.
- Record catalogue run date, source, item IDs, collection, and available quality metadata.
- Recheck provider availability and data/product terms before bulk downloads.

## Sources

- Microsoft Planetary Computer STAC API: https://planetarycomputer.microsoft.com/api/stac/v1/
- Landsat Collection 2 Level-2 collection: https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2
- Sentinel-2 Level-2A collection: https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a
- geoBoundaries open boundary API: https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/
- geoBoundaries API and CC BY 4.0 attribution guidance: https://www.geoboundaries.org/api.html
- Government of India, Southern Zonal Council composition: https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2301113&lang=1&reg=3
