import React from 'react';
import { MapContainer, TileLayer, Polygon, Polyline, CircleMarker, Popup } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const CUDDALORE_CENTER = [11.7480, 79.7714];

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

export default function MapView({ activeSection }) {
  const currentInfo = SECTIONS.find((s) => s.id === activeSection) || SECTIONS[0];
  const Icon = currentInfo.icon;

  return (
    <div className="map-container">
      {/* Active Section Banner */}
      <div className="map-banner">
        <h3>
          <Icon size={18} color={currentInfo.color} />
          <span>Active View: {currentInfo.name}</span>
        </h3>
      </div>

      <MapContainer center={CUDDALORE_CENTER} zoom={13} style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* SECTION 1: RAINFALL */}
        {activeSection === 'rainfall' && (
          <CircleMarker center={[11.7500, 79.7600]} radius={60} pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.35 }}>
            <Popup><strong>Section 1: Rainfall (GPM)</strong><br />Precipitation Anomaly: 145mm/day</Popup>
          </CircleMarker>
        )}

        {/* SECTION 2: TERRAIN */}
        {activeSection === 'terrain' && (
          <CircleMarker center={[11.7480, 79.7700]} radius={40} pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.4 }}>
            <Popup><strong>Section 2: Terrain (ALOS DEM)</strong><br />Slope Angle: 18.4° (Steep Bluff Zone)</Popup>
          </CircleMarker>
        )}

        {/* SECTION 3: WEATHER */}
        {activeSection === 'weather' && (
          <CircleMarker center={[11.7520, 79.7720]} radius={50} pathOptions={{ color: '#f59e0b', fillColor: '#f59e0b', fillOpacity: 0.4 }}>
            <Popup><strong>Section 3: Weather (ERA5)</strong><br />Peak Wind Vectors: 42 km/h NE</Popup>
          </CircleMarker>
        )}

        {/* SECTION 4: OCEAN */}
        {activeSection === 'ocean' && (
          <CircleMarker center={[11.7450, 79.7750]} radius={55} pathOptions={{ color: '#06b6d4', fillColor: '#06b6d4', fillOpacity: 0.4 }}>
            <Popup><strong>Section 4: Ocean Hydrodynamics</strong><br />Significant Wave Height (Hs): 2.8m</Popup>
          </CircleMarker>
        )}

        {/* SECTION 5: HISTORICAL BASELINE */}
        {activeSection === 'history' && (
          <Polyline positions={mockHistoricalLine} pathOptions={{ color: '#8b5cf6', weight: 4, dashArray: '6, 6' }}>
            <Popup><strong>Section 5: Historical Line</strong><br />1990 - 2024 DSAS Baseline Shift</Popup>
          </Polyline>
        )}

        {/* SECTION 6: AI MASTER PREDICTION */}
        {activeSection === 'prediction' && (
          <Polygon positions={mockPredictionZone} pathOptions={{ color: '#ef4444', fillColor: '#ef4444', fillOpacity: 0.55 }}>
            <Popup>
              <strong>Section 6: AI Master Prediction</strong><br />
              Model: Hybrid XGBoost + ConvLSTM<br />
              Predicted Retreat: 12.4m (Next 90 Days)
            </Popup>
          </Polygon>
        )}
      </MapContainer>
    </div>
  );
}