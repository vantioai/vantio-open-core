"use strict";

const { AUDIENCE, DIMENSIONS, RESULT_LIST, VOCABULARY_ID } = require("./vocabulary.cjs");
const { listPaths, PATHS } = require("./paths.cjs");
const { evaluate } = require("./evaluate.cjs");

const POSTURE = Object.freeze([
  "PRIVATE",
  "NOT_SHIPPED",
  "INTERNAL_PROOF",
  "NO_LIVE_ATTACH",
  "NO_EBPF_LOAD",
  "NO_NETWORK",
  "NO_CUSTOMER_DEPLOY",
]);

module.exports = {
  AUDIENCE,
  DIMENSIONS,
  PATHS,
  POSTURE,
  RESULT_LIST,
  VOCABULARY_ID,
  evaluate,
  listPaths,
};
