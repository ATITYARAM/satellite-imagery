/**
 * Shared Data Interface
 * ======================
 * Common conventions for combining domain outputs.
 *
 * CONVENTIONS
 *  - CRS:        WGS-84 (EPSG:4326) for storage; EPSG:32644 (UTM 44N) for metric calculations
 *  - Timestamps: ISO-8601 UTC strings
 *  - Missing:    null (never NaN in JSON)
 *  - Provenance: every record carries { data_origin, synthetic } fields
 *
 * DATA MODES
 *  'real'      — Only real downloaded data; fails if unavailable
 *  'synthetic' — Only synthetic generated data
 *  'mixed'     — Real when available, synthetic with explicit labelling otherwise
 *
 * DOMAIN STATUS
 *  'available'    — Data present and usable
 *  'unavailable'  — Data absent; pipeline not yet implemented
 *  'synthetic'    — Only synthetic data loaded
 */

export const DATA_MODES = /** @type {const} */ ({
  REAL: 'real',
  SYNTHETIC: 'synthetic',
  MIXED: 'mixed',
});

export const DOMAIN_IDS = /** @type {const} */ ([
  'satellite_imagery',
  'shoreline_history',
  'terrain',
  'rainfall_weather',
  'ocean_conditions',
]);

/**
 * Annotate a record with provenance metadata.
 * @param {object} record
 * @param {string} domain
 * @param {boolean} synthetic
 * @param {string} [source]
 */
export function annotateProvenance(record, domain, synthetic, source = null) {
  return {
    ...record,
    _domain: domain,
    data_origin: synthetic ? 'SYNTHETIC' : 'REAL',
    synthetic,
    _source: source,
  };
}

/**
 * Spatial-temporal key for joining records from different domains.
 * Rounds lat/lon to 0.01° (~1 km) and date to day.
 */
export function spatialTemporalKey(lat, lon, dateStr) {
  const roundedLat = Math.round(lat * 100) / 100;
  const roundedLon = Math.round(lon * 100) / 100;
  const day = dateStr ? dateStr.slice(0, 10) : 'unknown';
  return `${roundedLat}_${roundedLon}_${day}`;
}

/**
 * Validate a domain record against its required fields.
 */
export function validateRecord(record, requiredFields) {
  const missing = requiredFields.filter(f => !(f in record) || record[f] === undefined);
  if (missing.length > 0) {
    console.warn(`[dataInterface] Record missing fields: ${missing.join(', ')}`);
    return false;
  }
  return true;
}

/**
 * Create a domain status object for the UI.
 */
export function domainStatus(id, status, dataMode, recordCount = 0, notes = '') {
  return { id, status, dataMode, recordCount, notes };
}
