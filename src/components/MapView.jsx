import React, { useEffect, useMemo, useState } from 'react';
import { CircleMarker, GeoJSON, MapContainer, Polygon, Popup, TileLayer } from 'react-leaflet';
import { SECTIONS } from './Sidebar';
import { AlertTriangle, CloudRain, Database, History, Mountain, Waves } from 'lucide-react';

const DEFAULT_CENTER = [8.46, 76.925];

const DOMAIN_CONFIG = {
  history: {
    title: 'Shoreline history', eyebrow: 'DOMAIN 02', icon: History,
    description: 'Transect-by-transect shoreline displacement across the 2015–2025 study window.',
    path: '/domains/shoreline_history/data/synthetic/shoreline_observations.json',
  },
  terrain: {
    title: 'Terrain & coastal topography', eyebrow: 'DOMAIN 03', icon: Mountain,
    description: 'Elevation, slope and distance-to-coast context across the study-area grid.',
    path: '/domains/terrain/data/synthetic/terrain_grid.json',
  },
  weather: {
    title: 'Rainfall & weather', eyebrow: 'DOMAIN 04', icon: CloudRain,
    description: 'Monthly rainfall and atmospheric context for 2015–2025.',
    path: '/domains/rainfall_weather/data/synthetic/rainfall_weather_daily.json',
  },
  ocean: {
    title: 'Ocean conditions', eyebrow: 'DOMAIN 05', icon: Waves,
    description: 'Monthly wave-height, wave-period and tide context for 2015–2025.',
    path: '/domains/ocean_conditions/data/synthetic/ocean_conditions_6h.json',
  },
};

function featureYear(feature) {
  const properties = feature?.properties || {};
  const candidates = [
    properties.date, properties.datetime, properties.acquisition_date,
    properties.acquisition_datetime, properties.timestamp, properties.time,
    properties.year,
  ];
  for (const value of candidates) {
    if (value == null || value === '') continue;
    const match = String(value).match(/(?:19|20)\\d{2}/);
    if (match) {
      const year = Number(match[0]);
      if (year >= 1900 && year <= 2100) return year;
    }
  }
  return null;
}

function fmt(value, digits = 1) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—';
}

function MiniBars({ rows, valueKey, labelKey = 'label', color = '#38bdf8', suffix = '' }) {
  const values = rows.map((r) => Number(r[valueKey]) || 0);
  const max = Math.max(1, ...values);
  return (
    <div className="domain-mini-chart">
      {rows.map((row, index) => (
        <div className="domain-mini-bar-row" key={row[labelKey] ?? index}>
          <span>{row[labelKey]}</span>
          <div className="domain-mini-bar-track"><i style={{ width: `${Math.max(2, (values[index] / max) * 100)}%`, background: color }} /></div>
          <b>{fmt(values[index], 1)}{suffix}</b>
        </div>
      ))}
    </div>
  );
}

