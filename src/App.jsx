import React, { useEffect, useState } from 'react';
import { Palette, Satellite, BarChart3, RefreshCw, AlertTriangle, TreePine, Target } from 'lucide-react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

function getRequestedSection() {
  const requested = new URLSearchParams(window.location.search).get('section') || 'prediction';
  return SECTIONS.some((section) => section.id === requested) ? requested : 'prediction';
}

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
        title={colorView ? 'Show raw satellite split' : 'Show color satellite split'}
        aria-label={colorView ? 'Show raw satellite split' : 'Show color satellite split'}
      >
        {colorView ? <Satellite size={19} /> : <Palette size={19} />}
      </button>

      <section className="split-side split-side-left">
        {left?.available ? (
          <img
            src={colorView ? left.color_preview_url : left.preview_url}
            alt={colorView ? '2016 color satellite imagery' : '2016 raw satellite imagery'}
          />
        ) : null}
      </section>
      <section className="split-side split-side-right">
        {right?.available ? (
          <img
            src={colorView ? right.color_preview_url : right.preview_url}
            alt={colorView ? '2026 color satellite imagery' : '2026 raw satellite imagery'}
          />
        ) : null}
      </section>
    </main>
  );
}

function ResultView() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const runModel = async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/xgboost/result');
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || 'XGBoost result unavailable');
      }
      const value = await response.json();
      setResult(value);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Unable to run XGBoost.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runModel();
  }, []);

  return (
    <main className="result-page" aria-label="XGBoost result">
      <header className="result-header">
        <div>
          <div className="result-eyebrow"><BarChart3 size={16} /> MODEL OUTPUT</div>
          <h1>XGBoost Result</h1>
          <p>2016 → 2026 paired satellite-image prototype using the actual Landsat band data.</p>
        </div>
        <button type="button" className="result-refresh" onClick={runModel} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Running…' : 'Run XGBoost'}
        </button>
      </header>

      {loading ? (
        <section className="result-loading">
          <RefreshCw size={26} className="spin" />
          <strong>Running XGBoost on the two satellite observations…</strong>
          <span>Building paired spectral features and generating the output layer.</span>
        </section>
      ) : error ? (
        <section className="result-error">
          <AlertTriangle size={24} />
          <div>
            <strong>XGBoost result could not be generated</strong>
            <span>{error}</span>
            <small>Make sure the FastAPI backend is running and the 2016 / 2026 band files are available.</small>
          </div>
        </section>
      ) : (
        <>
          <section className="result-hero-grid">
            <article className="result-output-card">
              <div className="result-card-header">
                <div>
                  <span>OUTPUT LAYER</span>
                  <strong>XGBoost erosion-like change score</strong>
                </div>
                <span className="result-model-pill">XGBClassifier</span>
              </div>
              <div className="result-image-wrap">
                <img
                  src={result?.image_url ? result.image_url + '?v=' + result.run_id : ''}
                  alt="XGBoost erosion-like change score generated from 2016 and 2026 satellite imagery"
                />
                <div className="result-legend">
                  <span>Low</span>
                  <div className="result-gradient" />
                  <span>High</span>
                </div>
              </div>
            </article>

            <aside className="result-side-column">
              <article className="result-stat-card">
                <span>PIXELS ANALYZED</span>
                <strong>{Number(result?.pixels_analyzed || 0).toLocaleString()}</strong>
              </article>
              <article className="result-stat-card">
                <span>HIGH-SCORE AREA</span>
                <strong>{Number(result?.high_score_percent || 0).toFixed(1)}%</strong>
              </article>
              <article className="result-stat-card">
                <span>FEATURES</span>
                <strong>{result?.feature_count || 0}</strong>
              </article>
              <article className="result-stat-card">
                <span>BOOSTING TREES</span>
                <strong>{result?.n_estimators || 0}</strong>
              </article>
            </aside>
          </section>

          <section className="result-bottom-grid">
            <article className="result-panel">
              <div className="result-panel-title"><Target size={17} /> MODEL SETUP</div>
              <div className="result-detail-grid">
                <div><span>INPUT YEARS</span><b>2016 + 2026</b></div>
                <div><span>ALGORITHM</span><b>XGBoost gradient boosting</b></div>
                <div><span>TRAINING TARGET</span><b>Paired-image pseudo-label</b></div>
                <div><span>OUTPUT</span><b>Probability of erosion-like change</b></div>
              </div>
            </article>

            <article className="result-panel">
              <div className="result-panel-title"><TreePine size={17} /> TOP FEATURES</div>
              <div className="feature-list">
                {(result?.top_features || []).map((feature) => (
                  <div key={feature.name} className="feature-row">
                    <span>{feature.name}</span>
                    <div className="feature-track"><i style={{ width: Math.max(5, feature.importance * 100) + '%' }} /></div>
                    <b>{(feature.importance * 100).toFixed(1)}%</b>
                  </div>
                ))}
              </div>
            </article>
          </section>

          <div className="result-note">
            Prototype note: with only two dated images and no erosion ground-truth labels yet, the current XGBoost target is a paired-image change proxy. It is an actual XGBoost run, but it is not the final five-domain validated erosion model.
          </div>
        </>
      )}
    </main>
  );
}

export default function App() {
  const [activeSection, setActiveSection] = useState(getRequestedSection);
  const [satelliteDataOpen, setSatelliteDataOpen] = useState(false);
  const [xgboostColorView, setXgboostColorView] = useState(false);

  const selectSection = (sectionId) => {
    window.history.pushState({}, '', '?section=' + sectionId);
    setActiveSection(sectionId);
    if (sectionId !== 'satellite') setSatelliteDataOpen(false);
  };

  const openSatelliteData = () => {
    selectSection('satellite');
    setSatelliteDataOpen(true);
  };

  useEffect(() => {
    const handlePopState = () => {
      setActiveSection(getRequestedSection());
    };
    const close = () => setSatelliteDataOpen(false);
    window.addEventListener('popstate', handlePopState);
    window.addEventListener('close-satellite-data', close);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      window.removeEventListener('close-satellite-data', close);
    };
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

  if (activeSection === 'result') {
    return (
      <div className="app-container">
        <Sidebar
          activeSection={activeSection}
          onSelect={selectSection}
          onSatelliteDoubleClick={openSatelliteData}
        />
        <ResultView />
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
