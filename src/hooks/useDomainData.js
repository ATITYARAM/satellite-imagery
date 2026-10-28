/**
 * useDomainData — React hook that loads synthetic domain data for the UI.
 *
 * In a production deployment these fetches would hit a backend API that
 * provides real satellite-derived or downloaded data. In this release all
 * domains except satellite_imagery use pre-generated synthetic JSON files
 * served from /domains/<domain>/data/synthetic/.
 *
 * DATA STATUS per domain:
 *   satellite_imagery  — pipeline defined; real imagery requires Planetary Computer
 *   shoreline_history  — SYNTHETIC (random-walk model, seed 42)
 *   terrain            — SYNTHETIC (procedural surface, seed 42)
 *   rainfall_weather   — SYNTHETIC (seasonal Poisson model, seed 42)
 *   ocean_conditions   — SYNTHETIC (M2+S2 tide + climatological waves, seed 42)
 */

import { useState, useEffect } from 'react';

const BASE = import.meta.env.BASE_URL ?? '/';

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${path}`);
  return res.json();
}

/** Aggregate shoreline observations into per-transect summary */
function summariseShoreline(data) {
  if (!data?.records) return null;
  const byTransect = {};
  for (const r of data.records) {
    if (r.scenario !== 'erosion') continue; // show erosion scenario on map
    if (!byTransect[r.transect_id]) byTransect[r.transect_id] = [];
    byTransect[r.transect_id].push(r);
  }
  return Object.values(byTransect).map(pts => {
    const sorted = pts.sort((a, b) => a.date.localeCompare(b.date));
    const first = sorted[0];
    const last = sorted.at(-1);
    return {
      transect_id: first.transect_id,
      lat: first.lat,
      lon: first.lon,
      start_date: first.date,
      end_date: last.date,
      total_displacement_m: last.displacement_m,
      avg_rate_m_yr: parseFloat((last.displacement_m / (sorted.length * 3)).toFixed(3)),
      scenario: first.scenario,
      synthetic: true,
    };
  });
}

/** Get last 30 days of rainfall records */
function recentRainfall(data) {
  if (!data?.records) return null;
  return data.records.slice(-30);
}

/** Get last 7 days of ocean records */
function recentOcean(data) {
  if (!data?.records) return null;
  return data.records.slice(-28); // 4/day × 7 days
}

/** Sample terrain at grid edges for overlay */
function sampleTerrain(data) {
  if (!data?.records) return null;
  // Return every 10th record for map overlay performance
  return data.records.filter((_, i) => i % 10 === 0);
}

export function useDomainData(activeSection) {
  const [state, setState] = useState({ loading: false, error: null, data: null });

  useEffect(() => {
    if (!activeSection) return;
    setState({ loading: true, error: null, data: null });

    const controllers = [];

    async function load() {
      try {
        let data = null;

        if (activeSection === 'history') {
          const raw = await fetchJSON('domains/shoreline_history/data/synthetic/shoreline_observations.json');
          data = { type: 'shoreline', records: summariseShoreline(raw), metadata: raw.metadata };

        } else if (activeSection === 'terrain') {
          const raw = await fetchJSON('domains/terrain/data/synthetic/terrain_grid.json');
          data = { type: 'terrain', records: sampleTerrain(raw), metadata: raw.metadata };

        } else if (activeSection === 'rainfall') {
          const raw = await fetchJSON('domains/rainfall_weather/data/synthetic/rainfall_weather_daily.json');
          data = { type: 'rainfall', records: recentRainfall(raw), metadata: raw.metadata };

        } else if (activeSection === 'ocean') {
          const raw = await fetchJSON('domains/ocean_conditions/data/synthetic/ocean_conditions_6h.json');
          data = { type: 'ocean', records: recentOcean(raw), metadata: raw.metadata };

        } else if (activeSection === 'weather') {
          // Weather shares the rainfall_weather domain
          const raw = await fetchJSON('domains/rainfall_weather/data/synthetic/rainfall_weather_daily.json');
          data = { type: 'weather', records: recentRainfall(raw), metadata: raw.metadata };

        } else if (activeSection === 'prediction') {
          // Load all domains for combined prediction view
          const [sl, oc, rw] = await Promise.all([
            fetchJSON('domains/shoreline_history/data/synthetic/shoreline_observations.json'),
            fetchJSON('domains/ocean_conditions/data/synthetic/ocean_conditions_6h.json'),
            fetchJSON('domains/rainfall_weather/data/synthetic/rainfall_weather_daily.json'),
          ]);
          data = {
            type: 'prediction',
            shoreline: summariseShoreline(sl),
            ocean: recentOcean(oc),
            rainfall: recentRainfall(rw),
            metadata: {
              note: 'Illustrative scenario only — uses proxy labels and is not a validated scientific prediction.',
              synthetic: true,
            },
          };
        }

        setState({ loading: false, error: null, data });
      } catch (err) {
        setState({ loading: false, error: err.message, data: null });
      }
    }

    load();
    return () => controllers.forEach(c => c.abort());
  }, [activeSection]);

  return state;
}
