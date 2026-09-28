import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, Polygon, TileLayer } from 'react-leaflet';
import { SECTIONS } from './Sidebar';

const DEFAULT_CENTER = [12.8, 80.2];

function SatellitePanel({ data, onClose }) {
  const years = ['2016', '2026'];

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
                <img
                  src={item.preview_url}
                  alt={year + ' raw satellite imagery'}
                />
              ) : null}
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
