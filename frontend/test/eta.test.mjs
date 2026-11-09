import { test } from "node:test";
import assert from "node:assert/strict";

import { formatEta, partyLabel } from "../lib/eta.js";

test("null ETA means no table can seat the party", () => {
  assert.equal(formatEta(null), "No table fits your party");
  assert.equal(formatEta(undefined), "No table fits your party");
});

test("under a minute reads as immediate", () => {
  assert.equal(formatEta(0), "Seated any moment");
  assert.equal(formatEta(0.4), "Seated any moment");
});

test("minutes under an hour", () => {
  assert.equal(formatEta(1), "~1 min");
  assert.equal(formatEta(12.4), "~12 min");
  assert.equal(formatEta(45), "~45 min");
});

test("hours and minutes combine", () => {
  assert.equal(formatEta(60), "~1 h");
  assert.equal(formatEta(95), "~1 h 35 min");
  assert.equal(formatEta(130), "~2 h 10 min");
});

test("negative input clamps to zero", () => {
  assert.equal(formatEta(-5), "Seated any moment");
});

test("party label", () => {
  assert.equal(partyLabel(1), "Party of 1");
  assert.equal(partyLabel(4), "Party of 4");
});
