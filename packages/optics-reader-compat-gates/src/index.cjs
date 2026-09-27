"use strict";

const boundary = require("./boundary.cjs");
const { evaluateEntryGates } = require("./gates.cjs");

module.exports = {
  ACHIEVEMENT: boundary.ACHIEVEMENT,
  AUDIENCE: boundary.AUDIENCE,
  CLASSIFICATION_BLOCKED: boundary.CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY: boundary.CLASSIFICATION_READY,
  FROZEN_CLI_VERSION: boundary.FROZEN_CLI_VERSION,
  FUTURE_CLI_PLACEHOLDER: boundary.FUTURE_CLI_PLACEHOLDER,
  FUTURE_PYTHON_PLACEHOLDER: boundary.FUTURE_PYTHON_PLACEHOLDER,
  GATE_IDS: boundary.GATE_IDS,
  PACKAGE_VERSION: boundary.PACKAGE_VERSION,
  POSTURE: boundary.POSTURE,
  REQUIRED_ROLES: boundary.REQUIRED_ROLES,
  SCHEMA_STATUS: boundary.SCHEMA_STATUS,
  SCHEMA_VERSION: boundary.SCHEMA_VERSION,
  UNITS_D_E: boundary.UNITS_D_E,
  evaluateEntryGates,
};
