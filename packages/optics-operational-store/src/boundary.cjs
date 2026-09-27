"use strict";

// PRIVATE store facade. The selected Node binding is node:sqlite@24.15.0.
// Writer flags match the PKG-02 inactive list as data. This file does not import that package.
// Loading the builtin is gated in runtime-gate.cjs. This file does not load it.

const POSTURE = Object.freeze([
  "PRIVATE",
  "NOT_SHIPPED",
  "NO_DEFAULT_WRITE_PATH",
  "NO_LIVE_WRITER",
  "NO_CLI_REOPEN",
  "NO_CUSTOMER_MIGRATION",
  "NO_STABLE_SCHEMA",
  "NODE_BINDING_SELECTED",
]);

const AUDIENCE = "INTERNAL_RESTRICTED";
const SCHEMA_STATUS = "unstable-pre-1.0";
const PACKAGE_VERSION = "0.0.0-unstable-pre-1.0";
const OPERATIONAL_SCHEMA_VERSION = 1;
const PRIVACY_GENERATION = 1;
const EVIDENCE_TIER = "UNSET";
const NODE_BINDING = "node:sqlite@24.15.0";
const FOUNDER_DECISION_9 = "SELECTED";
const REASON_NODE_BINDING_CANNOT_LOAD = "NODE_BINDING_CANNOT_LOAD";
const CLASSIFICATION = "O7_RUNTIME_INTEGRATION_READY_FOR_COUNCIL";

const PKG02_WRITER_FLAGS = Object.freeze([
  "activate",
  "emit",
  "migrate",
  "publish",
  "seal",
  "sqlite",
  "write",
]);

module.exports = {
  AUDIENCE,
  CLASSIFICATION,
  EVIDENCE_TIER,
  FOUNDER_DECISION_9,
  NODE_BINDING,
  OPERATIONAL_SCHEMA_VERSION,
  PACKAGE_VERSION,
  PKG02_WRITER_FLAGS,
  POSTURE,
  PRIVACY_GENERATION,
  REASON_NODE_BINDING_CANNOT_LOAD,
  SCHEMA_STATUS,
};
