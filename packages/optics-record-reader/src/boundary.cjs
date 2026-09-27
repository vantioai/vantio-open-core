"use strict";

// PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

const POSTURE = Object.freeze([
  "PRIVATE",
  "INERT",
  "NOT_SHIPPED",
  "READ_AND_EXPLAIN",
  "NO_WRITE_BACK",
  "NO_LIVE_WRITER",
  "NO_MIGRATION",
  "NO_STABLE_SCHEMA",
]);

const AUDIENCE = "INTERNAL_RESTRICTED";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const READER_VERSION = "0.0.0-unstable-pre-1.0";
const READER_NAME = "@vantio/optics-record-reader";
const FUTURE_CLI_PLACEHOLDER = "PKG02-FUTURE-CLI-UNASSIGNED";
const FUTURE_PYTHON_PLACEHOLDER = "PKG02-FUTURE-PYTHON-UNASSIGNED";
const UNITS_D_E = "NOT_AUTHORIZED";
const UNICODE_PROFILE_ID = "PKG01-UCD-16.0.0";

const OPTICS_GLOSS = Object.freeze({
  APPLICATION_ERROR: "Application error",
  NOT_OBSERVED: "Not observed",
  OBSERVED: "Observed",
  OPTICS_ERROR: "Optics error",
  PARTIAL: "Partial",
  UNAVAILABLE: "Unavailable",
  UNSUPPORTED: "Unsupported",
});

const APPLICATION_GLOSS = Object.freeze({
  APPLICATION_ERROR: "Application error",
  NOT_OBSERVED: "Not observed",
  SUCCESS: "Successful",
  UNAVAILABLE: "Unavailable",
});

const ORIGIN_GLOSS = Object.freeze({
  DERIVED_DIAGNOSTIC: "Derived diagnostic",
  IMPORTED: "Imported",
  LEGACY_UNMARKED: "Legacy unmarked",
  LOCAL_OBSERVATION: "Local observation",
  PRODUCT_HEALTH: "Product health",
  SIMULATED_DEMO: "Simulated demo",
  TEST_FIXTURE: "Test fixture",
});

const OPTICS_ENUM = new Set(Object.keys(OPTICS_GLOSS));

const ALLOWED_NOTES = new Set([
  "comma-joined mediation omitted",
  "ended_at is file write time taken from generated_at",
  "failure_kind none omitted",
  "IMPORTED origin preserved",
  "inherited trace basis is ASSERTED_CONTEXT",
  "invalid method omitted",
  "invalid sampling omitted",
  "omitted span stays omitted",
  "optics token refused",
  "pre-completion duration omitted",
]);

const SAFE_NAME = /^[A-Za-z0-9._-]{1,80}$/;

const WRITER_FLAGS = Object.freeze([
  "activate",
  "emit",
  "migrate",
  "publish",
  "seal",
  "sqlite",
  "write",
]);

module.exports = {
  ALLOWED_NOTES,
  APPLICATION_GLOSS,
  AUDIENCE,
  FUTURE_CLI_PLACEHOLDER,
  FUTURE_PYTHON_PLACEHOLDER,
  OPTICS_ENUM,
  OPTICS_GLOSS,
  ORIGIN_GLOSS,
  POSTURE,
  READER_NAME,
  READER_VERSION,
  SAFE_NAME,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  UNICODE_PROFILE_ID,
  UNITS_D_E,
  WRITER_FLAGS,
};
