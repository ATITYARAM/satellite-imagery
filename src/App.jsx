import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import StatusPanel from './components/StatusPanel';
import DetailPanel from './components/DetailPanel';

export default function App() {
  const queryParams = new URLSearchParams(window.location.search);
  const initialSection = queryParams.get('section') || 'prediction';
  const [activeSection, setActiveSection] = useState(initialSection);
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('Checking...');
  const [refreshCount, setRefreshCount] = useState(0);

  const handleSectionSelect = (sectionId) => {
    setActiveSection(sectionId);
    window.history.pushState({}, '', `?section=${sectionId}`);
  };

  const loadData = async () => {
    try {
      const mapRes = await fetch('/map-data');
      if(mapRes.ok) setMapData(await mapRes.json());
      
      const metricsRes = await fetch('/metrics');
      if(metricsRes.ok) setMetrics(await metricsRes.json());
      
      const statusRes = await fetch('/pipeline-status');
      if(statusRes.ok) {
        const data = await statusRes.json();
        setPipelineStatus(data.status);
      }
    } catch (e) {
      console.error(e);
      setPipelineStatus('DISCONNECTED');
    }
  };

  useEffect(() => {
    loadData();
  }, [refreshCount]);

  const refreshData = () => {
    setRefreshCount(c => c + 1);
  };

  const runPipeline = async () => {
    setPipelineStatus('Running');
    try {
        await fetch('/pipeline/run', { method: 'POST' });
        setTimeout(() => refreshData(), 2000);
    } catch (e) {
        setPipelineStatus('Failed');
    }
  };

  return (
    <div className="app-container">
      <Sidebar activeSection={activeSection} onSelect={handleSectionSelect} />
      <div style={{ position: 'relative', flex: 1, height: '100vh', overflow: 'hidden' }}>
        <MapView 
            activeSection={activeSection} 
            mapData={mapData} 
            onSegmentSelect={setSelectedSegment} 
        />
        <StatusPanel 
            status={pipelineStatus} 
            onRefresh={refreshData} 
            onRun={runPipeline} 
            metrics={metrics}
        />
        {selectedSegment && (
            <DetailPanel 
                segment={selectedSegment} 
                onClose={() => setSelectedSegment(null)} 
            />
        )}
      </div>
    </div>
  );
}