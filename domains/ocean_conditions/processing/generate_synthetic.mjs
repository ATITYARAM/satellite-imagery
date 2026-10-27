/**
 * Synthetic Ocean-Conditions Generator
 * =======================================
 * Generates timestamped wave and tide records for pipeline testing.
 * OUTPUT IS SYNTHETIC — not INCOIS measurements or TPXO tide predictions.
 *
 * Models:
 *   - Waves: Hs scaled to Bay of Bengal climatology; seasonal + storm events
 *   - Tides: simplified M2 + S2 harmonic (period ~12.42 h and 12.00 h)
 *   - Wave power: P = (ρ g² / 64π) × Hs² × Tp  [kW/m, deepwater approximation]
 *
 * Usage:
 *   node domains/ocean_conditions/processing/generate_synthetic.mjs [seed]
 */

import { writeFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const OUT_DIR = join(__dir, '..', 'data', 'synthetic');

function mulberry32(seed) {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

const SEED = parseInt(process.argv[2] ?? '42', 10);
const rand = mulberry32(SEED);

// 6-hourly records 2015-01-01 to 2024-12-31
function dateRange6h(startY, endY) {
  const records = [];
  for (let y = startY; y <= endY; y++) {
    for (let m = 1; m <= 12; m++) {
      const days = new Date(y, m, 0).getDate();
      for (let d = 1; d <= days; d++) {
        for (const h of [0, 6, 12, 18]) {
          records.push(`${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}T${String(h).padStart(2,'0')}:00:00Z`);
        }
      }
    }
  }
  return records;
}

const timestamps = dateRange6h(2015, 2024);

// M2 + S2 tide model (Cuddalore tidal range ~1.0–1.4 m)
const M2_PERIOD_H = 12.4206;
const S2_PERIOD_H = 12.0;
const M2_AMP = 0.55;  // metres
const S2_AMP = 0.15;
const TIDAL_RANGE = (M2_AMP + S2_AMP) * 2;

function tideLevel(isoStr) {
  const ms = new Date(isoStr).getTime();
  const h = ms / 3600000;
  return parseFloat((M2_AMP * Math.cos(2 * Math.PI * h / M2_PERIOD_H) +
                     S2_AMP * Math.cos(2 * Math.PI * h / S2_PERIOD_H)).toFixed(3));
}

// Monthly mean Hs for Bay of Bengal near Cuddalore (m)
const meanHsByMonth = [1.0, 0.9, 0.8, 0.7, 0.9, 1.6, 1.8, 1.7, 1.5, 1.2, 1.3, 1.1];

function monthOf(ts) { return parseInt(ts.slice(5,7), 10); }
function hours_since_epoch(ts) { return new Date(ts).getTime() / 3600000; }

const records = [];
for (const ts of timestamps) {
  const m = monthOf(ts);
  const meanHs = meanHsByMonth[m - 1];
  // Add storm event probability ~3% per step
  const storm = rand() < 0.03 ? rand() * 2.5 : 0;
  const Hs = parseFloat(Math.max(0.2, meanHs + (rand() - 0.5) * 0.6 + storm).toFixed(2));
  const Tp = parseFloat((5 + Hs * 1.4 + (rand() - 0.5) * 1.5).toFixed(1));
  // Wave direction: predominantly from ENE (70°) with scatter
  const wave_dir_deg = Math.round((70 + (rand() - 0.5) * 60 + 360) % 360);
  // Wave power deepwater approximation (kW/m)
  const rho = 1025, g = 9.81;
  const wave_power_kw_per_m = parseFloat((rho * g * g / (64 * Math.PI) * Hs * Hs * Tp / 1000).toFixed(2));

  const tide_level_m = tideLevel(ts);
  const storm_surge_flag = storm > 1.5;

  records.push({
    timestamp: ts,
    Hs_m: Hs,
    Tp_s: Tp,
    wave_dir_deg,
    wave_power_kw_per_m,
    tide_level_m,
    tidal_range_m: parseFloat(TIDAL_RANGE.toFixed(3)),
    storm_surge_flag,
    data_origin: 'SYNTHETIC',
    synthetic: true,
  });
}

mkdirSync(OUT_DIR, { recursive: true });

writeFileSync(join(OUT_DIR, 'ocean_conditions_6h.json'), JSON.stringify({
  metadata: {
    data_origin: 'SYNTHETIC',
    synthetic: true,
    generator_version: '1.0.0',
    generation_timestamp: new Date().toISOString(),
    seed: SEED,
    domain: 'ocean_conditions',
    location: 'Bay of Bengal — Cuddalore nearshore (11.748°N 79.771°E)',
    date_range: { start: timestamps[0], end: timestamps.at(-1) },
    temporal_resolution: '6-hourly',
    tide_model: `Simplified M2 (A=${M2_AMP}m, T=${M2_PERIOD_H}h) + S2 (A=${S2_AMP}m, T=${S2_PERIOD_H}h)`,
    units: {
      Hs_m: 'metres (significant wave height)',
      Tp_s: 'seconds (peak wave period)',
      wave_dir_deg: 'degrees from North (direction waves come from)',
      wave_power_kw_per_m: 'kW/m (deepwater approximation)',
      tide_level_m: 'metres above mean water level (SYNTHETIC datum)',
      tidal_range_m: 'metres',
    },
    limitations: [
      'These are simulated records — NOT INCOIS or TPXO measurements.',
      'Tide model uses only M2+S2 constituents; real Bay of Bengal tides have ~6 constituents.',
      'Wave statistics not calibrated against any buoy or reanalysis product.',
      'Do not use for navigation, engineering, or scientific analysis.',
    ],
  },
  records,
}, null, 2));

const csvLines = ['timestamp,Hs_m,Tp_s,wave_dir_deg,wave_power_kw_per_m,tide_level_m,tidal_range_m,storm_surge_flag,synthetic'];
for (const r of records) {
  csvLines.push(`${r.timestamp},${r.Hs_m},${r.Tp_s},${r.wave_dir_deg},${r.wave_power_kw_per_m},${r.tide_level_m},${r.tidal_range_m},${r.storm_surge_flag},true`);
}
writeFileSync(join(OUT_DIR, 'ocean_conditions_6h.csv'), csvLines.join('\n'));

console.log(`[ocean_conditions] Synthetic data written to ${OUT_DIR}`);
console.log(`  Records: ${records.length}  |  Seed: ${SEED}`);
