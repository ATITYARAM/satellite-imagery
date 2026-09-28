import React from 'react';

export default function StatusPanel({ status, onRefresh, onRun, metrics }) {
  return (
    <div style={{
      position: 'absolute', top: '20px', right: '20px', zIndex: 1000,
      backgroundColor: 'rgba(15, 23, 42, 0.9)', padding: '15px',
      borderRadius: '8px', color: 'white', backdropFilter: 'blur(8px)',
      boxShadow: '0 4px 6px rgba(0,0,0,0.3)', width: '300px', fontSize: '0.85rem'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h3 style={{ margin: 0, fontSize: '1rem', color: '#3b82f6' }}>Project Status</h3>
        <button onClick={onRefresh} style={{ backgroundColor: 'transparent', color: '#3b82f6', border: '1px solid #3b82f6', borderRadius: '4px', padding: '2px 8px', cursor: 'pointer', fontSize: '0.75rem' }}>Refresh</button>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span>Backend:</span> <span style={{ color: status === 'DISCONNECTED' ? '#ef4444' : '#10b981' }}>{status === 'DISCONNECTED' ? 'DISCONNECTED' : 'CONNECTED'}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span>Dataset:</span> <span style={{ color: '#f59e0b' }}>SYNTHETIC</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
          <span>Pipeline:</span> <span>{status}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <span>Model:</span> <span>RF + XGBoost</span>
        </div>
      </div>

      <button 
        onClick={onRun} 
        disabled={status === 'Running'}
        style={{ 
          width: '100%', backgroundColor: status === 'Running' ? '#475569' : '#ef4444', 
          color: 'white', border: 'none', padding: '8px', borderRadius: '4px', 
          cursor: status === 'Running' ? 'not-allowed' : 'pointer', fontWeight: 'bold' 
        }}
      >
        {status === 'Running' ? 'Running...' : 'RUN PIPELINE'}
      </button>

      {metrics && metrics.XGBoost && (
        <div style={{ marginTop: '15px', borderTop: '1px solid #334155', paddingTop: '10px' }}>
          <div style={{ fontWeight: 'bold', marginBottom: '5px', color: '#94a3b8' }}>Synthetic Demonstration Metrics (XGB)</div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>R²:</span> <span>{metrics.XGBoost.R2.toFixed(4)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>MAE:</span> <span>{metrics.XGBoost.MAE.toFixed(4)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>RMSE:</span> <span>{metrics.XGBoost.RMSE.toFixed(4)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
