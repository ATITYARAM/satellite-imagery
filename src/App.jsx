import React from 'react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('section') || 'prediction';
  const activeSection = SECTIONS.some((section) => section.id === requested)
    ? requested
    : 'prediction';

  const selectSection = (sectionId) => {
    window.history.pushState({}, '', '?section=' + sectionId);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  return (
    <div className="app-container">
      <Sidebar activeSection={activeSection} onSelect={selectSection} />
      <MapView activeSection={activeSection} />
    </div>
  );
}