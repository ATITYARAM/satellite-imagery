import React from 'react';
import { CloudRain, Mountain, Wind, Waves, History, Cpu, ChevronRight } from 'lucide-react';

export const SECTIONS = [
  { id: 'rainfall', name: '1. Rainfall (GPM)', icon: CloudRain, color: '#3b82f6', desc: 'Precipitation & Runoff' },
  { id: 'terrain', name: '2. Terrain (ALOS DEM)', icon: Mountain, color: '#10b981', desc: 'Elevation & Slope Angle' },
  { id: 'weather', name: '3. Weather (ERA5)', icon: Wind, color: '#f59e0b', desc: 'Wind Velocity & Pressure' },
  { id: 'ocean', name: '4. Ocean Waves (INCOIS)', icon: Waves, color: '#06b6d4', desc: 'Wave Energy & Surges' },
  { id: 'history', name: '5. Historical Baseline', icon: History, color: '#8b5cf6', desc: 'Multi-Decade Shorelines' },
  { id: 'prediction', name: '6. AI Master Prediction', icon: Cpu, color: '#ef4444', desc: 'Hybrid XGBoost + ConvLSTM', isAI: true }
];

export default function Sidebar({ activeSection }) {
  const handleSectionSelect = (sectionId) => {
    // Force a full page refresh with the selected section in the URL
    window.location.search = `?section=${sectionId}`;
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Coastal Analytics</h2>
        <p>Select a section view to reload analytics mode.</p>
      </div>

      <div className="section-nav">
        {SECTIONS.map((sec) => {
          const Icon = sec.icon;
          const isActive = activeSection === sec.id;

          return (
            <button
              key={sec.id}
              className={`section-btn ${isActive ? (sec.isAI ? 'ai-active' : 'active') : ''}`}
              onClick={() => handleSectionSelect(sec.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Icon size={20} color={sec.color} />
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{sec.name}</div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '2px' }}>{sec.desc}</div>
                </div>
              </div>
              <ChevronRight size={16} style={{ opacity: isActive ? 1 : 0.3 }} />
            </button>
          );
        })}
      </div>
    </div>
  );
}