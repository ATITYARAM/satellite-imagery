import React, { useEffect, useState } from 'react';
import { Palette, Satellite, BarChart3, RefreshCw, AlertTriangle, TreePine, Target } from 'lucide-react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

function getRequestedSection() {
  const requested = new URLSearchParams(window.location.search).get('section') || 'satellite';
  return SECTIONS.some((section) => section.id === requested) ? requested : 'satellite';
}

function SatelliteLatestView() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    fetch('/satellite/data')
      .then(async (response) => {
        const contentType = response.headers.get('content-type') || '';
        const body = await response.text();
        if (!response.ok) {
          throw new Error(`Satellite API returned HTTP ${response.status}: ${body || response.statusText}`);
        }
        if (!contentType.includes('application/json')) {
          throw new Error('Satellite API returned a non-JSON response. Start the project with npm run dev so Vite can proxy requests to FastAPI.');
        }
        try {
          return JSON.parse(body);
        } catch {
          throw new Error('Satellite API returned invalid JSON. Start the project with npm run dev and check the FastAPI server.');
        }
      })
      .then((value) => {
        if (!cancelled) setData(value);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load satellite data');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const latest = data?.years?.['2025'];
  const acquisitionDate = latest?.acquisition_datetime
    ? new Intl.DateTimeFormat('en-GB', { dateStyle: 'long', timeZone: 'UTC' }).format(new Date(latest.acquisition_datetime))
    : null;

  return (
    <main className="xgboost-satellite-split satellite-latest-view" aria-label="Latest satellite imagery">
      {loading ? (
        <section className="split-side satellite-latest-image">
          <div className="satellite-unavailable">
            <strong>Loading latest 2025 satellite imagery…</strong>
            <span>Checking the cached Landsat scene for the configured Thiruvananthapuram study area.</span>
          </div>
        </section>
      ) : latest?.available ? (
        <section className="split-side satellite-latest-image" style={{ gridColumn: "1 / -1" }}>
          <img src={latest.color_preview_url} alt="Latest 2025 satellite imagery of the study area" />
          <div className="satellite-year-label">
            <strong>2025</strong>
            <span>{acquisitionDate || 'Acquisition date unavailable'} · {latest.source || 'Source unavailable'}</span>
            <span>{latest.platform || 'Platform unavailable'} · {latest.scene_id || 'Scene ID unavailable'} · {latest.cloud_cover_percent ?? 'Unknown'}% cloud cover</span>
          </div>
        </section>
      ) : (
        <section className="split-side satellite-latest-image">
          <div className="satellite-unavailable">
            <strong>{error ? 'Satellite data could not be loaded' : '2025 imagery is unavailable'}</strong>
            <span>{error || latest?.unavailable_reason || 'The 2025 imagery metadata or required bands are missing.'}</span>
            <span>Recovery: run <code>.venv/bin/python scripts/download_landsat_aoi.py --year 2025</code>, then refresh.</span>
          </div>
        </section>
      )}
    </main>
  );
}

function XGBoostSatelliteSplit() {
  const [panels, setPanels] = useState({
    2015: { loading: true, imageLoading: true },
    2025: { loading: true, imageLoading: true },
  });
  const [comparisonMode, setComparisonMode] = useState('side-by-side');
  const [swipePosition, setSwipePosition] = useState(50);

  useEffect(() => {
    let cancelled = false;
    [2015, 2025].forEach((year) => {
      fetch(`/satellite/archive-data/${year}`)
        .then(async (response) => {
          const body = await response.text();
          if (!response.ok) throw new Error(`HTTP ${response.status}: ${body}`);
          return JSON.parse(body);
        })
        .then((metadata) => {
          if (!cancelled) setPanels((old) => ({ ...old, [year]: { loading: false, imageLoading: true, metadata } }));
        })
        .catch((err) => {
          if (!cancelled) setPanels((old) => ({ ...old, [year]: { loading: false, error: err.message || 'Could not load scene metadata.' } }));
        });
    });
    return () => { cancelled = true; };
  }, []);

  const formatDate = (value) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'long', timeZone: 'UTC' }).format(new Date(value));
  const bothReady = [2015, 2025].every((year) => panels[year].metadata && !panels[year].error);
  const yearSpan = bothReady
    ? ((new Date(panels[2025].metadata.acquisition_datetime) - new Date(panels[2015].metadata.acquisition_datetime)) / 31557600000).toFixed(1)
    : '—';
  const limitation = bothReady && panels[2025].metadata.selection_note
    ? `Coverage substitution: ${panels[2025].metadata.selection_note} Original last-selected scene ${panels[2025].metadata.original_last_selected_item_id} had ${panels[2025].metadata.original_last_selected_coverage_percent}% valid RGB coverage. Reported cloud cover for the displayed 2025 scene is ${panels[2025].metadata.cloud_cover_percent}%; visible clouds further limit interpretation.`
    : 'Transparent areas are nodata, not water or land. Clouds and scene conditions can limit visual interpretation.';

  const image = (year, className = '') => (
    <img
      className={className}
      src={panels[year].metadata.image_url}
      alt={`${year} satellite image for the Thiruvananthapuram study area`}
      onLoad={() => setPanels((old) => ({ ...old, [year]: { ...old[year], imageLoading: false } }))}
      onError={() => setPanels((old) => ({ ...old, [year]: { ...old[year], imageLoading: false, error: 'The image endpoint failed. Confirm the RGB bands are available and FastAPI is running.' } }))}
    />
  );

  return (
    <main className="comparison-page" aria-label="2015 and 2025 satellite comparison">
      <header className="comparison-header">
        <div>
          <span className="comparison-eyebrow">XGBOOST INPUT COMPARISON</span>
          <h1>Satellite observations</h1>
          <p>Compare the first selected 2015 observation with the coverage-qualified 2025 observation. This is a visual input review, not a shoreline-erosion measurement.</p>
        </div>
        <div className="comparison-controls" aria-label="Comparison view">
          <button type="button" className={comparisonMode === 'side-by-side' ? 'active' : ''} onClick={() => setComparisonMode('side-by-side')}>Side-by-side</button>
          <button type="button" className={comparisonMode === 'swipe' ? 'active' : ''} onClick={() => setComparisonMode('swipe')} disabled={!bothReady}>Swipe comparison</button>
        </div>
      </header>

      {bothReady && (
        <section className="comparison-info" aria-label="Comparison information">
          {[2015, 2025].map((year) => <div key={year}><b>{year}</b><span>{formatDate(panels[year].metadata.acquisition_datetime)}</span><code>{panels[year].metadata.item_id}</code><small>{panels[year].metadata.valid_pixel_coverage_percent}% valid RGB</small></div>)}
          <div><b>INTERVAL</b><span>{yearSpan} years</span><small>Common RGB scaling; nodata is transparent.</small></div>
          <p role="note">{limitation}</p>
        </section>
      )}

      {comparisonMode === 'swipe' && bothReady ? (
        <section className="swipe-comparison" aria-label="Swipe satellite comparison">
          <div className="swipe-stage">
            {image(2015, 'swipe-image')}
            <div className="swipe-overlay" style={{ clipPath: `inset(0 ${100 - swipePosition}% 0 0)` }}>{image(2025, 'swipe-image')}</div>
            <div className="swipe-divider" style={{ left: `${swipePosition}%` }} aria-hidden="true"><span>↔</span></div>
            <span className="swipe-label swipe-label-left">2025</span><span className="swipe-label swipe-label-right">2015</span>
          </div>
          <label className="swipe-range">Reveal 2025 imagery
            <input type="range" min="0" max="100" value={swipePosition} onChange={(event) => setSwipePosition(Number(event.target.value))} aria-valuetext={`${swipePosition}% 2025 imagery revealed`} />
          </label>
          <p>Drag the divider or use the arrow keys on the slider. Both dates use identical image bounds and display scaling.</p>
        </section>
      ) : (
        <section className="comparison-panels" aria-label="Side-by-side satellite imagery">
          {[2015, 2025].map((year) => (
            <article className="comparison-panel" key={year}>
              <header><strong>{year}</strong><span>{panels[year].metadata ? `${year === 2015 ? 'First' : 'Coverage-qualified'} selected observation · ${formatDate(panels[year].metadata.acquisition_datetime)}` : 'Loading selected observation…'}</span></header>
              {panels[year].loading ? <div className="satellite-unavailable"><strong>Loading {year} satellite image…</strong><span>Checking the cached selected scene.</span></div>
                : panels[year].error ? <div className="satellite-unavailable"><strong>{year} satellite image could not load</strong><span>{panels[year].error}</span></div>
                  : <div className="comparison-image-frame">{image(year)}{panels[year].imageLoading && <div className="archive-image-loading">Loading image…</div>}<span className="nodata-key">▧ Transparent = nodata</span></div>}
              {panels[year].metadata && <footer><span>{panels[year].metadata.platform} · {panels[year].metadata.collection}</span><code>{panels[year].metadata.item_id}</code><span>{panels[year].metadata.valid_pixel_coverage_percent}% valid RGB coverage</span></footer>}
            </article>
          ))}
        </section>
      )}
      <aside className="comparison-legend"><b>How to read this</b><span>Natural-color Landsat RGB is stretched with shared 2nd–98th percentile ranges calculated from valid pixels in both dates. Transparent/neutral regions are unavailable data; visual differences are not measured coastal erosion.</span></aside>
    </main>
  );
}

