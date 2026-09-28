import React from 'react';
import { CloudRain, Mountain, Waves, History, Cpu, ChevronRight, Activity, BarChart3 } from 'lucide-react';

export const SECTIONS = [
  { id: 'satellite', name: '1. Satellite Imagery', icon: Activity, color: '#3b82f6', desc: 'Raw Satellite Input' },
  { id: 'history', name: '2. Shoreline History', icon: History, color: '#8b5cf6', desc: 'Historical Coastal Movement' },
  { id: 'terrain', name: '3. Terrain', icon: Mountain, color: '#10b981', desc: 'Elevation & Coastal Topography' },
  { id: 'weather', name: '4. Rainfall / Weather', icon: CloudRain, color: '#f59e0b', desc: 'Precipitation & Atmospheric Forcing' },
  { id: 'ocean', name: '5. Ocean Conditions', icon: Waves, color: '#06b6d4', desc: 'Wave & Hydrodynamic Forcing' },
  { id: 'prediction', name: '6. XGBoost', icon: Cpu, color: '#ef4444', desc: 'ML Processing', isAI: true },
  { id: 'result', name: 'RESULT', icon: BarChart3, color: '#f97316', desc: 'XGBoost Output' },
];

export default function Sidebar({ activeSection, onSelect, onSatelliteDoubleClick }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Coastal Erosion Prediction Platform</h2>
        <p>Chennai–Mahabalipuram Coastal Belt</p>
      </div>
      <nav className="section-nav" aria-label="Project sections">
        {SECTIONS.map((section) => {
          const Icon = section.icon;
          const active = activeSection === section.id;
          const handleClick = () => onSelect(section.id);
          const handleDoubleClick = () => {
            if (section.id === 'satellite') onSatelliteDoubleClick();
          };

          return (
            <button
              key={section.id}
              type="button"
              className={[
                'section-btn',
                active ? 'active' : '',
                active && section.isAI ? 'ai-active' : '',
                active && section.id === 'result' ? 'result-active' : '',
              ].join(' ')}
              onClick={handleClick}
              onDoubleClick={handleDoubleClick}
              aria-current={active ? 'page' : undefined}
              title={section.id === 'satellite' ? 'Double-click to open raw satellite data' : undefined}
            >
              <span className="section-content">
                <Icon size={20} color={section.color} />
                <span>
                  <span className="section-title">{section.name}</span>
                  <span className="section-desc">{section.desc}</span>
                </span>
              </span>
              <ChevronRight size={16} />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
