import React, { useEffect, useMemo, useState } from 'react';
import { GeoJSON, MapContainer, Polygon, TileLayer } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const DEFAULT_CENTER = [8.46, 76.925];

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
  const [shorelineError, setShorelineError] = useState(null);

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

  const shorelineStyle = useMemo(
    () => ({
      color: '#ff4d6d',
      weight: 3,
      opacity: 0.95,
    }),
    [],
  );

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
          <label
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              cursor: realShorelineAvailable ? 'pointer' : 'default',
              fontWeight: 600,
            }}
          >
            <input
              type="checkbox"
              checked={shorelineVisible}
              disabled={!realShorelineAvailable}
              onChange={(event) => setShorelineVisible(event.target.checked)}
            />
            <span style={{ color: '#ff7b91' }}>━━</span>
            Real CoastSat shoreline
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
              <p style={{ margin: '8px 0 0', color: '#bbf7d0' }}>
                {shorelineData.feature_count ?? shorelineData.geojson.features.length} extracted features
              </p>
              <p style={{ margin: '4px 0 0', color: '#cbd5e1' }}>
                Source: CoastSat
              </p>
              <p style={{ margin: '4px 0 0', color: '#fde68a' }}>
                Review the detections before scientific interpretation.
              </p>
            </>
          ) : (
            <p role="status" style={{ margin: '8px 0 0', color: '#fde68a' }}>
              Real shoreline output not generated yet. Synthetic history data
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

        {activeSection === 'history' &&
          shorelineVisible &&
          realShorelineAvailable && (
            <GeoJSON
              key={shorelineData.metadata?.generated_utc || 'coastsat-shoreline'}
              data={shorelineData.geojson}
              style={shorelineStyle}
            />
          )}
      </MapContainer>

      {activeSection !== 'satellite' && activeSection !== 'history' && (
        <div className="map-stage-label">
          <strong>{current.name}</strong>
          <span>
            Domain output will be added here as each research system is implemented.
          </span>
        </div>
      )}
    </main>
  );
}
