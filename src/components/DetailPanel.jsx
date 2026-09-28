import React, { useEffect, useState } from 'react';

function fmt(value, digits = 3) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : 'N/A';
}

export default function DetailPanel({ segment, section, onClose }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    const loadDetails = async () => {
      try {
        const endpoint = section === 'satellite'
          ? '/satellite/output'
          : '/priority-zones';
        const response = await fetch(endpoint);
        const payload = await response.json();
        const rows = section === 'satellite' ? payload : payload;
        const segData = Array.isArray(rows)
          ? rows.find((row) => row.segment_id === segment)
          : null;
        setData(segData || null);
      } catch (e) {
        console.error(e);
        setData(null);
      }
    };
    loadDetails();
  }, [segment, section]);

  return (
    <div style={{
      position: 'absolute', bottom: '20px', right: '20px', zIndex: 1000,
      backgroundColor: 'rgba(15, 23, 42, 0.96)', padding: '20px',
      borderRadius: '8px', color: 'white', backdropFilter: 'blur(8px)',
      boxShadow: '0 4px 12px rgba(0,0,0,0.5)', width: '360px',
      fontSize: '0.85rem', maxHeight: '68vh', overflowY: 'auto'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '15px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', color: section === 'satellite' ? '#38bdf8' : '#3b82f6' }}>
          {section === 'satellite' ? 'Satellite Segment' : 'Segment Details'}
        </h3>
        <button onClick={onClose} style={{
          background: 'transparent', border: 'none', color: '#94a3b8',
          cursor: 'pointer', fontSize: '1.2rem'
        }}>&times;</button>
      </div>

      {data ? (
        <div>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '1.2rem' }}>{segment}</h4>

          {section === 'satellite' ? (
            <div>
              <div style={{ marginBottom: '12px', padding: '10px', backgroundColor: 'rgba(56,189,248,0.08)', borderRadius: '6px' }}>
                <div><strong>Observation:</strong> {data.observation_date || 'N/A'}</div>
                <div><strong>Sensor:</strong> {data.sensor || 'N/A'}</div>
                <div><strong>Source:</strong> {data.source || 'N/A'}</div>
                <div><strong>Scene:</strong> {data.scene_id || 'N/A'}</div>
                <div><strong>Quality:</strong> {data.quality_flag || 'N/A'}</div>
              </div>

              <div style={{ color: '#cbd5e1' }}>
                <strong>Paper-aligned satellite features</strong>
                <div style={{ marginTop: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  <span>Blue: {fmt(data.blue)}</span>
                  <span>Green: {fmt(data.green)}</span>
                  <span>Red: {fmt(data.red)}</span>
                  <span>NIR: {fmt(data.nir)}</span>
                  <span>SWIR1: {fmt(data.swir1)}</span>
                  <span>SWIR2: {fmt(data.swir2)}</span>
                  <span>NDVI: {fmt(data.ndvi)}</span>
                  <span>NDWI: {fmt(data.ndwi)}</span>
                  <span>MNDWI: {fmt(data.mndwi)}</span>
                  <span>SAVI: {fmt(data.savi)}</span>
                  <span>Water probability: {fmt(data.water_probability, 2)}</span>
                  <span>Class: {data.land_water_class || 'N/A'}</span>
                </div>
              </div>

              <div style={{ marginTop: '12px', color: '#f59e0b', fontStyle: 'italic' }}>
                Source mode: {data.source_mode}. Live mode uses public Landsat data;
                synthetic fallback is used only when live acquisition is unavailable.
              </div>
            </div>
          ) : (
            <div>
              <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px' }}>
                <div><strong>Prediction:</strong> {fmt(data.predicted_change)} m</div>
                <div>
                  <strong>Priority:</strong>
                  <span style={{
                    marginLeft: '8px', padding: '2px 6px', borderRadius: '4px',
                    fontSize: '0.75rem', fontWeight: 'bold',
                    backgroundColor: data.priority_class === 'High' ? '#ef4444'
                      : data.priority_class === 'Medium' ? '#f59e0b' : '#10b981'
                  }}>
                    {data.priority_class}
                  </span>
                </div>
              </div>
              <div style={{ color: '#cbd5e1' }}>
                <strong>Five data domains</strong>
                <ul style={{ paddingLeft: '20px', margin: '5px 0' }}>
                  <li>Satellite</li>
                  <li>Shoreline History</li>
                  <li>Terrain</li>
                  <li>Rainfall / Weather</li>
                  <li>Ocean Conditions</li>
                </ul>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div style={{ color: '#94a3b8' }}>
          No segment output is available yet. Run the {section === 'satellite' ? 'satellite' : 'main'} pipeline first.
        </div>
      )}
    </div>
  );
}
