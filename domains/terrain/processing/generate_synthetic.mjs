/**
 * Synthetic Terrain Generator
 * ============================
 * Generates a simulated coastal elevation surface for pipeline testing.
 * OUTPUT IS SYNTHETIC — not a real DEM or measured elevation data.
 *
 * Model: 2-D procedural surface with coastal gradient, dune ridge,
 * and low-frequency noise. Slope and aspect are derived analytically.
 *
 * Usage:
 *   node domains/terrain/processing/generate_synthetic.mjs [seed]
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

// Grid parameters — 30 m cells over ~3 km × 3 km
const GRID_COLS = 100;
const GRID_ROWS = 100;
const CELL_SIZE_M = 30;
const ORIGIN_LAT = 11.720;
const ORIGIN_LON = 79.750;
const DEG_PER_M_LAT = 1 / 111320;
const DEG_PER_M_LON = 1 / (111320 * Math.cos(ORIGIN_LAT * Math.PI / 180));

// Simple noise helper
function smoothNoise(x, y, scale, rand) {
  const xi = Math.floor(x / scale);
  const yi = Math.floor(y / scale);
  const fx = (x / scale) - xi;
  const fy = (y / scale) - yi;
  // deterministic hash
  const h = (xi * 1619 + yi * 31337 + SEED * 6791) & 0xffff;
  return (Math.sin(h * 0.003) * 0.5 + 0.5) * (1 - fx) * (1 - fy) +
         (Math.sin((h + 13) * 0.003) * 0.5 + 0.5) * fx * (1 - fy) +
         (Math.sin((h + 27) * 0.003) * 0.5 + 0.5) * (1 - fx) * fy +
         (Math.sin((h + 41) * 0.003) * 0.5 + 0.5) * fx * fy;
}

function elevation(col, row) {
  const x = col * CELL_SIZE_M;
  const y = row * CELL_SIZE_M;
  // Shore is at col=90 (east edge); elevation rises westward
  const distFromShore = (GRID_COLS - col) * CELL_SIZE_M;
  const base = 0.5 + distFromShore * 0.003;             // gentle inland rise
  const dune = 2.5 * Math.exp(-Math.pow((distFromShore - 150) / 80, 2)); // dune ridge
  const noise = smoothNoise(x, y, 400, rand) * 1.2 - 0.6;
  return parseFloat(Math.max(0, base + dune + noise).toFixed(2));
}

const records = [];
for (let r = 0; r < GRID_ROWS; r++) {
  for (let c = 0; c < GRID_COLS; c++) {
    const elev = elevation(c, r);
    // Slope: finite difference (deg)
    const dzdx = (elevation(Math.min(c + 1, GRID_COLS - 1), r) - elevation(Math.max(c - 1, 0), r)) / (2 * CELL_SIZE_M);
    const dzdy = (elevation(c, Math.min(r + 1, GRID_ROWS - 1)) - elevation(c, Math.max(r - 1, 0))) / (2 * CELL_SIZE_M);
    const slope = parseFloat((Math.atan(Math.sqrt(dzdx * dzdx + dzdy * dzdy)) * 180 / Math.PI).toFixed(3));
    const aspect = parseFloat(((Math.atan2(-dzdy, dzdx) * 180 / Math.PI + 360) % 360).toFixed(1));
    const lat = parseFloat((ORIGIN_LAT + r * CELL_SIZE_M * DEG_PER_M_LAT).toFixed(6));
    const lon = parseFloat((ORIGIN_LON + c * CELL_SIZE_M * DEG_PER_M_LON).toFixed(6));
    const coastal_proximity = parseFloat(((GRID_COLS - c) * CELL_SIZE_M).toFixed(1));
    records.push({ col: c, row: r, lat, lon, elevation_m: elev, slope_deg: slope, aspect_deg: aspect, coastal_proximity_m: coastal_proximity });
  }
}

mkdirSync(OUT_DIR, { recursive: true });

writeFileSync(join(OUT_DIR, 'terrain_grid.json'), JSON.stringify({
  metadata: {
    data_origin: 'SYNTHETIC',
    synthetic: true,
    generator_version: '1.0.0',
    generation_timestamp: new Date().toISOString(),
    seed: SEED,
    domain: 'terrain',
    crs: 'WGS-84 (EPSG:4326)',
    vertical_datum: 'SYNTHETIC — not EGM96 or any real datum',
    resolution_m: CELL_SIZE_M,
    grid: { cols: GRID_COLS, rows: GRID_ROWS },
    units: { elevation_m: 'metres', slope_deg: 'degrees', aspect_deg: 'degrees from North', coastal_proximity_m: 'metres' },
    limitations: [
      'This is a procedurally generated surface — NOT a real DEM.',
      'Elevation values are not measured and have no physical validity.',
      'Do not use for engineering, navigation, or scientific analysis.',
    ],
  },
  records,
}, null, 2));

// Summary CSV (every 5th cell to keep file small)
const csvLines = ['col,row,lat,lon,elevation_m,slope_deg,aspect_deg,coastal_proximity_m,synthetic'];
for (const r of records.filter((_, i) => i % 5 === 0)) {
  csvLines.push(`${r.col},${r.row},${r.lat},${r.lon},${r.elevation_m},${r.slope_deg},${r.aspect_deg},${r.coastal_proximity_m},true`);
}
writeFileSync(join(OUT_DIR, 'terrain_sample.csv'), csvLines.join('\n'));

console.log(`[terrain] Synthetic data written to ${OUT_DIR}`);
console.log(`  Grid cells: ${records.length}  |  Seed: ${SEED}`);
