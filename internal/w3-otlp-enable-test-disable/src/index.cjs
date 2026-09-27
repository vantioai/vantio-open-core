"use strict";

const {
  HARNESS_ENDPOINT,
  PRODUCER_CLASSIFICATION,
} = require("./boundary.cjs");
const { runEnableTestDisable } = require("./cycle.cjs");
const { REST_REGISTER } = require("./registers.cjs");
const { assertRestDisabled, restState } = require("./rest.cjs");

assertRestDisabled(restState());

module.exports = {
  HARNESS_ENDPOINT,
  PRODUCER_CLASSIFICATION,
  REST_REGISTER,
  restState,
  runEnableTestDisable,
};
