# Domain 1 — Satellite Imagery

## Purpose
Provides multispectral imagery over the Cuddalore study area for spectral-index
computation and shoreline extraction.

## Data Source
**Landsat Collection 2 Level-2** via Microsoft Planetary Computer STAC API  
Endpoint: `https://planetarycomputer.microsoft.com/api/stac/v1`  
Collection: `landsat-c2-l2`  
Sensors: Landsat 8 OLI-TIRS, Landsat 9 OLI-2-TIRS-2  
Bands: B2 (Blue), B3 (Green), B4 (Red), B5 (NIR), B6 (SWIR1), B10 (TIRS1)  

Scale factor applied: `SR = DN × 0.0000275 − 0.2`

## Status
Pipeline defined in `config/config.json`.  
**Real imagery download requires a Planetary Computer API token** (`PLANETARY_COMPUTER_TOKEN` env var).  
No imagery is bundled in this repository.

## Computed Indices
| Index | Formula | Use |
|-------|---------|-----|
| MNDWI | (Green − SWIR1) / (Green + SWIR1) | Shoreline extraction |
| NDVI  | (NIR − Red) / (NIR + Red) | Vegetation/bare-soil |
| NDWI  | (Green − NIR) / (Green + NIR) | Open water |

## Limitations
- Real imagery not included; pipeline must be run with valid credentials
- Cloud cover threshold ≤ 20 % applied; dense cloud periods may have gaps
- 30 m Landsat resolution limits sub-pixel shoreline accuracy
