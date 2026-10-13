"use strict";

// Major 1 is additive only. A breaking change requires major 2 and a
// deprecation window of two minor releases of this exporter, during which
// 1.x events are still accepted.

const SCHEMA_ID = "vantio.observability.export";
const SCHEMA_VERSION = "1.0.0";
const SCHEMA_MAJOR = 1;
const SCOPE_NAME = "vantio.optics.export";

const COVERAGE = Object.freeze([
  "OBSERVED",
  "NOT_OBSERVED",
  "PARTIAL",
  "UNSUPPORTED",
  "UNKNOWN",
]);

const KINDS = Object.freeze([
  "optics.observation",
  "phantom.decision",
  "enterprise.evidence",
]);

const DECISIONS = Object.freeze(["ALLOW", "BLOCK"]);

function parseVersion(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(String(version || ""));
  if (!match) return null;
  return { major: Number(match[1]), minor: Number(match[2]), patch: Number(match[3]) };
}

function acceptsVersion(version) {
  const parsed = parseVersion(version);
  return Boolean(parsed && parsed.major === SCHEMA_MAJOR);
}

module.exports = {
  COVERAGE,
  DECISIONS,
  KINDS,
  SCHEMA_ID,
  SCHEMA_MAJOR,
  SCHEMA_VERSION,
  SCOPE_NAME,
  acceptsVersion,
  parseVersion,
};
