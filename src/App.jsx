// src/App.jsx
import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import MapView from './components/MapView';

export default function App() {
  const [activeLayers, setActiveLayers] = useState({
    rainfall: false,
    terrain: false,
    weather: false,
    ocean: false,
    history: true,
    prediction: true // Set AI Prediction active by default for 30% prototype demo
  });

  const toggleLayer = (id) => {
    setActiveLayers((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  return (
    <div className="app-container">
      <Sidebar activeLayers={activeLayers} toggleLayer={toggleLayer} />
      <MapView activeLayers={activeLayers} />
    </div>
  );
}