function ResultView() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const runModel = async (force = false) => {
    setLoading(true);
    setError('');
    try {
      const response = await fetch('/xgboost/result' + (force ? '?force=true' : ''));
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
          <p>2015 → 2025 coastal change analysis using Landsat observations at five-year intervals (2015, 2020, 2025).</p>
        </div>
        <button type="button" className="result-refresh" onClick={() => runModel(true)} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Running…' : 'Run XGBoost'}
        </button>
      </header>

      {loading ? (
        <section className="result-loading">
          <RefreshCw size={26} className="spin" />
          <strong>Running XGBoost on the 2015, 2020 and 2025 satellite observations…</strong>
          <span>Building paired spectral features and generating the output layer.</span>
        </section>
      ) : error ? (
        <section className="result-error">
          <AlertTriangle size={24} />
          <div>
            <strong>XGBoost result could not be generated</strong>
            <span>{error}</span>
            <small>Make sure the FastAPI backend is running and the 2015, 2020 and 2025 band files are available.</small>
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
                  alt="XGBoost coastal change score generated from 2015, 2020 and 2025 satellite imagery"
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
                <div><span>INPUT YEARS</span><b>2015 + 2020 + 2025</b></div>
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
            Prototype note: the model uses 2015, 2020 and 2025 imagery, including five-year interval features. Without erosion ground-truth labels, its output is a spectral-change proxy, not a validated erosion measurement or the final five-domain model.
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

  if (activeSection === 'satellite') {
    return (
      <div className="app-container">
        <Sidebar
          activeSection={activeSection}
          onSelect={selectSection}
          onSatelliteDoubleClick={openSatelliteData}
        />
        <SatelliteLatestView />
      </div>
    );
  }

  if (activeSection === 'prediction') {
    return (
      <div className="app-container">
        <Sidebar
          activeSection={activeSection}
          onSelect={selectSection}
          onSatelliteDoubleClick={openSatelliteData}
        />
        <XGBoostSatelliteSplit />
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
