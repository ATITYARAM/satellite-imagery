# Forecast outputs

This directory is created and populated by `app/domains/forecast_pipeline.py`.

Generated files are stored by forecast year:

- `output/forecasts/2026/forecast_map.png`
- `output/forecasts/2026/forecast.json`
- `output/forecasts/2026/transects.geojson`
- `output/forecasts/2027/forecast_map.png`
- `output/forecasts/2027/forecast.json`
- `output/forecasts/2027/transects.geojson`

The original spectral-change proxy image in `outputs/xgboost/` is not modified by the forecast renderer.

The forecast maps are clean geographic visualizations of the configured study-area boundary and the current transect scenario records. The scale bar is an approximate 2 km reference at the study area's latitude. A configured study-area boundary is not a measured coastline.

Current shoreline-transect records are illustrative development data. The maps are not real-time observations and must not be presented as validated real-world erosion forecasts. Real-time or scientifically validated results require genuine shoreline observations and verified, time-stamped environmental inputs.
