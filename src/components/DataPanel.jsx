import React, { useState } from 'react';
import { ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

function StatRow({ label, value, unit = '' }) {
  return (
    <div className="stat-row">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value != null ? `${value}${unit ? ' ' + unit : ''}` : '—'}</span>
    </div>
  );
}

export default function DataPanel({ activeSection, data }) {
  const [open, setOpen] = useState(true);

  if (!data) return null;

  const renderContent = () => {
    if (activeSection === 'rainfall') {
      const recs = data.records || [];
      const latest = recs.at(-1);
      const total = recs.reduce((s, r) => s + (r.rainfall_mm_per_day || 0), 0);
      const max30 = Math.max(...recs.map(r => r.accum_30d_mm || 0));
      return (
        <>
          <StatRow label="Latest daily rainfall" value={latest?.rainfall_mm_per_day} unit="mm/day" />
          <StatRow label="30-day accumulated" value={total.toFixed(1)} unit="mm" />
          <StatRow label="Max 30d window" value={max30.toFixed(1)} unit="mm" />
          <StatRow label="Records loaded" value={recs.length} />
        </>
      );
    }
    if (activeSection === 'weather') {
      const latest = data.records?.at(-1);
      return (
        <>
          <StatRow label="Wind speed" value={latest?.wind_speed_kmh} unit="km/h" />
          <StatRow label="Wind direction" value={latest?.wind_dir_deg} unit="°" />
          <StatRow label="Temperature" value={latest?.temp_c} unit="°C" />
          <StatRow label="Pressure" value={latest?.pressure_hpa} unit="hPa" />
        </>
      );
    }
    if (activeSection === 'terrain') {
      const recs = data.records || [];
      const elevs = recs.map(r => r.elevation_m);
      const minE = Math.min(...elevs).toFixed(1);
      const maxE = Math.max(...elevs).toFixed(1);
      const avgE = (elevs.reduce((s, v) => s + v, 0) / elevs.length).toFixed(1);
      const avgS = (recs.reduce((s, r) => s + (r.slope_deg || 0), 0) / recs.length).toFixed(2);
      return (
        <>
          <StatRow label="Elevation range" value={`${minE}–${maxE}`} unit="m" />
          <StatRow label="Mean elevation" value={avgE} unit="m" />
          <StatRow label="Mean slope" value={avgS} unit="°" />
          <StatRow label="Sample cells shown" value={recs.length} />
        </>
      );
    }
    if (activeSection === 'ocean') {
      const recs = data.records || [];
      const latest = recs.at(-1);
      const maxHs = Math.max(...recs.map(r => r.Hs_m || 0)).toFixed(2);
      const storms = recs.filter(r => r.storm_surge_flag).length;
      return (
        <>
          <StatRow label="Latest Hs" value={latest?.Hs_m} unit="m" />
          <StatRow label="Latest Tp" value={latest?.Tp_s} unit="s" />
          <StatRow label="Max Hs (7d)" value={maxHs} unit="m" />
          <StatRow label="Tide level" value={latest?.tide_level_m} unit="m" />
          <StatRow label="Storm events (7d)" value={storms} />
        </>
      );
    }
    if (activeSection === 'history') {
      const recs = data.records || [];
      const retreating = recs.filter(r => r.total_displacement_m < 0).length;
      const avgRate = recs.length
        ? (recs.reduce((s, r) => s + (r.avg_rate_m_yr || 0), 0) / recs.length).toFixed(3)
        : '—';
      return (
        <>
          <StatRow label="Transects loaded" value={recs.length} />
          <StatRow label="Retreating transects" value={retreating} />
          <StatRow label="Mean rate" value={avgRate} unit="m/yr" />
          <StatRow label="Scenario" value="erosion" />
        </>
      );
    }
    if (activeSection === 'prediction') {
      return (
        <>
          <StatRow label="Shoreline transects" value={data.shoreline?.length ?? '—'} />
          <StatRow label="Ocean records" value={data.ocean?.length ?? '—'} />
          <StatRow label="Rainfall records" value={data.rainfall?.length ?? '—'} />
          <StatRow label="Model" value="XGBoost (demo)" />
        </>
      );
    }
    return null;
  };

  return (
    <div className="data-panel">
      <div className="data-panel-header" onClick={() => setOpen(o => !o)}>
        <span>Domain Summary</span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </div>
      {open && (
        <div className="data-panel-body">
          <div className="synthetic-notice">
            <AlertTriangle size={12} />
            <span>SYNTHETIC DATA — testing only</span>
          </div>
          {renderContent()}
        </div>
      )}
    </div>
  );
}
