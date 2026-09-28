import React, { useState } from 'react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('section') || 'prediction';
  const activeSection = SECTIONS.some((section) => section.id === requested)
    ? requested
    : 'prediction';

  const [satelliteDataOpen, setSatelliteDataOpen] = useState(false);

  const selectSection = (sectionId) => {
    window.history.pushState({}, '', '?section=' + sectionId);
    window.dispatchEvent(new PopStateEvent('popstate'));
    if (sectionId !== 'satellite') setSatelliteDataOpen(false);
  };

  const openSatelliteData = () => {
    selectSection('satellite');
    setSatelliteDataOpen(true);
  };

  React.useEffect(() => {
    const close = () => setSatelliteDataOpen(false);
    window.addEventListener('close-satellite-data', close);
    return () => window.removeEventListener('close-satellite-data', close);
  }, []);

  return (
    <div className="app-container">
      <Sidebar
        activeSection={activeSection}
        onSelect={selectSection}
        onSatelliteDoubleClick={openSatelliteData}
      />
      <MapView activeSection={activeSection} satelliteDataOpen={satelliteDataOpen} />
    </div>
  );
}
