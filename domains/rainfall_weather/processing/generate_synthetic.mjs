/**
 * Synthetic Rainfall / Weather Generator
 * ========================================
 * Generates timestamped rainfall and meteorological records for pipeline testing.
 * OUTPUT IS SYNTHETIC — not GPM IMERG measurements or ERA5 reanalysis fields.
 *
 * Model:
 *   - Daily rainfall: seasonal Poisson process scaled to Tamil Nadu monsoon
 *     climatology (NE monsoon Oct–Dec, SW monsoon Jun–Sep)
 *   - Wind, pressure, temperature: smooth seasonal signal + noise
 *
 * Usage:
 *   node domains/rainfall_weather/processing/generate_synthetic.mjs [seed]
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

// Date range: 2015-01-01 to 2024-12-31 (daily)
function dateRange(startY, endY) {
  const dates = [];
  for (let y = startY; y <= endY; y++) {
    for (let m = 1; m <= 12; m++) {
      const days = new Date(y, m, 0).getDate();
      for (let d = 1; d <= days; d++) {
        dates.push(`${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`);
      }
    }
  }
  return dates;
}

const dates = dateRange(2015, 2024);

// Seasonal monsoon intensity (month 1-12)
const monsoonFactor = [0.4,0.3,0.2,0.3,0.5,0.9,1.0,0.9,0.8,1.2,1.3,0.7];

function monthOf(dateStr) { return parseInt(dateStr.slice(5,7), 10); }
function dayOfYear(dateStr) {
  const d = new Date(dateStr);
  return Math.floor((d - new Date(d.getFullYear(), 0, 0)) / 86400000);
}

const records = [];
let accum7 = 0, accum30 = 0;
const window7 = [], window30 = [];

for (const date of dates) {
  const m = monthOf(date);
  const doy = dayOfYear(date);
  const mf = monsoonFactor[m - 1];

  // Poisson-like daily rainfall
  const lambda = mf * 12; // mean mm/day
  // Approximate Poisson using sum of geometric
  let rain = 0;
  const nEvents = Math.floor(rand() * 3);
  for (let i = 0; i < nEvents; i++) rain += -lambda * Math.log(rand() + 1e-9) / nEvents;
  const rainfall_mm = parseFloat(Math.max(0, rain).toFixed(2));
  const max_intensity = parseFloat((rainfall_mm / 24 * (1 + rand() * 2)).toFixed(3));

  window7.push(rainfall_mm); if (window7.length > 7)  window7.shift();
  window30.push(rainfall_mm); if (window30.length > 30) window30.shift();
  const accum_7d  = parseFloat(window7.reduce((a,b) => a+b, 0).toFixed(2));
  const accum_30d = parseFloat(window30.reduce((a,b) => a+b, 0).toFixed(2));

  // Wind (NE monsoon Oct-Dec: NE; SW monsoon Jun-Sep: SW)
  const isNE = m >= 10 && m <= 12;
  const isSW = m >= 6  && m <= 9;
  const baseWind = isNE ? 25 : isSW ? 20 : 10;
  const wind_speed_kmh = parseFloat(Math.max(0, baseWind + (rand() - 0.5) * 20).toFixed(1));
  const baseDir = isNE ? 45 : isSW ? 225 : 180;
  const wind_dir_deg = Math.round((baseDir + (rand() - 0.5) * 40 + 360) % 360);

  // Temperature: 24–34 °C seasonal
  const temp_c = parseFloat((29 + 5 * Math.sin((doy - 90) * 2 * Math.PI / 365) + (rand() - 0.5) * 2).toFixed(1));

  // Pressure
  const pressure_hpa = parseFloat((1010 - mf * 6 + (rand() - 0.5) * 4).toFixed(1));

  records.push({
    date,
    rainfall_mm_per_day: rainfall_mm,
    max_intensity_mm_per_hr: max_intensity,
    accum_7d_mm: accum_7d,
    accum_30d_mm: accum_30d,
    wind_speed_kmh,
    wind_dir_deg,
    temp_c,
    pressure_hpa,
    quality_flag: rainfall_mm > 80 ? 'extreme_event' : 'ok',
    data_origin: 'SYNTHETIC',
    synthetic: true,
  });
}

mkdirSync(OUT_DIR, { recursive: true });

writeFileSync(join(OUT_DIR, 'rainfall_weather_daily.json'), JSON.stringify({
  metadata: {
    data_origin: 'SYNTHETIC',
    synthetic: true,
    generator_version: '1.0.0',
    generation_timestamp: new Date().toISOString(),
    seed: SEED,
    domain: 'rainfall_weather',
    location: 'Cuddalore, Tamil Nadu, India (11.748°N 79.771°E)',
    date_range: { start: dates[0], end: dates.at(-1) },
    temporal_resolution: 'daily',
    units: {
      rainfall_mm_per_day: 'mm/day',
      max_intensity_mm_per_hr: 'mm/hr',
      accum_7d_mm: 'mm (7-day rolling sum)',
      accum_30d_mm: 'mm (30-day rolling sum)',
      wind_speed_kmh: 'km/h',
      wind_dir_deg: 'degrees from North (met convention)',
      temp_c: '°C (2m air temperature)',
      pressure_hpa: 'hPa (mean sea level)',
    },
    limitations: [
      'These are simulated records — NOT GPM IMERG or ERA5 measurements.',
      'Seasonal pattern based on Tamil Nadu monsoon climatology but values are not calibrated.',
      'Do not use as meteorological evidence.',
    ],
  },
  records,
}, null, 2));

const csvLines = ['date,rainfall_mm_per_day,max_intensity_mm_per_hr,accum_7d_mm,accum_30d_mm,wind_speed_kmh,wind_dir_deg,temp_c,pressure_hpa,quality_flag,synthetic'];
for (const r of records) {
  csvLines.push(`${r.date},${r.rainfall_mm_per_day},${r.max_intensity_mm_per_hr},${r.accum_7d_mm},${r.accum_30d_mm},${r.wind_speed_kmh},${r.wind_dir_deg},${r.temp_c},${r.pressure_hpa},${r.quality_flag},true`);
}
writeFileSync(join(OUT_DIR, 'rainfall_weather_daily.csv'), csvLines.join('\n'));

console.log(`[rainfall_weather] Synthetic data written to ${OUT_DIR}`);
console.log(`  Records: ${records.length}  |  Seed: ${SEED}`);
