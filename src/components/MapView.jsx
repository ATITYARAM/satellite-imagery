// src/components/MapView.jsx
import React from 'react';
import { MapContainer, TileLayer, Polygon, Polyline, CircleMarker, Popup } from 'react-leaflet';

// Testing Zone Coordinates: Cuddalore Shoreline
const CUDDALORE_CENTER = [11.7480, 79.7714];

// Mock Layer Geo-Data
const mockHistoricalLine = [
  [11.7600, 79.7750],
  [11.7500, 79.7730],
  [11.7400, 79.7710],
  [11.7300, 79.7690]
];

const mockPredictionZone = [
  [11.7550, 79.7740],
  [11.7550, 79.7710],
  [11.7450, 79.7690],
  [11.7450, 79.7720]
];

export default function MapView({ activeLayers }) {
  return (
    <div className="map-container">
      <MapContainer center={CUDDALORE_CENTER} zoom={13} style={{ height: '100%', width: '100%' }}>
        {/* Base Map Layer */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* LAYER 1: Rainfall Overlay */}
        {activeLayers.rainfall && (
          <CircleMarker center={[11.7500, 79.7600]} radius={50} pathOptions={{ color: 'blue', fillColor: 'blue', fillOpacity: 0.3 }}>
            <Popup>GPM Rainfall Anomaly: High Runoff Detected</Popup>
          </CircleMarker>
        )}

        {/* LAYER 5: Historical Erosion Lines */}
        {activeLayers.history && (
          <Polyline positions={mockHistoricalLine} pathOptions={{ color: 'purple', weight: 3, dashArray: '5, 5' }}>
            <Popup>Historical Baseline (1990 - 2024 DSAS Line)</Popup>
          </Polyline>
        )}

        {/* LAYER 6: AI Master Prediction Zone */}
        {activeLayers.prediction && (
          <Polygon positions={mockPredictionZone} pathOptions={{ color: 'red', fillColor: 'red', fillOpacity: 0.5 }}>
            <Popup>
              <strong>AI Master Hazard Zone (XGBoost + ConvLSTM)</strong><br/>
              Predicted Land Retreat: 12.4 meters (Next 90 Days)
            </Popup>
          </Polygon>
        )}
      </MapContainer>
    </div>
  );
}