function DomainDashboard({ section, payload, loading, error }) {
  const config = DOMAIN_CONFIG[section];
  if (!config) return null;
  const Icon = config.icon;
  const records = payload?.records || [];
  const monthly = records.filter((row) => row.month);
  const latest = monthly.at(-1);
  const fixture = payload?.metadata?.synthetic === true || records.some((row) => row.synthetic || row.data_origin === 'SYNTHETIC');
  let stats = [];
  let chart = null;

  if (section === 'history') {
    const byTransect = {};
    records.forEach((row) => { (byTransect[row.transect_id] ||= []).push(row); });
    const series = Object.entries(byTransect).map(([id, pts]) => {
      const sorted = [...pts].sort((a, b) => String(a.date).localeCompare(String(b.date)));
      const first = sorted[0], last = sorted.at(-1);
      return { label: id, displacement: Number(last?.displacement_m) - Number(first?.displacement_m), uncertainty: Number(last?.uncertainty_m) || 0, lat: last?.lat, lon: last?.lon };
    });
    const retreatCount = series.filter((r) => r.displacement < 0).length;
    stats = [
      ['Transects', series.length],
      ['Retreat scenarios', retreatCount],
      ['Mean displacement', `${fmt(series.length ? series.reduce((s, r) => s + r.displacement, 0) / series.length : NaN)} m`],
    ];
    chart = <><h3>2015–2025 displacement by transect</h3><MiniBars rows={series.map((r) => ({ label: r.label, value: Math.abs(r.displacement) }))} valueKey="value" color="#fb7185" suffix=" m" /><p className="domain-chart-note">Bars show magnitude only; the sign and uncertainty are listed in the table below.</p><div className="domain-detail-list">{series.map((r) => <div key={r.label}><span>{r.label}</span><b className={r.displacement < 0 ? 'negative' : 'positive'}>{r.displacement < 0 ? 'Retreat' : 'Advance'} · {fmt(Math.abs(r.displacement))} m</b><small>Illustrative uncertainty ±{fmt(r.uncertainty)} m</small></div>)}</div></>;
  } else if (section === 'terrain') {
    const min = Math.min(...records.map((r) => Number(r.elevation_m)).filter(Number.isFinite));
    const max = Math.max(...records.map((r) => Number(r.elevation_m)).filter(Number.isFinite));
    const avg = records.length ? records.reduce((s, r) => s + (Number(r.elevation_m) || 0), 0) / records.length : NaN;
    const slope = records.length ? records.reduce((s, r) => s + (Number(r.slope_deg) || 0), 0) / records.length : NaN;
    stats = [['Grid cells', records.length], ['Elevation range', `${fmt(min)}–${fmt(max)} m`], ['Mean slope', `${fmt(slope, 2)}°`]];
    const bins = [
      { label: '0–1 m', value: records.filter((r) => r.elevation_m >= 0 && r.elevation_m < 1).length },
      { label: '1–2 m', value: records.filter((r) => r.elevation_m >= 1 && r.elevation_m < 2).length },
      { label: '2–3 m', value: records.filter((r) => r.elevation_m >= 2 && r.elevation_m < 3).length },
      { label: '3 m+', value: records.filter((r) => r.elevation_m >= 3).length },
    ];
    chart = <><h3>Elevation distribution</h3><MiniBars rows={bins} valueKey="value" color="#34d399" suffix=" cells" /><p className="domain-chart-note">Map dots are colored by elevation. Low-lying cells are shown in warm colors; higher cells in green/blue.</p></>;
  } else if (section === 'weather') {
    const rain = monthly;
    const annual = Object.values(rain.reduce((acc, r) => { acc[r.year] ||= { label: String(r.year), value: 0 }; acc[r.year].value += Number(r.rainfall_mm) || 0; return acc; }, {}));
    const latestRain = latest?.rainfall_mm;
    const wettest = [...rain].sort((a, b) => (Number(b.rainfall_mm) || 0) - (Number(a.rainfall_mm) || 0))[0];
    stats = [['Monthly records', records.length], ['Latest monthly rainfall', `${fmt(latestRain)} mm`], ['Highest month in archive', wettest ? `${wettest.year}-${String(wettest.month).padStart(2,'0')}` : '—']];
    chart = <><h3>Annual rainfall totals</h3><MiniBars rows={annual.slice(-8)} valueKey="value" color="#f59e0b" suffix=" mm" /><h3 className="domain-subchart-title">Latest monthly context</h3><div className="domain-detail-list"><div><span>Mean daily rainfall</span><b>{fmt(latest?.rainfall_mean_mm_day)} mm/day</b></div><div><span>Wind speed</span><b>{fmt(latest?.wind_speed_kmh)} km/h</b></div><div><span>Temperature</span><b>{fmt(latest?.temp_c)} °C</b></div><div><span>Pressure</span><b>{fmt(latest?.pressure_hpa)} hPa</b></div></div></>;
  } else if (section === 'ocean') {
    const maxWave = Math.max(...monthly.map((r) => Number(r.Hs_mean_m) || 0));
    const highMonths = monthly.filter((r) => r.high_wave_month_flag).length;
    stats = [['Monthly records', records.length], ['Peak mean wave height', `${fmt(maxWave)} m`], ['Flagged high-wave months', highMonths]];
    chart = <><h3>Monthly mean significant wave height</h3><MiniBars rows={monthly.slice(-12).map((r) => ({ label: new Date(Number(r.year), Number(r.month)-1, 1).toLocaleString('en', { month: 'short' }), value: Number(r.Hs_mean_m) || 0 }))} valueKey="value" color="#22d3ee" suffix=" m" /><h3 className="domain-subchart-title">Latest marine context</h3><div className="domain-detail-list"><div><span>Peak wave estimate</span><b>{fmt(latest?.Hs_p95_m)} m</b></div><div><span>Mean wave period</span><b>{fmt(latest?.Tp_mean_s)} s</b></div><div><span>Tidal range</span><b>{fmt(latest?.tidal_range_m)} m</b></div><div><span>Estimated storm days</span><b>{fmt(latest?.storm_days_estimate, 0)}</b></div></div></>;
  }

  return (
    <aside className="domain-dashboard" aria-label={config.title}>
      <header className="domain-dashboard-header"><div className="domain-dashboard-icon"><Icon size={20}/></div><div><span>{config.eyebrow}</span><h2>{config.title}</h2><p>{config.description}</p></div></header>
      {loading ? <div className="domain-dashboard-state">Loading domain records…</div> : error ? <div className="domain-dashboard-state error"><AlertTriangle size={17}/>{error}</div> : records.length === 0 ? <div className="domain-dashboard-state">No records are available for this domain.</div> : <>
        <div className="domain-stat-grid">{stats.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
        <div className="domain-dashboard-chart">{chart}</div>
        <div className={`domain-provenance ${fixture ? 'scenario' : 'observed'}`}><Database size={15}/><div><strong>{fixture ? 'Illustrative scenario dataset' : 'Loaded domain dataset'}</strong><p>{fixture ? 'These values help demonstrate the workflow and charts; they are not live measurements or validated evidence of coastal change.' : 'Values loaded from the configured domain data source.'}</p></div></div>
      </>}
    </aside>
  );
}

function SatellitePanel({ data, onClose }) {
  const years = ['2015', '2025'];

  return (
    <div className="satellite-panel raw-image-only">
      <button
        type="button"
        className="satellite-close"
        onClick={onClose}
        aria-label="Close raw satellite data"
      >
        ×
      </button>

      <div className="raw-image-split">
        {years.map((year) => {
          const item = data?.years?.[year];

          return (
            <div className="raw-image-side" key={year}>
              {item?.available ? (
                <img src={item.preview_url} alt={`${year} raw satellite imagery`} />
              ) : (
                <div className="satellite-unavailable">
                  <strong>{year} imagery not downloaded for this coastline</strong>
                  <span>Run the Landsat AOI download script in the project terminal.</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function MapView({ activeSection, satelliteDataOpen }) {
  const [aoi, setAoi] = useState(null);
  const [satelliteData, setSatelliteData] = useState(null);
  const [shorelineData, setShorelineData] = useState(null);
  const [shorelineVisible, setShorelineVisible] = useState(true);
  const [shorelineYearA, setShorelineYearA] = useState('2015');
  const [shorelineYearB, setShorelineYearB] = useState('2025');
  const [shorelineError, setShorelineError] = useState(null);
  const [domainPayload, setDomainPayload] = useState(null);
  const [domainLoading, setDomainLoading] = useState(false);
  const [domainError, setDomainError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    fetch('/aoi')
      .then((response) => {
        if (!response.ok) throw new Error('AOI unavailable');
        return response.json();
      })
      .then((data) => {
        if (!cancelled) setAoi(data);
      })
      .catch(() => {
        if (!cancelled) setAoi(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (activeSection !== 'satellite' || !satelliteDataOpen) return undefined;

    let cancelled = false;

    fetch('/satellite/data')
      .then((response) => {
        if (!response.ok) throw new Error('Satellite data unavailable');
        return response.json();
      })
      .then((data) => {
        if (!cancelled) setSatelliteData(data);
      })
      .catch(() => {
        if (!cancelled) setSatelliteData(null);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSection, satelliteDataOpen]);

  useEffect(() => {
    if (activeSection !== 'history') return undefined;

    let cancelled = false;
    setShorelineError(null);

    fetch('/shoreline/data')
      .then((response) => {
        if (!response.ok) throw new Error(`Shoreline API returned HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!cancelled) setShorelineData(data);
      })
      .catch((error) => {
        if (!cancelled) {
          setShorelineData(null);
          setShorelineError(error.message || 'Could not load shoreline data.');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeSection]);

  useEffect(() => {
    const config = DOMAIN_CONFIG[activeSection];
    if (!config) { setDomainPayload(null); setDomainError(null); setDomainLoading(false); return undefined; }
    let cancelled = false;
    setDomainLoading(true);
    setDomainError(null);
    fetch(config.path)
      .then((response) => { if (!response.ok) throw new Error(`Domain data request failed (HTTP ${response.status})`); return response.json(); })
      .then((json) => { if (!cancelled) setDomainPayload(json); })
      .catch((err) => { if (!cancelled) { setDomainPayload(null); setDomainError(err.message || 'Unable to load domain data.'); } })
      .finally(() => { if (!cancelled) setDomainLoading(false); });
    return () => { cancelled = true; };
  }, [activeSection]);

  const current = useMemo(
    () => SECTIONS.find((section) => section.id === activeSection) || SECTIONS[0],
    [activeSection],
  );
  const Icon = current.icon;

  const polygonPositions = useMemo(() => {
    const ring = aoi?.features?.[0]?.geometry?.coordinates?.[0];
    if (!Array.isArray(ring)) return null;
    return ring.map(([longitude, latitude]) => [latitude, longitude]);
  }, [aoi]);

  const mapCenter = useMemo(() => {
    const ring = aoi?.features?.[0]?.geometry?.coordinates?.[0];
    if (!Array.isArray(ring) || ring.length < 4) return DEFAULT_CENTER;

    const vertices = ring.slice(0, -1);
    const longitude =
      vertices.reduce((sum, point) => sum + point[0], 0) / vertices.length;
    const latitude =
      vertices.reduce((sum, point) => sum + point[1], 0) / vertices.length;

    return [latitude, longitude];
  }, [aoi]);

  const realShorelineAvailable =
    shorelineData?.available === true &&
    shorelineData?.geojson?.type === 'FeatureCollection' &&
    Array.isArray(shorelineData.geojson.features) &&
    shorelineData.geojson.features.length > 0;

  const shorelineYears = useMemo(() => {
    if (!realShorelineAvailable) return [];
    return [...new Set(shorelineData.geojson.features.map(featureYear).filter((year) => year != null))]
      .sort((a, b) => a - b);
  }, [realShorelineAvailable, shorelineData]);

  useEffect(() => {
    if (!shorelineYears.length) return;
    if (!shorelineYears.includes(Number(shorelineYearA))) setShorelineYearA(String(shorelineYears[0]));
    if (!shorelineYears.includes(Number(shorelineYearB))) setShorelineYearB(String(shorelineYears.at(-1)));
  }, [shorelineYears, shorelineYearA, shorelineYearB]);

  const shorelineLayerA = useMemo(() => ({
    type: 'FeatureCollection',
    features: (shorelineData?.geojson?.features || []).filter((feature) => featureYear(feature) === Number(shorelineYearA)),
  }), [shorelineData, shorelineYearA]);

  const shorelineLayerB = useMemo(() => ({
    type: 'FeatureCollection',
    features: (shorelineData?.geojson?.features || []).filter((feature) => featureYear(feature) === Number(shorelineYearB)),
  }), [shorelineData, shorelineYearB]);

  const shorelineStyleA = useMemo(() => ({ color: '#38bdf8', weight: 3, opacity: 0.95 }), []);
  const shorelineStyleB = useMemo(() => ({ color: '#fb7185', weight: 3, opacity: 0.95 }), []);

  return (
    <main className="map-container">
      <div className="map-banner">
        <Icon size={18} color={current.color} />
        <span>Active View: {current.name}</span>
      </div>

      {activeSection === 'satellite' && satelliteDataOpen && (
        <SatellitePanel
          data={satelliteData}
          onClose={() =>
            window.dispatchEvent(new CustomEvent('close-satellite-data'))
          }
        />
      )}

      {activeSection === 'history' && (
        <section
          aria-label="Shoreline layer controls"
          style={{
            position: 'absolute',
            zIndex: 1000,
            top: 58,
            right: 12,
            maxWidth: 'min(340px, calc(100% - 24px))',
            padding: '12px 14px',
            borderRadius: 10,
            background: 'rgba(15, 23, 42, 0.95)',
            color: '#f8fafc',
            boxShadow: '0 4px 16px rgba(0,0,0,0.22)',
            fontSize: 13,
          }}
        >
          <strong style={{ display: 'block', fontSize: 14, marginBottom: 10 }}>Compare two extracted shoreline years</strong>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <label style={{ display: 'grid', gap: 5, fontSize: 12, color: '#cbd5e1' }}>
              <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: '#38bdf8', marginRight: 5 }} />Year A</span>
              <select value={shorelineYearA} onChange={(event) => setShorelineYearA(event.target.value)} style={{ width: '100%', padding: '7px 8px', borderRadius: 6, background: '#1e293b', color: '#f8fafc', border: '1px solid #475569' }}>
                {(shorelineYears.length ? shorelineYears : Array.from({ length: 11 }, (_, i) => 2015 + i)).map((year) => <option key={year} value={year}>{year}</option>)}
              </select>
            </label>
            <label style={{ display: 'grid', gap: 5, fontSize: 12, color: '#cbd5e1' }}>
              <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3, background: '#fb7185', marginRight: 5 }} />Year B</span>
              <select value={shorelineYearB} onChange={(event) => setShorelineYearB(event.target.value)} style={{ width: '100%', padding: '7px 8px', borderRadius: 6, background: '#1e293b', color: '#f8fafc', border: '1px solid #475569' }}>
                {(shorelineYears.length ? shorelineYears : Array.from({ length: 11 }, (_, i) => 2015 + i)).map((year) => <option key={year} value={year}>{year}</option>)}
              </select>
            </label>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, cursor: realShorelineAvailable ? 'pointer' : 'default', fontWeight: 600 }}>
            <input type="checkbox" checked={shorelineVisible} disabled={!realShorelineAvailable} onChange={(event) => setShorelineVisible(event.target.checked)} />
            Show extracted shoreline lines
          </label>

          {shorelineError ? (
            <p role="status" style={{ margin: '8px 0 0', color: '#fecaca' }}>
              Could not load shoreline data: {shorelineError}
            </p>
          ) : !shorelineData ? (
            <p role="status" style={{ margin: '8px 0 0', color: '#cbd5e1' }}>
              Checking shoreline data…
            </p>
          ) : realShorelineAvailable ? (
            <>
              <p style={{ margin: '8px 0 0', color: '#bbf7d0' }}>{shorelineData.feature_count ?? shorelineData.geojson.features.length} extracted features across {shorelineYears.length} detected years.</p>
              <p style={{ margin: '4px 0 0', color: '#cbd5e1' }}>Blue: {shorelineYearA} ({shorelineLayerA.features.length} lines) · Pink: {shorelineYearB} ({shorelineLayerB.features.length} lines)</p>
              {shorelineYearA === shorelineYearB && <p style={{ margin: '4px 0 0', color: '#fde68a' }}>Choose two different years to compare shoreline movement.</p>}
              {(shorelineLayerA.features.length === 0 || shorelineLayerB.features.length === 0) && <p style={{ margin: '4px 0 0', color: '#fde68a' }}>No extracted shoreline feature is available for one of these years. Choose another year with data.</p>}
              <p style={{ margin: '4px 0 0', color: '#cbd5e1' }}>Source: CoastSat satellite-derived detections. Review the lines before scientific interpretation.</p>
            </>
          ) : (
            <p role="status" style={{ margin: '8px 0 0', color: '#fde68a' }}>
              Real shoreline output is not generated yet. Illustrative historical scenario data
              is not displayed as a real shoreline layer.
            </p>
          )}
        </section>
      )}

      <MapContainer
        center={mapCenter}
        zoom={12}
        minZoom={8}
        maxZoom={18}
        zoomControl
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {polygonPositions && (
          <Polygon
            positions={polygonPositions}
            pathOptions={{
              color: '#38bdf8',
              weight: 2,
              fillColor: '#38bdf8',
              fillOpacity: 0.05,
            }}
          />
        )}

        {activeSection === 'history' && shorelineVisible && realShorelineAvailable && shorelineLayerA.features.length > 0 && (
          <GeoJSON key={`shoreline-${shorelineYearA}-${shorelineData.metadata?.generated_utc || 'extracted'}`} data={shorelineLayerA} style={shorelineStyleA} />
        )}
        {activeSection === 'history' && shorelineVisible && realShorelineAvailable && shorelineYearB !== shorelineYearA && shorelineLayerB.features.length > 0 && (
          <GeoJSON key={`shoreline-${shorelineYearB}-${shorelineData.metadata?.generated_utc || 'extracted'}`} data={shorelineLayerB} style={shorelineStyleB} />
        )}

        {activeSection === 'terrain' && domainPayload?.records?.map((row, index) => {
          const elevation = Number(row.elevation_m) || 0;
          const color = elevation < 1 ? '#f97316' : elevation < 2 ? '#facc15' : elevation < 3 ? '#34d399' : '#38bdf8';
          return <CircleMarker key={`${row.row}-${row.col}-${index}`} center={[row.lat, row.lon]} radius={5} pathOptions={{ color, fillColor: color, fillOpacity: .8, weight: .6 }}>
            <Popup><strong>Terrain cell {row.row}, {row.col}</strong><br/>Elevation: {fmt(elevation)} m<br/>Slope: {fmt(Number(row.slope_deg), 2)}°<br/>Coastal proximity: {fmt(Number(row.coastal_proximity_m), 0)} m</Popup>
          </CircleMarker>;
        })}
      </MapContainer>

      {DOMAIN_CONFIG[activeSection] && activeSection !== 'history' && <DomainDashboard section={activeSection} payload={domainPayload} loading={domainLoading} error={domainError} />}
    </main>
  );
}
