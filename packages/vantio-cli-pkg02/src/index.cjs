"use strict";

const boundary = require("./boundary.cjs");
const { proveAdapterByteIdentity, proveUnknownOpticsNotSuccess } = require("./prerequisites.cjs");
const { composeCanonical } = require("./record.cjs");
const { explainCanonical, readRolledBack } = require("./rollback-reader.cjs");
const { writerEnabled } = require("./writer.cjs");

module.exports = {
  AUDIENCE: boundary.AUDIENCE,
  FUTURE_CLI_VERSION: boundary.FUTURE_CLI_VERSION,
  FROZEN_CLI_VERSION: boundary.FROZEN_CLI_VERSION,
  PRODUCER: boundary.PRODUCER,
  SCHEMA_STATUS: boundary.SCHEMA_STATUS,
  SCHEMA_VERSION: boundary.SCHEMA_VERSION,
  UNICODE_PROFILE_ID: boundary.UNICODE_PROFILE_ID,
  activates_unit_d: true,
  activates_unit_e: false,
  composeCanonical,
  explainCanonical,
  proveAdapterByteIdentity,
  proveUnknownOpticsNotSuccess,
  readRolledBack,
  shipped_product: false,
  writerEnabled,
};
