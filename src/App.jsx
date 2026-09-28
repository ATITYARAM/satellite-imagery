import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';
import StatusPanel from './components/StatusPanel';
import DetailPanel from './components/DetailPanel';
import SatelliteRawModal from './components/SatelliteRawModal';

export default function App() {
  const queryParams = new URLSearchParams(window.location.search);
  const initialSection = queryParams.get('section') || 'prediction';

  const [activeSection, setActiveSection] = useState(initialSection);
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [mapData, setMapData] = useState(null);
  const [satelliteMapData, setSatelliteMapData] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState('Checking...');
  const [satelliteStatus, setSatelliteStatus] = useState('Checking...');
  const [refreshCount, setRefreshCount] = useState(0);
  const [showRawSatelliteModal, setShowRawSatelliteModal] = useState(false);

  useEffect(() => {
    window.onSatelliteDoubleClick = () => setShowRawSatelliteModal(true);
  }, []);

  const handleSectionSelect = (sectionId) => {
    setActiveSection(sectionId);
    setSelectedSegment(null);
    window.history.pushState({}, '', `?section=${sectionId}`);
  };

  const loadData = async () => {
    try {
      const [mapRes, metricsRes, statusRes, satMapRes, satStatusRes] = await Promise.all([
        fetch('/map-data'),
        fetch('/metrics'),
        fetch('/pipeline-status'),
        fetch('/satellite-map'),
        fetch('/satellite/status'),
      ]);

      if (mapRes.ok) setMapData(await mapRes.json());
      if (metricsRes.ok) setMetrics(await metricsRes.json());
      if (statusRes.ok) setPipelineStatus((await statusRes.json()).status);
      if (satMapRes.ok) setSatelliteMapData(await satMapRes.json());
      if (satStatusRes.ok) setSatelliteStatus((await satStatusRes.json()).status);
    } catch (e) {
      console.error(e);
      setPipelineStatus('DISCONNECTED');
      setSatelliteStatus('DISCONNECTED');
    }
  };

  useEffect(() => {
    loadData();
  }, [refreshCount]);

  const refreshData = () => setRefreshCount((c) => c + 1);

  const runPipeline = async () => {
    setPipelineStatus('Running');
    try {
      const response = await fetch('/pipeline/run', { method: 'POST' });
      if (!response.ok) throw new Error('Pipeline request failed');
      const poll = setInterval(async () => {
        const statusRes = await fetch('/pipeline-status');
        if (!statusRes.ok) return;
        const status = (await statusRes.json()).status;
        setPipelineStatus(status);
        if (status !== 'Running') {
          clearInterval(poll);
          refreshData();
        }
      }, 1500);
    } catch (e) {
      console.error(e);
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
          satelliteMapData={satelliteMapData}
          onSegmentSelect={setSelectedSegment}
        />
        <StatusPanel
          status={activeSection === 'satellite' ? satelliteStatus : pipelineStatus}
          onRefresh={refreshData}
          onRun={activeSection === 'satellite'
            ? async () => {
                setSatelliteStatus('Running');
                try {
                  const response = await fetch('/satellite/run', { method: 'POST' });
                  if (!response.ok) throw new Error('Satellite pipeline request failed');
                  const poll = setInterval(async () => {
                    const statusRes = await fetch('/satellite/status');
                    if (!statusRes.ok) return;
                    const status = (await statusRes.json()).status;
                    setSatelliteStatus(status);
                    if (status !== 'Running') {
                      clearInterval(poll);
                      refreshData();
                    }
                  }, 1500);
                } catch (e) {
                  console.error(e);
                  setSatelliteStatus('Failed');
                }
              } : runPipeline}
          metrics={metrics}
          activeSection={activeSection}
        />
        {selectedSegment && (
          <DetailPanel
            segment={selectedSegment}
            section={activeSection}
            onClose={() => setSelectedSegment(null)}
          />
        )}
        {showRawSatelliteModal && (
          <SatelliteRawModal onClose={() => setShowRawSatelliteModal(false)} />
        )}
      </div>
    </div>
  );
}
