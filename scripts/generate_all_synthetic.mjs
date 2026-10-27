/**
 * Generate all synthetic datasets.
 * Run: node scripts/generate_all_synthetic.mjs [seed]
 */
import { execSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SEED = process.argv[2] ?? '42';

const generators = [
  'domains/shoreline_history/processing/generate_synthetic.mjs',
  'domains/terrain/processing/generate_synthetic.mjs',
  'domains/rainfall_weather/processing/generate_synthetic.mjs',
  'domains/ocean_conditions/processing/generate_synthetic.mjs',
];

console.log(`\n=== Generating all synthetic datasets (seed=${SEED}) ===\n`);
for (const g of generators) {
  console.log(`→ ${g}`);
  execSync(`node ${join(ROOT, g)} ${SEED}`, { stdio: 'inherit' });
}
console.log('\n✓ All synthetic datasets generated.\n');
console.log('NOTE: These are SYNTHETIC datasets for testing only.');
console.log('      They do not represent real measurements.\n');
