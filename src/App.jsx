import React, { useEffect, useState } from 'react';
import { Palette, Satellite, BarChart3, RefreshCw, AlertTriangle, TreePine, Target } from 'lucide-react';
import Sidebar, { SECTIONS } from './components/Sidebar';
import MapView from './components/MapView';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');
const apiUrl = (path) => `${API_BASE_URL}${path}`;

async function fetchApiJson(path, options = {}) {
  const response = await fetch(apiUrl(path), options);
  const contentType = response.headers.get('content-type') || '';
  const body = await response.text();
  if (!response.ok) {
    let detail = body || response.statusText;
    if (contentType.includes('application/json') && body) {
      try { detail = JSON.parse(body).detail || detail; } catch { /* retain body */ }
    }
    throw new Error(`API ${response.status}: ${detail}`);
  }
  if (!contentType.includes('application/json')) {
    const hint = body.trimStart().startsWith('<!doctype') || body.trimStart().startsWith('<html')
      ? 'Received HTML instead of JSON. Check the Vite /forecast proxy or VITE_API_BASE_URL.'
      : 'Received a non-JSON response from the backend.';
    throw new Error(hint);
  }
  if (!body.trim()) throw new Error('Backend returned an empty JSON response.');
  try { return JSON.parse(body); } catch { throw new Error('Backend returned invalid JSON.'); }
}

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
  const [imageError, setImageError] = useState(false);
  const [forecastYear, setForecastYear] = useState(2026);
  const [forecast, setForecast] = useState(null);
  const [forecastLoading, setForecastLoading] = useState(true);
  const [forecastError, setForecastError] = useState('');
  const [forecastImageError, setForecastImageError] = useState(false);

  const runModel = async (force = false) => {
    setLoading(true);
    setError('');
    setImageError(false);
    try {
      setResult(await fetchApiJson(force ? '/xgboost/run?force=true' : '/xgboost/result', force ? { method: 'POST' } : {}));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Unable to run XGBoost.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { runModel(); }, []);

  const loadForecast = async (year, force = false) => {
    setForecastLoading(true); setForecastError(''); setForecastImageError(false);
    try {
      setForecast(await fetchApiJson(force ? `/forecast/${year}/run` : `/forecast/${year}`, force ? { method: 'POST' } : {}));
    } catch (err) {
      setForecast(null); setForecastError(err instanceof Error ? err.message : 'Forecast unavailable.');
    } finally { setForecastLoading(false); }
  };

  useEffect(() => { loadForecast(forecastYear); }, [forecastYear]);

  const domains = [
    ['Shoreline history', result?.domain_coverage?.shoreline_history],
    ['Terrain', result?.domain_coverage?.terrain],
    ['Rainfall / weather', result?.domain_coverage?.rainfall_weather],
    ['Ocean conditions', result?.domain_coverage?.ocean_conditions],
  ];
  const realScenes = result?.scene_count ?? 0;
  const totalScenes = result?.catalogue_scene_count ?? 55;
  const isFull = result?.model_mode === 'full_55_scene';

  return (
    <main className="result-page result-page-clean" aria-label="XGBoost result">
      <header className="result-header clean-result-header">
        <div>
          <div className="result-eyebrow"><BarChart3 size={16} /> COASTAL CHANGE ANALYSIS</div>
          <h1>Model results</h1>
          <p>Thiruvananthapuram Coast, Kerala <span className="header-separator">/</span> 2015–2025</p>
        </div>
        <button type="button" className="result-refresh" onClick={() => runModel(true)} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
          {loading ? 'Processing…' : 'Run analysis'}
        </button>
      </header>

      {loading ? (
        <section className="result-loading clean-state">
          <RefreshCw size={26} className="spin" />
          <strong>Preparing the coastal-change result</strong>
          <span>Checking satellite coverage, calculating features and rendering the map.</span>
        </section>
      ) : error ? (
        <section className="result-error clean-state" role="alert">
          <AlertTriangle size={24} />
          <div>
            <strong>Analysis could not be completed</strong>
            <span>{error}</span>
            <small>Check the FastAPI terminal for the underlying error, then select Run analysis to retry.</small>
            <button type="button" className="result-retry-inline" onClick={() => runModel(true)}>Retry analysis</button>
          </div>
        </section>
      ) : (
        <>
          <section className="forecast-section" aria-label="Shoreline forecast">
            <header className="forecast-header">
              <div><span className="result-eyebrow">SHORELINE FORECAST</span><h2>{forecastYear} forecast</h2><p>Forecast origin: end of 2025. Negative displacement denotes retreat.</p></div>
              <div className="forecast-toggle" aria-label="Forecast year">
                {[2026, 2027].map((year) => <button key={year} type="button" className={forecastYear === year ? 'active' : ''} onClick={() => setForecastYear(year)} disabled={forecastLoading}>{year} Forecast</button>)}
              </div>
            </header>
            {forecastLoading ? <div className="forecast-state"><RefreshCw size={20} className="spin" /> Preparing {forecastYear} forecast artifact…</div>
              : forecastError ? <div className="forecast-state error"><AlertTriangle size={20} /> {forecastError}<button type="button" onClick={() => loadForecast(forecastYear, true)}>Retry</button></div>
              : <div className="forecast-grid">
                  <article className="result-output-card forecast-map-card">
                    <div className="forecast-warning"><AlertTriangle size={15} /> Scenario preview — illustrative only; not a validated coastal forecast.</div>
                    {forecastImageError ? <div className="result-map-error"><AlertTriangle size={22}/><strong>Forecast map could not load</strong><button type="button" className="result-retry-inline" onClick={() => loadForecast(forecastYear, true)}>Regenerate</button></div>
                      : <img className="forecast-map-image" src={apiUrl(`${forecast?.artifact_urls?.map || forecast?.image_url}?v=${forecastYear}-${encodeURIComponent(forecast?.input_signature || '')}`)} onError={() => setForecastImageError(true)} alt={`${forecastYear} illustrative shoreline trend scenario`} />}
                  </article>
                  <aside className="forecast-summary">
                    <span>MODEL STATUS</span><strong>Real ML forecast unavailable</strong>
                    <p>{forecast?.model?.xgboost_regression}</p>
                    <dl><div><dt>Illustrative mean displacement</dt><dd>{Number(forecast?.summary?.mean_displacement_m || 0).toFixed(1)} m</dd></div><div><dt>Illustrative mean rate</dt><dd>{Number(forecast?.summary?.mean_retreat_rate_m_yr || 0).toFixed(2)} m/year</dd></div><div><dt>Scenario transects</dt><dd>{forecast?.summary?.transect_count || 0}</dd></div></dl>
                    <p className="forecast-note">{forecast?.validation?.reason}</p>
                  </aside>
                </div>}
          </section>
          <section className="result-metric-grid" aria-label="Analysis summary">
            <article className="result-metric">
              <span>Satellite scenes used</span>
              <strong>{realScenes}<small> / {totalScenes}</small></strong>
              <em>{isFull ? 'Complete selected archive' : 'Partial archive · real observations'}</em>
            </article>
            <article className="result-metric">
              <span>High-score area</span>
              <strong>{Number(result?.high_score_percent || 0).toFixed(1)}<small>%</small></strong>
              <em>Pixels with proxy score ≥ 0.70</em>
            </article>
            <article className="result-metric">
              <span>Valid map pixels</span>
              <strong>{Number(result?.pixels_analyzed || 0).toLocaleString('en-IN')}</strong>
              <em>After masking and quality checks</em>
            </article>
            <article className="result-metric">
              <span>Input features</span>
              <strong>{Number(result?.feature_count || 0).toLocaleString('en-IN')}</strong>
              <em>{result?.n_estimators || 0} boosting trees</em>
            </article>
          </section>

          <section className="result-map-layout">
            <article className="result-output-card clean-map-card">
              <div className="result-card-header clean-map-header">
                <div>
                  <span>SPATIAL OUTPUT</span>
                  <strong>Spectral-change proxy map</strong>
                  <p>Supporting satellite-analysis layer; not the shoreline forecast above.</p>
                </div>
                <span className={isFull ? 'result-status-pill complete' : 'result-status-pill partial'}>
                  {isFull ? 'Full archive' : 'Development run'}
                </span>
              </div>
              <div className="result-image-wrap clean-result-image">
                {imageError ? (
                  <div className="result-map-error" role="alert">
                    <AlertTriangle size={22} />
                    <strong>Map image could not load</strong>
                    <span>The result data loaded, but the PNG endpoint failed.</span>
                    <button type="button" className="result-retry-inline" onClick={() => runModel(true)}>Regenerate map</button>
                  </div>
                ) : (
                  <img
                    src={result?.image_url ? result.image_url + '?v=' + encodeURIComponent(result.run_id || 'latest') : ''}
                    alt="Geographically annotated spectral-change proxy map for Thiruvananthapuram Coast, with score zones, study-area boundary, coordinate labels, north arrow, scale bar and legend"
                    onError={() => setImageError(true)}
                  />
                )}
              </div>
              <div className="result-map-caption">
                <span><i className="caption-dot" /> Study-area boundary shown; no coastline is inferred.</span>
                <span>Map generated {result?.run_id ? result.run_id.replace('T', ' · ').replace('Z', ' UTC') : 'for latest run'}</span>
              </div>
            </article>

            <aside className="result-context-column">
              <article className="result-context-card">
                <div className="result-panel-title"><Target size={16} /> MODEL SUMMARY</div>
                <dl className="result-summary-list">
                  <div><dt>Algorithm</dt><dd>XGBoost classifier</dd></div>
                  <div><dt>Analysis period</dt><dd>2015–2025</dd></div>
                  <div><dt>Target</dt><dd>Spectral-change pseudo-label</dd></div>
                  <div><dt>Output meaning</dt><dd>Unvalidated change proxy</dd></div>
                </dl>
              </article>
              <article className="result-context-card">
                <div className="result-panel-title"><Satellite size={16} /> INPUT COVERAGE</div>
                <div className="coverage-summary">
                  <div><span>Real satellite archive</span><strong>{realScenes}/{totalScenes}</strong></div>
                  <div className="coverage-track"><i style={{ width: Math.min(100, totalScenes ? realScenes / totalScenes * 100 : 0) + '%' }} /></div>
                </div>
                <div className="domain-coverage-list">
                  {domains.map(([name, info]) => (
                    <div key={name} className="domain-coverage-row">
                      <span>{name}</span>
                      <b>{info?.record_count ?? 0} <small>records</small></b>
                      <em>Scenario data</em>
                    </div>
                  ))}
                </div>
              </article>
            </aside>
          </section>

          <section className="result-bottom-grid clean-result-bottom">
            <article className="result-panel clean-result-panel">
              <div className="result-panel-title"><TreePine size={17} /> MOST INFLUENTIAL FEATURES</div>
              <p className="panel-description">Relative contribution within this fitted model; not causal importance.</p>
              <div className="feature-list">
                {(result?.top_features || []).slice(0, 8).map((feature) => (
                  <div key={feature.name} className="feature-row clean-feature-row">
                    <span title={feature.name}>{feature.name}</span>
                    <div className="feature-track"><i style={{ width: Math.max(2, feature.importance * 100) + '%' }} /></div>
                    <b>{(feature.importance * 100).toFixed(1)}%</b>
                  </div>
                ))}
              </div>
            </article>
            <article className="result-panel clean-result-panel">
              <div className="result-panel-title"><AlertTriangle size={17} /> INTERPRETATION & LIMITATIONS</div>
              <ul className="result-limitations">
                {(result?.limitations || []).map((item, index) => <li key={index}>{item}</li>)}
              </ul>
              <div className="result-caveat">
                <strong>Important</strong>
                <span>{result?.pseudo_label || 'The output is a spectral-change proxy, not a validated erosion prediction.'}</span>
              </div>
            </article>
          </section>
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
