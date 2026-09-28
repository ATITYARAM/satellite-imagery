import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const CHENNAI_CENTER = [12.8, 80.2];

export default function MapView({ activeSection, mapData, onSegmentSelect }) {
  const currentInfo = SECTIONS.find((s) => s.id === activeSection) || SECTIONS[0];
  const Icon = currentInfo.icon;

  const getPriorityColor = (priority) => {
    if (priority === 'High') return '#ef4444';
    if (priority === 'Medium') return '#f59e0b';
    return '#10b981';
  };

  const getSectionColor = (sectionId) => {
    const sec = SECTIONS.find(s => s.id === sectionId);
    return sec ? sec.color : '#3b82f6';
  };

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: '#1e293b' }}>
      <div style={{ 
        position: 'absolute', top: '20px', left: '20px', zIndex: 1000, 
        backgroundColor: 'rgba(15, 23, 42, 0.85)', padding: '10px 20px', 
        borderRadius: '8px', color: 'white', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', gap: '10px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
      }}>
        <Icon size={20} color={currentInfo.color} />
        <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Active View: {currentInfo.name}</h3>
      </div>

      <MapContainer center={CHENNAI_CENTER} zoom={10} style={{ height: '100%', width: '100%', backgroundColor: '#0f172a' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {mapData && mapData.features && mapData.features.map((feature, idx) => {
          const coords = feature.geometry.coordinates; // [lon, lat]
          const p = feature.properties;
          
          let fillColor = getSectionColor(activeSection);
          if (activeSection === 'prediction') {
            fillColor = getPriorityColor(p.priority_class);
          }

          return (
            <CircleMarker 
              key={idx}
              center={[coords[1], coords[0]]} 
              radius={activeSection === 'prediction' ? 8 : 5}
              pathOptions={{ 
                color: '#000', weight: 1, 
                fillColor: fillColor, fillOpacity: 0.8 
              }}
              eventHandlers={{
                click: () => onSegmentSelect(p.segment_id)
              }}
            >
              <Popup>
                <div style={{ color: '#333' }}>
                  <strong>Segment ID:</strong> {p.segment_id}<br/>
                  {activeSection === 'prediction' && (
                    <>
                      <strong>Predicted Change:</strong> {p.predicted_change ? p.predicted_change.toFixed(3) : 'N/A'} m<br/>
                      <strong>Priority:</strong> {p.priority_class}<br/>
                    </>
                  )}
                  <strong>Coordinates:</strong> {coords[1].toFixed(4)}, {coords[0].toFixed(4)}<br/>
                  <hr style={{ margin: '5px 0' }}/>
                  <small style={{ color: '#f59e0b', fontWeight: 'bold' }}>DATA STATUS: Synthetic demonstration</small>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      
      {activeSection === 'prediction' && (
        <div style={{
            position: 'absolute', bottom: '30px', left: '20px', zIndex: 1000,
            backgroundColor: 'rgba(15, 23, 42, 0.85)', padding: '10px 15px',
            borderRadius: '8px', color: 'white', backdropFilter: 'blur(4px)',
            boxShadow: '0 4px 6px rgba(0,0,0,0.3)', fontSize: '0.85rem'
        }}>
            <div style={{ fontWeight: 'bold', marginBottom: '5px' }}>Priority Legend</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#ef4444' }}></div> High
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: '3px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#f59e0b' }}></div> Medium
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#10b981' }}></div> Low
            </div>
        </div>
      )}
    </div>
  );
}