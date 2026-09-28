# PAPER REGISTRY

This registry defines the current five-domain research-system plan.
Each domain has one primary existing paper/system whose methodology is
implemented/adapted in this project. The papers do not need to solve all
five domains themselves.

## 1. Satellite Imagery — PRIMARY

**Paper**: Chawalit, C. et al. (2025), "Geoinformatics and Machine Learning for Shoreline Change Monitoring: A 35-Year Analysis of Coastal Erosion in the Upper Gulf of Thailand."

**Journal**: ISPRS International Journal of Geo-Information, 14(2), 94.

**DOI**: https://doi.org/10.3390/ijgi14020094

**Role**: Satellite-domain foundation.

**Methodology used by this project**:
- Landsat multispectral imagery
- Blue, Green, Red, NIR, SWIR1, SWIR2
- NDVI, NDWI, MNDWI, SAVI
- land/water classification
- Random Forest as the classification method of interest
- shoreline-related spatial output

**Our domain output**:
- per-segment spectral features
- spectral indices
- land/water class
- water probability
- classification confidence
- scene metadata
- quality flags
- GeoJSON map output

**Implementation note**: when labelled training samples are not available locally, the live pipeline uses an explicitly labelled pseudo-label fallback based on MNDWI. This is a local adaptation and is not claimed to be the paper's original training data.

## 2. Shoreline History — PRIMARY

**System**: Vos, K. et al. (2019), "CoastSat: A Google Earth Engine-enabled Python toolkit to extract shorelines from publicly available satellite imagery."

**Journal**: Environmental Modelling & Software, 122, 104528.

**DOI**: https://doi.org/10.1016/j.envsoft.2019.104528

**Role**: Historical shoreline extraction/time-series foundation.

**Methodology used by this project**:
- public Landsat/Sentinel-2 imagery
- shoreline extraction
- transect-based time series
- historical shoreline position

**Expected domain output**:
- transect_id / segment_id
- acquisition date
- shoreline position
- time-series change fields
- quality/uncertainty metadata

## 3. Terrain — PRIMARY

**System**: Hosan, S. et al. (2025), "Predicting coastal erosion susceptibility in Bangladesh under climate scenario via machine learning techniques."

**Journal**: PLOS ONE, 20(11), e0334347.

**DOI**: https://doi.org/10.1371/journal.pone.0334347

**Role**: Terrain-derived coastal susceptibility feature methodology.

**Methodology used by this project**:
- DEM-based topographic processing
- elevation
- slope
- distance/terrain-derived hydrologic variables
- terrain indices such as TWI/TPI/TRI/VDCN where data permit

**Expected domain output**:
- elevation
- slope
- terrain/hydrologic derivatives
- distance-to-shore
- static segment-level terrain features

## 4. Rainfall / Weather — PRIMARY

**System**: Mishra, M. et al. (2022), "Assessment of impacts to the sequence of the tropical cyclone Nisarga and monsoon events in shoreline changes and vegetation damage in the coastal zone of Maharashtra, India."

**Journal**: Marine Pollution Bulletin, 174, 113262.

**DOI**: https://doi.org/10.1016/j.marpolbul.2021.113262

**Role**: Rainfall/event forcing domain.

**Methodology used by this project**:
- GPM rainfall data
- event/monsoon precipitation analysis
- temporal linkage of rainfall and coastal response

**Expected domain output**:
- rainfall totals
- event intensity
- rolling rainfall windows
- anomaly/extreme-event fields where source data support them
- date/segment linkage

## 5. Ocean Conditions — PRIMARY

**System**: "Data-driven modelling of coastal storm erosion for real-time forecasting at a wave-dominated embayed beach" (2024).

**Journal**: Coastal Engineering, 193, 104596.

**DOI**: https://doi.org/10.1016/j.coastaleng.2024.104596

**Role**: Wave and water-level forcing domain.

**Methodology used by this project**:
- wave height
- wave direction
- wave period
- water levels
- storm-event aggregation
- storm wave energy

**Expected domain output**:
- wave height
- wave direction
- wave period
- storm wave energy
- water level / surge proxy
- event windows

## Integration principle

The five systems remain independent:

Satellite
→ Satellite output

Shoreline History
→ Shoreline output

Terrain
→ Terrain output

Rainfall / Weather
→ Weather output

Ocean
→ Ocean output

Only after those outputs are standardized are they fused by spatial and
temporal identifiers for the project's downstream ML stage.

The final ML target is intentionally configurable and is not fixed by this
registry.
