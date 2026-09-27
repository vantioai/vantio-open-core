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
const PACKAGE_VERSION = "0.0.0-unstable-pre-1.0";
const UNITS_D_E = "NOT_AUTHORIZED";
const ACHIEVEMENT = "NOT_SHIPPED";
const CLASSIFICATION_READY = "OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL";
const CLASSIFICATION_BLOCKED = "OPTICS_PKG02_READER_COMPAT_GATES_BLOCKED";
const FROZEN_CLI_VERSION = "0.3.24";
const FUTURE_CLI_PLACEHOLDER = "PKG02-FUTURE-CLI-UNASSIGNED";
const FUTURE_PYTHON_PLACEHOLDER = "PKG02-FUTURE-PYTHON-UNASSIGNED";

const GATE_IDS = Object.freeze([
  "mixed_version_directories",
  "legacy_records",
  "future_records",
  "unknown_statuses",
  "absent_fields",
  "origin_preservation",
  "reader_fallback",
  "no_unknown_to_success",
  "frozen_cli_honestly_unsupported",
  "rollback_without_record_rewriting",
  "reader_refuses_unsafe_promotion",
]);

const REQUIRED_ROLES = Object.freeze([
  "legacy_cli",
  "legacy_python",
  "future_canonical",
  "unknown_status",
  "absent_fields",
  "imported",
  "claimed_local",
  "simulated_demo",
  "newer_schema",
  "corrupt",
  "node_sdk",
  "future_field",
]);

const OPTICS_TOKENS = new Set([
  "OBSERVED",
  "NOT_OBSERVED",
  "UNSUPPORTED",
  "UNAVAILABLE",
  "APPLICATION_ERROR",
  "OPTICS_ERROR",
  "PARTIAL",
  "SUCCESS",
]);

const ORIGINS = new Set([
  "DERIVED_DIAGNOSTIC",
  "IMPORTED",
  "LEGACY_UNMARKED",
  "LOCAL_OBSERVATION",
  "PRODUCT_HEALTH",
  "SIMULATED_DEMO",
  "TEST_FIXTURE",
]);

const INPUT_CLASSES = new Set([
  "absent",
  "enum",
  "null",
  "refused_success",
  "unknown",
  "unreadable",
]);

const REASON_CODES = new Set([
  "ABSENT_FILE",
  "ENFORCEMENT_ACTION_EXCLUDED",
  "INPUT_CHANGED",
  "LEGACY_UNMARKED",
  "MALFORMED_JSON",
  "MALFORMED_UTF8",
  "OPTIMISTIC_DEFAULT_FORBIDDEN",
  "PATH_REFUSED",
  "PROMPT_COMPLETION_EXCLUDED",
  "PROVENANCE_INSUFFICIENT",
  "RECORD_TYPE_REJECTED",
  "SCHEMA_STATUS_CORRECTED",
  "UNKNOWN_FIELD_OMITTED",
  "UNREADABLE",
  "UNSUPPORTED",
  "WRITER_INACTIVE",
]);

const APPLICATION_TOKENS = new Set([
  "APPLICATION_ERROR",
  "NOT_OBSERVED",
  "SUCCESS",
  "UNAVAILABLE",
]);

const SAFE_NAME = /^[A-Za-z0-9._-]{1,80}$/;
const SAFE_SCHEMA_STATUS = /^[A-Za-z0-9._+-]{1,32}$/;

const PROHIBITED_ECHOES = Object.freeze([
  "\"prompt\"",
  "freshness",
  "widget_hint",
  "est_spend_usd",
  "\"cost\"",
  "\"plane\"",
  "\"machine\"",
]);

module.exports = {
  ACHIEVEMENT,
  APPLICATION_TOKENS,
  AUDIENCE,
  CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY,
  FROZEN_CLI_VERSION,
  FUTURE_CLI_PLACEHOLDER,
  FUTURE_PYTHON_PLACEHOLDER,
  GATE_IDS,
  INPUT_CLASSES,
  OPTICS_TOKENS,
  ORIGINS,
  PACKAGE_VERSION,
  POSTURE,
  PROHIBITED_ECHOES,
  REASON_CODES,
  REQUIRED_ROLES,
  SAFE_NAME,
  SAFE_SCHEMA_STATUS,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  UNITS_D_E,
};
