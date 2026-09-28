import React, { useEffect, useState } from 'react';

export default function DetailPanel({ segment, onClose }) {
  const [data, setData] = useState(null);
  
  useEffect(() => {
    // In a real app, you would fetch details for this specific segment here.
    // For now we'll fetch the feature importance and priority zones to simulate detailed info.
    const loadDetails = async () => {
        try {
            const priorityRes = await fetch('/priority-zones');
            const zones = await priorityRes.json();
            const segData = zones.find(z => z.segment_id === segment);
            setData(segData);
        } catch (e) {
            console.error(e);
        }
    };
    loadDetails();
  }, [segment]);

  return (
    <div style={{
      position: 'absolute', bottom: '20px', right: '20px', zIndex: 1000,
      backgroundColor: 'rgba(15, 23, 42, 0.95)', padding: '20px',
      borderRadius: '8px', color: 'white', backdropFilter: 'blur(8px)',
      boxShadow: '0 4px 12px rgba(0,0,0,0.5)', width: '350px', fontSize: '0.85rem',
      maxHeight: '60vh', overflowY: 'auto'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', borderBottom: '1px solid #334155', paddingBottom: '10px' }}>
        <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#3b82f6' }}>Segment Details</h3>
        <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1.2rem' }}>&times;</button>
      </div>

      {data ? (
        <div>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '1.2rem' }}>{segment}</h4>
          
          <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px' }}>
            <div style={{ marginBottom: '5px' }}><strong>Prediction:</strong> {data.predicted_change ? data.predicted_change.toFixed(3) : 'N/A'} m</div>
            <div>
              <strong>Priority:</strong> 
              <span style={{ 
                  marginLeft: '8px', padding: '2px 6px', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 'bold',
                  backgroundColor: data.priority_class === 'High' ? '#ef4444' : (data.priority_class === 'Medium' ? '#f59e0b' : '#10b981')
              }}>
                {data.priority_class}
              </span>
            </div>
          </div>

          <div style={{ color: '#cbd5e1', marginBottom: '10px' }}>
            <strong>Data Domains</strong>
            <ul style={{ paddingLeft: '20px', margin: '5px 0' }}>
              <li>Satellite: NDVI, NDWI, SAVI</li>
              <li>Shoreline: Historical Change</li>
              <li>Terrain: Elevation, Slope</li>
              <li>Weather: Rainfall, Wind</li>
              <li>Ocean: Wave Height, Surge</li>
            </ul>
            <div style={{ color: '#f59e0b', fontStyle: 'italic', marginTop: '10px' }}>* Synthetic values generated via pipeline.</div>
          </div>
        </div>
      ) : (
        <div>Loading segment data...</div>
      )}
    </div>
  );
}
