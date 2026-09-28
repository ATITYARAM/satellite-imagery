import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const CHENNAI_CENTER = [12.8, 80.2];

function fmt(value, digits = 3) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : 'N/A';
}

export default function MapView({ activeSection, mapData, satelliteMapData, onSegmentSelect }) {
  const currentInfo = SECTIONS.find((s) => s.id === activeSection) || SECTIONS[0];
  const Icon = currentInfo.icon;
  const activeData = activeSection === 'satellite' ? satelliteMapData : mapData;

  const getPriorityColor = (priority) => {
    if (priority === 'High') return '#ef4444';
    if (priority === 'Medium') return '#f59e0b';
    return '#10b981';
  };

  const getSatelliteColor = (landWaterClass) => {
    if (landWaterClass === 'water') return '#38bdf8';
    if (landWaterClass === 'land') return '#84cc16';
    return '#94a3b8';
  };

  return (
    <div style={{ position: 'absolute', inset: 0, backgroundColor: '#1e293b' }}>
      <div className="map-banner">
        <Icon size={20} color={currentInfo.color} />
        <h3>Active View: {currentInfo.name}</h3>
      </div>

      <MapContainer center={CHENNAI_CENTER} zoom={10} style={{ height: '100%', width: '100%', backgroundColor: '#0f172a' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {activeData?.features?.map((feature, idx) => {
          const coords = feature.geometry?.coordinates || [];
          const p = feature.properties || {};
          if (coords.length < 2) return null;

          let fillColor = currentInfo.color;
          let radius = 5;
          if (activeSection === 'prediction') {
            fillColor = getPriorityColor(p.priority_class);
            radius = 8;
          } else if (activeSection === 'satellite') {
            fillColor = getSatelliteColor(p.land_water_class);
            radius = 7;
          }

          return (
            <CircleMarker
              key={`${p.segment_id || 'segment'}-${idx}`}
              center={[coords[1], coords[0]]}
              radius={radius}
              pathOptions={{ color: '#000', weight: 1, fillColor, fillOpacity: 0.85 }}
              eventHandlers={{ click: () => onSegmentSelect(p.segment_id) }}
            >
              <Popup>
                <div style={{ minWidth: '210px', color: '#333' }}>
                  <strong>Segment:</strong> {p.segment_id}<br />
                  {activeSection === 'satellite' ? (
                    <>
                      <strong>Land/Water:</strong> {p.land_water_class || 'N/A'}<br />
                      <strong>Water Probability:</strong> {fmt(p.water_probability, 2)}<br />
                      <strong>NDVI:</strong> {fmt(p.ndvi, 3)}<br />
                      <strong>NDWI:</strong> {fmt(p.ndwi, 3)}<br />
                      <strong>MNDWI:</strong> {fmt(p.mndwi, 3)}<br />
                      <strong>SAVI:</strong> {fmt(p.savi, 3)}<br />
                      <strong>Quality:</strong> {p.quality_flag || 'N/A'}<br />
                      <strong>Source:</strong> {p.source_mode || 'N/A'}<br />
                    </>
                  ) : activeSection === 'prediction' ? (
                    <>
                      <strong>Predicted Change:</strong> {fmt(p.predicted_change)} m<br />
                      <strong>Priority:</strong> {p.priority_class || 'N/A'}<br />
                    </>
                  ) : (
                    <>
                      <strong>Domain:</strong> {currentInfo.name}<br />
                    </>
                  )}
                  <strong>Coordinates:</strong> {fmt(coords[1], 4)}, {fmt(coords[0], 4)}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {activeSection === 'prediction' && (
        <div className="map-overlay-legend">
          <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>Priority Legend</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#ef4444' }} /> High</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#f59e0b' }} /> Medium</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#10b981' }} /> Low</div>
        </div>
      )}

      {activeSection === 'satellite' && (
        <div className="map-overlay-legend">
          <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>Satellite Class</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#38bdf8' }} /> Water</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#84cc16' }} /> Land</div>
          <div><span className="legend-dot" style={{ backgroundColor: '#94a3b8' }} /> Unknown</div>
          <div style={{ marginTop: '6px', color: '#f59e0b' }}>Live or synthetic fallback</div>
        </div>
      )}
    </div>
  );
}
