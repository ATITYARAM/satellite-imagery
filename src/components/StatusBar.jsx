import React from 'react';
import { SECTIONS } from './Sidebar';

const DOMAIN_STATUS = {
  satellite_imagery: { status: 'pipeline-ready', label: 'Satellite: pipeline defined — real imagery pending', color: '#f59e0b' },
  shoreline_history: { status: 'synthetic',      label: 'Shoreline: Illustrative scenario',      color: '#8b5cf6' },
  terrain:           { status: 'synthetic',      label: 'Terrain: Illustrative scenario',  color: '#10b981' },
  rainfall_weather:  { status: 'synthetic',      label: 'Rainfall/Weather: Illustrative scenario',      color: '#3b82f6' },
  ocean_conditions:  { status: 'synthetic',      label: 'Ocean: Illustrative scenario', color: '#06b6d4' },
};

export default function StatusBar({ activeSection }) {
  const sec = SECTIONS.find(s => s.id === activeSection);
  if (!sec) return null;

  const domainKey = sec.domain === 'all' ? 'shoreline_history' : sec.domain;
  const domainInfo = DOMAIN_STATUS[domainKey];

  return (
    <div className="status-bar">
      <span className="status-dot" style={{ background: domainInfo?.color }} />
      <span className="status-text">{domainInfo?.label}</span>
      <span className="status-separator">|</span>
      <span className="status-text" style={{ color: '#ef4444', fontSize: '0.72rem' }}>
        ⚠ Not real measured data — testing/demonstration only
      </span>
    </div>
  );
}
