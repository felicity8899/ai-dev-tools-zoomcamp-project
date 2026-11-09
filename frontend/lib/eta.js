/**
 * ETA formatting helpers for the TableNow SPA.
 * Pure functions, no DOM — unit-tested with node:test (see test/eta.test.mjs).
 */

/**
 * Human label for an estimated wait in minutes.
 * null/undefined (party can never be seated) -> "No table fits your party".
 */
export function formatEta(minutes) {
  if (minutes === null || minutes === undefined) {
    return "No table fits your party";
  }
  const m = Math.max(0, Math.round(minutes));
  if (m < 1) return "Seated any moment";
  if (m < 60) return `~${m} min`;
  const h = Math.floor(m / 60);
  const rest = m % 60;
  return rest === 0 ? `~${h} h` : `~${h} h ${rest} min`;
}

/** "Party of 4" / "Party of 1" label. */
export function partyLabel(size) {
  return size === 1 ? "Party of 1" : `Party of ${size}`;
}
