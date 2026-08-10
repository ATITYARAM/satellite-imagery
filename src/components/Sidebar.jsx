// src/components/Sidebar.jsx
import React from 'react';
import { CloudRain, Mountain, Wind, Waves, History, Cpu } from 'lucide-react';

const LAYERS = [
  { id: 'rainfall', name: '1. Rainfall (GPM)', icon: CloudRain, color: '#3b82f6' },
  { id: 'terrain', name: '2. Terrain (ALOS DEM)', icon: Mountain, color: '#10b981' },
  { id: 'weather', name: '3. Weather & Wind (ERA5)', icon: Wind, color: '#f59e0b' },
  { id: 'ocean', name: '4. Ocean Waves (INCOIS)', icon: Waves, color: '#06b6d4' },
  { id: 'history', name: '5. Historical Erosion', icon: History, color: '#8b5cf6' },
  { id: 'prediction', name: '6. AI Master Prediction', icon: Cpu, color: '#ef4444', isAI: true }
];

export default function Sidebar({ activeLayers, toggleLayer }) {
  return (
    <div className="sidebar">
      <h2>Coastal Analytics</h2>
      <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
        Select layers to analyze or view AI master prediction.
      </p>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '10px' }}>
        {LAYERS.map((layer) => {
          const Icon = layer.icon;
          const isActive = activeLayers[layer.id];
          return (
            <div
              key={layer.id}
              className={`layer-card ${isActive ? 'active' : ''}`}
              onClick={() => toggleLayer(layer.id)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Icon size={20} color={layer.color} />
                <span style={{ fontWeight: layer.isAI ? 'bold' : 'normal', color: layer.isAI ? '#fca5a5' : '#fff' }}>
                  {layer.name}
                </span>
              </div>
              <input type="checkbox" checked={isActive} readOnly />
            </div>
          );
        })}
      </div>
    </div>
  );
}