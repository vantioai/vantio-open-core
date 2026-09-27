"use strict";

const boundary = require("./boundary.cjs");
const { explainCopy, explainFixture, readRunFile } = require("./explain.cjs");

module.exports = {
  AUDIENCE: boundary.AUDIENCE,
  FUTURE_CLI_PLACEHOLDER: boundary.FUTURE_CLI_PLACEHOLDER,
  FUTURE_PYTHON_PLACEHOLDER: boundary.FUTURE_PYTHON_PLACEHOLDER,
  POSTURE: boundary.POSTURE,
  READER_NAME: boundary.READER_NAME,
  READER_VERSION: boundary.READER_VERSION,
  SCHEMA_STATUS: boundary.SCHEMA_STATUS,
  SCHEMA_VERSION: boundary.SCHEMA_VERSION,
  UNICODE_PROFILE_ID: boundary.UNICODE_PROFILE_ID,
  UNITS_D_E: boundary.UNITS_D_E,
  explainCopy,
  explainFixture,
  readRunFile,
};
