# Coastal Erosion Prediction Platform

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
