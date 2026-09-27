"use strict";

const { LIMITS, POSTURE, SIGNALS } = require("./boundary.cjs");
const { evaluateRecords } = require("./authority.cjs");
const { exportOpticsRecords } = require("./deliver.cjs");
const { parseCustomerEndpoint } = require("./endpoint.cjs");

function adapterStatus() {
  return Object.freeze({
    ...POSTURE,
    active: false,
    network_on_load: false,
    signals: SIGNALS,
    limits: LIMITS,
  });
}

module.exports = {
  LIMITS,
  POSTURE,
  adapterStatus,
  evaluateRecords,
  exportOpticsRecords,
  parseCustomerEndpoint,
};
