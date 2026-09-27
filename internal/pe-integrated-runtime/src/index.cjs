"use strict";

const boundary = require("./boundary.cjs");
const productHealth = require("./product-health.cjs");
const registers = require("./registers.cjs");
const runtime = require("./runtime.cjs");

module.exports = {
  AUDIENCE: boundary.AUDIENCE,
  COUNCIL_STATUS: boundary.COUNCIL_STATUS,
  INTEGRATION_REGISTER: registers.INTEGRATION_REGISTER,
  OPS: runtime.OPS,
  PLANES: boundary.PLANES,
  POSTURE: boundary.POSTURE,
  PRODUCER_CLASSIFICATION: boundary.PRODUCER_CLASSIFICATION,
  PRODUCT_HEALTH_CLASSIFICATION: productHealth.PRODUCER_CLASSIFICATION,
  PRODUCT_HEALTH_INTEGRATION_REGISTER: productHealth.INTEGRATION_REGISTER,
  PRODUCT_HEALTH_RUNTIME_REGISTER: productHealth.RUNTIME_REGISTER,
  PROGRESSIVE_STEPS: runtime.PROGRESSIVE_STEPS,
  RUNTIME_REGISTER: registers.RUNTIME_REGISTER,
  STARTING_REF: boundary.STARTING_REF,
  composeProductHealth: productHealth.composeProductHealth,
  createRuntime: runtime.createRuntime,
  integrate: runtime.integrate,
  integrateAll: runtime.integrateAll,
  productHealth: runtime.productHealth,
  sealChild: boundary.sealChild,
  snapshot: runtime.snapshot,
};
