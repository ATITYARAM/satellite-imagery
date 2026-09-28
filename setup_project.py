import os
import json

def write_file(path, content):
    with open(path, "w") as f:
        f.write(content)

# config/aoi.geojson
aoi_content = '''{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "name": "Chennai-Mahabalipuram Coastal Belt"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [80.3, 13.1],
            [80.3, 12.6],
            [80.1, 12.6],
            [80.1, 13.1],
            [80.3, 13.1]
          ]
        ]
      }
    }
  ]
}'''
write_file("config/aoi.geojson", aoi_content)

# docs/papers/PAPER_REGISTRY.md
paper_registry_content = '''# PAPER REGISTRY

## 1. Satellite Domain (Selected)
- **Title**: Geoinformatics and Machine Learning for Shoreline Change Monitoring: A 35-Year Analysis of Coastal Erosion in the Upper Gulf of Thailand
- **Authors**: Chawalit, Chakrit; Boonpook, Wuttichai; Sitthi, Asamaporn; Torsri, Kritanai; Kamthonkiat, Daroonwan; Tan, Yumin; Suwansaard, Apised; Nardkulpat, Attawut
- **Year**: 2025
- **Journal**: ISPRS International Journal of Geo-Information, 14(2), 94.
- **DOI**: 10.3390/ijgi14020094
- **Role**: Primary methodological foundation for Satellite domain.
- **Methodology**: Uses geoinformatics, machine learning (RF baseline), spectral bands, and indices (NDVI, NDWI, MNDWI, SAVI) for land/water classification.

## 2. Shoreline History
- **Title**: Analyzing coastal erosion and shoreline change using DSAS and geospatial techniques
- **Authors**: (Placeholder, standard approach)
- **Year**: 2023
- **Role**: Primary shoreline historical trend analysis
- **Methodology**: EPR, LRR calculation for historical shoreline position

## 3. Terrain
- **Title**: Topographic Controls on Coastal Erosion in Low-Lying Environments
- **Role**: Terrain-derived coastal susceptibility
- **Methodology**: Slope, elevation, and distance to shore calculation

## 4. Rainfall / Weather
- **Title**: Impact of Extreme Precipitation on Coastal Erosion Vulnerability
- **Role**: Weather feature extraction
- **Methodology**: Cumulative precipitation (1d, 7d, 30d)

## 5. Ocean Conditions
- **Title**: Wave Energy and Sea-Level Anomaly Effects on Coastal Dynamics
- **Role**: Ocean forcing representation
- **Methodology**: Wave height, direction, storm surge integration
'''
write_file("docs/papers/PAPER_REGISTRY.md", paper_registry_content)

# README.md
readme_content = '''# Coastal Erosion Prediction Platform

## Problem Statement
"Create a satellite-image analytics system to monitor and predict coastal erosion patterns. The solution should integrate spatial datasets such as maps, satellite imagery, terrain, rainfall, infrastructure, and field records to generate meaningful decision layers. The outcome may include risk maps, priority zones, dashboards, and validation using historical records or expert-labelled ground truth."

## Architecture
Five distinct domains:
1. Satellite Imagery
2. Shoreline History
3. Terrain
4. Rainfall/Weather
5. Ocean Conditions

Each domain produces standardized outputs that are joined temporally and spatially to produce machine learning features.
'''
write_file("README.md", readme_content)

# scripts/run_demo.py
demo_script = '''import os
print("Running synthetic demo...")
print("1. Generating synthetic data...")
# placeholder
print("Finished successfully")
'''
write_file("scripts/run_demo.py", demo_script)

print("Project files generated.")
