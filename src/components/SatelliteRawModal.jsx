import React, { useState, useEffect } from 'react';

export default function SatelliteRawModal({ onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRawData = async () => {
      try {
        const response = await fetch('/satellite/raw');
        if (!response.ok) {
          throw new Error('Raw satellite imagery unavailable');
        }
        const metadata = await response.json();
        setData(metadata);
      } catch (err) {
        setError('Live satellite imagery unavailable. Run the pipeline first.');
      } finally {
        setLoading(false);
      }
    };
    fetchRawData();
  }, []);

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (loading) {
    return (
      <div style={overlayStyle}>
        <div style={modalStyle}>
          <div style={headerStyle}>
            <h3>SATELLITE IMAGERY — RAW INPUT</h3>
            <button style={closeBtnStyle} onClick={onClose}>&times;</button>
          </div>
          <div style={{ padding: '20px', textAlign: 'center' }}>Loading raw satellite imagery...</div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={overlayStyle}>
        <div style={modalStyle}>
          <div style={headerStyle}>
            <h3>SATELLITE IMAGERY — RAW INPUT</h3>
            <button style={closeBtnStyle} onClick={onClose}>&times;</button>
          </div>
          <div style={{ padding: '20px', color: '#ef4444', textAlign: 'center' }}>{error || 'No data available'}</div>
        </div>
      </div>
    );
  }

  const isSynthetic = data.status === 'synthetic_fallback';

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div style={modalStyle} onClick={e => e.stopPropagation()}>
        <div style={headerStyle}>
          <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#38bdf8' }}>SATELLITE IMAGERY — RAW INPUT</h3>
          <button style={closeBtnStyle} onClick={onClose}>&times;</button>
        </div>
        
        <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}>
          
          <div style={{ position: 'relative', width: '100%', maxWidth: '600px', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', overflow: 'hidden' }}>
            <img 
              src={data.image_url} 
              alt="Raw Satellite Preview" 
              style={{ width: '100%', height: 'auto', display: 'block' }} 
            />
          </div>

          <div style={{ width: '100%', maxWidth: '600px', backgroundColor: 'rgba(255, 255, 255, 0.05)', padding: '15px', borderRadius: '8px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.9rem' }}>
              <div><strong>Source:</strong> {data.source}</div>
              <div><strong>Sensor:</strong> {data.sensor}</div>
              <div><strong>Scene ID:</strong> {data.scene_id}</div>
              <div><strong>Acquisition:</strong> {data.observation_date}</div>
              <div><strong>Cloud Cover:</strong> {data.cloud_cover}%</div>
              <div><strong>Study Area:</strong> Chennai–Mahabalipuram</div>
            </div>
            
            <div style={{ 
                marginTop: '15px', padding: '10px', borderRadius: '4px', fontWeight: 'bold', textAlign: 'center',
                backgroundColor: isSynthetic ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                color: isSynthetic ? '#f59e0b' : '#10b981',
                border: isSynthetic ? '1px solid #f59e0b' : '1px solid #10b981'
            }}>
              DATA STATUS: {isSynthetic ? 'SYNTHETIC FALLBACK — PIPELINE DEMONSTRATION' : 'REAL SATELLITE DATA'}
            </div>
            
            <div style={{ marginTop: '15px', fontSize: '0.75rem', color: '#94a3b8', textAlign: 'center' }}>
              Satellite-domain research basis: Chawalit et al. (2025)
            </div>
          </div>
          
        </div>
      </div>
    </div>
  );
}

const overlayStyle = {
  position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
  backgroundColor: 'rgba(0, 0, 0, 0.7)',
  display: 'flex', justifyContent: 'center', alignItems: 'center',
  zIndex: 9999, backdropFilter: 'blur(4px)'
};

const modalStyle = {
  backgroundColor: '#1e293b',
  border: '1px solid #334155',
  borderRadius: '8px',
  width: '90%',
  maxWidth: '700px',
  maxHeight: '90vh',
  overflowY: 'auto',
  boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
  color: 'white'
};

const headerStyle = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '15px 20px', borderBottom: '1px solid #334155', backgroundColor: '#0f172a'
};

const closeBtnStyle = {
  background: 'transparent', border: 'none', color: '#94a3b8',
  cursor: 'pointer', fontSize: '1.5rem', lineHeight: 1
};
