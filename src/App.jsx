import React, { useEffect, useState } from 'react';
import { Map, Satellite } from 'lucide-react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

function XGBoostSatelliteSplit({ onToggleView }) {
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
        title="Show map view"
        aria-label="Show map view"
      >
        <Map size={19} />
      </button>

      <section className="split-side split-side-left">
        {left?.available ? <img src={left.preview_url} alt="2016 raw satellite imagery" /> : null}
      </section>
      <section className="split-side split-side-right">
        {right?.available ? <img src={right.preview_url} alt="2026 raw satellite imagery" /> : null}
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
  const [xgboostSplitView, setXgboostSplitView] = useState(true);

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

        {xgboostSplitView ? (
          <XGBoostSatelliteSplit onToggleView={() => setXgboostSplitView(false)} />
        ) : (
          <main className="xgboost-map-view">
            <button
              type="button"
              className="xgboost-view-toggle"
              onClick={() => setXgboostSplitView(true)}
              title="Show raw satellite comparison"
              aria-label="Show raw satellite comparison"
            >
              <Satellite size={19} />
            </button>
            <MapView activeSection={activeSection} satelliteDataOpen={false} />
          </main>
        )}
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
