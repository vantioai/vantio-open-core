"use strict";

const boundary = require("./boundary.cjs");
const { adaptFixture, adaptNodeCopy } = require("./adapt.cjs");

module.exports = {
  ADAPTER_VERSION: boundary.ADAPTER_VERSION,
  AUDIENCE: boundary.AUDIENCE,
  FUTURE_CLI_PLACEHOLDER: boundary.FUTURE_CLI_PLACEHOLDER,
  POSTURE: boundary.POSTURE,
  SCHEMA_STATUS: boundary.SCHEMA_STATUS,
  SCHEMA_VERSION: boundary.SCHEMA_VERSION,
  UNICODE_PROFILE_ID: boundary.UNICODE_PROFILE_ID,
  adaptFixture,
  adaptNodeCopy,
};
