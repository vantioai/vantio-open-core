"use strict";

// PRIVATE store facade. Node does not select a SQLite binding.
// Writer flags match the PKG-02 inactive list as data. This file does not import that package.

const POSTURE = Object.freeze([
  "PRIVATE",
  "NOT_SHIPPED",
  "NO_DEFAULT_WRITE_PATH",
  "NO_LIVE_WRITER",
  "NO_CLI_REOPEN",
  "NO_CUSTOMER_MIGRATION",
  "NO_STABLE_SCHEMA",
  "NODE_BINDING_UNSELECTED",
]);

const AUDIENCE = "INTERNAL_RESTRICTED";
const SCHEMA_STATUS = "unstable-pre-1.0";
const PACKAGE_VERSION = "0.0.0-unstable-pre-1.0";
const OPERATIONAL_SCHEMA_VERSION = 1;
const PRIVACY_GENERATION = 1;
const EVIDENCE_TIER = "UNSET";
const NODE_BINDING = "UNSELECTED";
const FOUNDER_DECISION_9 = "UNRESOLVED";
const REASON_NODE_BINDING = "NODE_BINDING_UNSELECTED";

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
  EVIDENCE_TIER,
  FOUNDER_DECISION_9,
  NODE_BINDING,
  OPERATIONAL_SCHEMA_VERSION,
  PACKAGE_VERSION,
  PKG02_WRITER_FLAGS,
  POSTURE,
  PRIVACY_GENERATION,
  REASON_NODE_BINDING,
  SCHEMA_STATUS,
};
