import React, { useEffect, useState } from 'react';
import { Palette, Satellite } from 'lucide-react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

function XGBoostSatelliteSplit({ onToggleView, colorView }) {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/satellite/data')
      .then((response) => {
        if (!response.ok) throw new Error('Satellite data unavailable');
        return response.json();
      })
      .then((value) => {
        if (!cancelled) setData(value);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const left = data?.years?.['2016'];
  const right = data?.years?.['2026'];

  return (
    <main className="xgboost-satellite-split" aria-label="Raw satellite imagery comparison">
      <button
        type="button"
        className="xgboost-view-toggle"
        onClick={onToggleView}
        title={colorView ? "Show raw satellite split" : "Show color satellite split"}
        aria-label={colorView ? "Show raw satellite split" : "Show color satellite split"}
      >
        {colorView ? <Satellite size={19} /> : <Palette size={19} />}
      </button>

      <section className="split-side split-side-left">
        {left?.available ? <img src={colorView ? left.color_preview_url : left.preview_url} alt={colorView ? "2016 color satellite imagery" : "2016 raw satellite imagery"} /> : null}
      </section>
      <section className="split-side split-side-right">
        {right?.available ? <img src={colorView ? right.color_preview_url : right.preview_url} alt={colorView ? "2026 color satellite imagery" : "2026 raw satellite imagery"} /> : null}
      </section>
    </main>
  );
}

export default function App() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get('section') || 'prediction';
  const activeSection = SECTIONS.some((section) => section.id === requested)
    ? requested
    : 'prediction';

  const [satelliteDataOpen, setSatelliteDataOpen] = useState(false);
  const [xgboostColorView, setXgboostColorView] = useState(false);

  const selectSection = (sectionId) => {
    window.history.pushState({}, '', '?section=' + sectionId);
    window.dispatchEvent(new PopStateEvent('popstate'));
    if (sectionId !== 'satellite') setSatelliteDataOpen(false);
  };

  const openSatelliteData = () => {
    selectSection('satellite');
    setSatelliteDataOpen(true);
  };

  useEffect(() => {
    const close = () => setSatelliteDataOpen(false);
    window.addEventListener('close-satellite-data', close);
    return () => window.removeEventListener('close-satellite-data', close);
  }, []);

  if (activeSection === 'prediction') {
    return (
      <div className="app-container">
        <Sidebar
          activeSection={activeSection}
          onSelect={selectSection}
          onSatelliteDoubleClick={openSatelliteData}
        />

        <XGBoostSatelliteSplit
          colorView={xgboostColorView}
          onToggleView={() => setXgboostColorView((value) => !value)}
        />
      </div>
    );
  }

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
