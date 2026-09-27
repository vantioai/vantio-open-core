"use strict";

// PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

const POSTURE = Object.freeze([
  "PRIVATE",
  "INERT",
  "NOT_SHIPPED",
  "NO_LIVE_WRITER",
  "NO_LIVE_READER",
  "NO_MIGRATION",
  "NO_STABLE_SCHEMA",
]);

const AUDIENCE = "INTERNAL_RESTRICTED";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const UNICODE_PROFILE_ID = "PKG01-UCD-16.0.0";
const UNICODE_PROFILE_VERSION = "16.0.0";

const FROZEN_VERSIONS = Object.freeze({
  cli: "0.3.24",
  nodeSdk: "0.2.4",
  python: "3.1.0",
  evidenceContract: "0.0.0-unstable-pre-1.0",
  thisPackage: "0.0.0-unstable-pre-1.0",
});

const FUTURE_VERSION_PLACEHOLDER = "PKG02-FUTURE-CLI-UNASSIGNED";

const COMPATIBILITY_CLASSES = Object.freeze([
  "PARTIAL",
  "REQUIRES_ADAPTER",
  "UNSUPPORTED",
  "REJECT_WITH_EXPLANATION",
  "REQUIRES_ALIAS",
  "READ_ONLY",
  "NOT_YET_DECIDED",
  "FULL",
]);

const MAX_ALIAS_FANOUT = 8;
const MAX_ALIAS_WALK_DEPTH = 4;
const MAX_JSON_DEPTH = 32;

const REQUIRED_DIMENSIONS = Object.freeze([
  "schema_identity_status",
  "record_identity",
  "execution_identity",
  "process_identity",
  "timestamps_duration",
  "destination_provider_identity",
  "http_network_outcomes",
  "optics_health",
  "workload_outcome",
  "dependency_outcome",
  "issue_location",
  "evidence_origin_basis",
  "coverage",
  "completeness",
  "integrity",
  "sampling",
  "drop_state",
  "version_identity",
]);

const SEPARATED_DIMENSIONS = Object.freeze([
  "optics_health",
  "workload_outcome",
  "dependency_outcome",
  "coverage",
  "completeness",
  "integrity",
]);

const ADDITIONAL_DISJOINT_DIMENSIONS = Object.freeze([
  "http_network_outcomes",
  "attempt_lifecycle",
  "sampling",
  "drop_state",
  "observation_action",
  "evidence_origin_basis",
]);

module.exports = {
  ADDITIONAL_DISJOINT_DIMENSIONS,
  AUDIENCE,
  COMPATIBILITY_CLASSES,
  FROZEN_VERSIONS,
  FUTURE_VERSION_PLACEHOLDER,
  MAX_ALIAS_FANOUT,
  MAX_ALIAS_WALK_DEPTH,
  MAX_JSON_DEPTH,
  POSTURE,
  REQUIRED_DIMENSIONS,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  SEPARATED_DIMENSIONS,
  UNICODE_PROFILE_ID,
  UNICODE_PROFILE_VERSION,
};
