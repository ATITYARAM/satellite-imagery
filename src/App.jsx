import React from 'react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

export default function App() {
  // Read section ID from URL query param (e.g. ?section=terrain), default to 'prediction'
  const queryParams = new URLSearchParams(window.location.search);
  const activeSection = queryParams.get('section') || 'prediction';

  return (
    <div className="app-container">
      <Sidebar activeSection={activeSection} />
      <MapView activeSection={activeSection} />
    </div>
  );
}