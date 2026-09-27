"use strict";

const boundary = require("./boundary.cjs");
const registers = require("./registers.cjs");
const compose = require("./compose.cjs");

module.exports = {
  AUDIENCE: boundary.AUDIENCE,
  CITED_REQUIREMENTS: boundary.CITED_REQUIREMENTS,
  COUNCIL_STATUS: boundary.COUNCIL_STATUS,
  INTEGRATION_REGISTER: registers.INTEGRATION_REGISTER,
  MODULE_VERSION: boundary.MODULE_VERSION,
  OPS: compose.OPS,
  PLANES: boundary.PLANES,
  POSTURE: boundary.POSTURE,
  PRODUCER_CLASSIFICATION: boundary.PRODUCER_CLASSIFICATION,
  PRODUCER_ID: boundary.PRODUCER_ID,
  PRODUCER_URL: boundary.PRODUCER_URL,
  RUNTIME_REGISTER: registers.RUNTIME_REGISTER,
  STARTING_REF: boundary.STARTING_REF,
  STATUS: registers.STATUS,
  WAVE2_CLOSE: boundary.WAVE2_CLOSE,
  compose: compose.compose,
  createComposition: compose.createComposition,
  integrate: compose.integrate,
  integrateAll: compose.integrateAll,
  sealEnterpriseChild: boundary.sealEnterpriseChild,
  snapshot: compose.snapshot,
};
