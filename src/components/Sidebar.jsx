import React from 'react';
import { CloudRain, Mountain, Wind, Waves, History, Cpu, ChevronRight, Activity } from 'lucide-react';

export const SECTIONS = [
  { id: 'satellite', name: '1. Satellite Imagery', icon: Activity, color: '#3b82f6', desc: 'Spectral Features & Coastal State' },
  { id: 'history', name: '2. Shoreline History', icon: History, color: '#8b5cf6', desc: 'Historical Coastal Movement' },
  { id: 'terrain', name: '3. Terrain', icon: Mountain, color: '#10b981', desc: 'Elevation & Coastal Topography' },
  { id: 'weather', name: '4. Rainfall / Weather', icon: CloudRain, color: '#f59e0b', desc: 'Precipitation & Atmospheric Forcing' },
  { id: 'ocean', name: '5. Ocean Conditions', icon: Waves, color: '#06b6d4', desc: 'Wave & Hydrodynamic Forcing' },
  { id: 'prediction', name: '6. AI Master Prediction', icon: Cpu, color: '#ef4444', desc: 'Five-Domain ML Fusion', isAI: true }
];

export default function Sidebar({ activeSection, onSelect }) {
  return (
    <div className="sidebar" style={{ width: '340px', backgroundColor: '#0f172a', color: 'white', display: 'flex', flexDirection: 'column', height: '100vh', overflowY: 'auto' }}>
      <div className="sidebar-header" style={{ padding: '20px' }}>
        <h2 style={{ fontSize: '1.25rem', margin: '0 0 10px 0' }}>Coastal Erosion Prediction Platform</h2>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', margin: '0 0 10px 0' }}>
          Create a satellite-image analytics system to monitor and predict coastal erosion patterns. The solution should integrate spatial datasets such as maps, satellite imagery, terrain, rainfall, infrastructure, and field records to generate meaningful decision layers. The outcome may include risk maps, priority zones, dashboards, and validation using historical records or expert-labelled ground truth.
        </p>
        <div style={{ backgroundColor: '#f59e0b', color: '#fff', fontSize: '0.75rem', padding: '5px', borderRadius: '4px', fontWeight: 'bold', textAlign: 'center' }}>
          SYNTHETIC DATA — PIPELINE DEMONSTRATION
        </div>
      </div>

      <div className="section-nav" style={{ padding: '10px 20px', flex: 1 }}>
        {SECTIONS.map((sec) => {
          const Icon = sec.icon;
          const isActive = activeSection === sec.id;
          const bg = isActive ? (sec.isAI ? 'rgba(239, 68, 68, 0.15)' : 'rgba(59, 130, 246, 0.15)') : 'transparent';
          const borderLeft = isActive ? `4px solid ${sec.color}` : '4px solid transparent';

          return (
            <button
              key={sec.id}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '12px',
                marginBottom: '8px',
                backgroundColor: bg,
                border: 'none',
                borderLeft: borderLeft,
                borderRadius: '0 8px 8px 0',
                color: 'white',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'background-color 0.2s'
              }}
              onClick={() => onSelect(sec.id)}
              onDoubleClick={(e) => {
                  if (sec.id === 'satellite' && window.onSatelliteDoubleClick) {
                      window.onSatelliteDoubleClick();
                  }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Icon size={20} color={sec.color} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{sec.name}</div>
                  <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '2px' }}>{sec.desc}</div>
                </div>
              </div>
              <ChevronRight size={16} style={{ opacity: isActive ? 1 : 0.3 }} />
            </button>
          );
        })}
      </div>
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <a href="/docs_static/presentation/project_status.html" target="_blank" style={{ color: '#3b82f6', fontSize: '0.8rem', textDecoration: 'none' }}>PROJECT PRESENTATION</a>
      </div>
    </div>
  );
}
