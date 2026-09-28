import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, Polygon, TileLayer } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const DEFAULT_CENTER = [12.8, 80.2];

function SatellitePanel({ data, onClose }) {
  const years = ['2016', '2026'];

  return (
    <div className="satellite-panel">
      <button type="button" className="satellite-close" onClick={onClose} aria-label="Close raw satellite data">×</button>
      <div className="satellite-panel-header">
        <div>
          <strong>Raw Satellite Data</strong>
          <span>Same AOI · Landsat Collection 2 Level-2</span>
        </div>
        <span className="data-status">LIVE DATA</span>
      </div>

      <div className="satellite-cards">
        {years.map((year) => {
          const item = data?.years?.[year];
          return (
            <article className="satellite-card" key={year}>
              {item?.available ? (
                <>
                  <img
                    src={item.preview_url}
                    alt={year + ' Landsat scene preview'}
                    className="satellite-preview"
                  />
                  <div className="satellite-card-body">
                    <div className="satellite-year">{year}</div>
                    <div className="satellite-scene">{item.scene_id}</div>
                    <div className="satellite-meta">
                      <span>{new Date(item.acquisition_datetime).toLocaleDateString()}</span>
                      <span>{Number(item.cloud_cover_percent).toFixed(2)}% cloud</span>
                    </div>
                    <div className="satellite-links">
                      {Object.entries(item.download_urls || {}).map(([name, url]) => (
                        <a href={url} download key={name}>{name.replace('B2_', 'B2 ').replace('B3_', 'B3 ').replace('B4_', 'B4 ').replace('B5_', 'B5 ').replace('B6_', 'B6 ').replace('B7_', 'B7 ')}</a>
                      ))}
                      <a href={item.metadata_url} target="_blank" rel="noreferrer">metadata</a>
                    </div>
                  </div>
                </>
              ) : (
                <div className="satellite-empty">
                  <div className="satellite-year">{year}</div>
                  <span>Data not found locally.</span>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

export default function MapView({ activeSection, satelliteDataOpen }) {
  const [aoi, setAoi] = useState(null);
  const [satelliteData, setSatelliteData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/aoi')
      .then((response) => { if (!response.ok) throw new Error('AOI unavailable'); return response.json(); })
      .then((data) => { if (!cancelled) setAoi(data); })
      .catch(() => { if (!cancelled) setAoi(null); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (activeSection !== 'satellite' || !satelliteDataOpen) return undefined;
    let cancelled = false;
    fetch('/satellite/data')
      .then((response) => { if (!response.ok) throw new Error('Satellite data unavailable'); return response.json(); })
      .then((data) => { if (!cancelled) setSatelliteData(data); })
      .catch(() => { if (!cancelled) setSatelliteData(null); });
    return () => { cancelled = true; };
  }, [activeSection, satelliteDataOpen]);

  const current = useMemo(() => SECTIONS.find((section) => section.id === activeSection) || SECTIONS[0], [activeSection]);
  const Icon = current.icon;
  const polygonPositions = useMemo(() => {
    const ring = aoi?.features?.[0]?.geometry?.coordinates?.[0];
    if (!Array.isArray(ring)) return null;
    return ring.map(([longitude, latitude]) => [latitude, longitude]);
  }, [aoi]);

  return (
    <main className="map-container">
      <div className="map-banner">
        <Icon size={18} color={current.color} />
        <span>Active View: {current.name}</span>
      </div>

      {activeSection === 'satellite' && satelliteDataOpen && <SatellitePanel data={satelliteData} onClose={() => window.dispatchEvent(new CustomEvent('close-satellite-data'))} />}

      <MapContainer center={DEFAULT_CENTER} zoom={10} minZoom={8} maxZoom={18} zoomControl style={{ height: '100%', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {polygonPositions && (
          <Polygon positions={polygonPositions} pathOptions={{ color: '#38bdf8', weight: 2, fillColor: '#38bdf8', fillOpacity: 0.05 }} />
        )}
      </MapContainer>

      {activeSection !== 'satellite' && (
        <div className="map-stage-label">
          <strong>{current.name}</strong>
          <span>Domain output will be added here as each research system is implemented.</span>
        </div>
      )}
    </main>
  );
}
