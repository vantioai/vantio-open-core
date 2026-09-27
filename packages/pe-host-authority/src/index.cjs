"use strict";

const { PRODUCER_CLASSIFICATION, FIXTURE_HOST, SURFACES, CLAIMS } = require("./catalog.cjs");
const { evaluate } = require("./evaluate.cjs");
const { prove, runPureCases } = require("./prove.cjs");
const { collectHostFacts } = require("./host-facts.cjs");
const { CASES } = require("./cases.cjs");

module.exports = {
  PRODUCER_CLASSIFICATION,
  FIXTURE_HOST,
  SURFACES,
  CLAIMS,
  CASES,
  evaluate,
  prove,
  runPureCases,
  collectHostFacts,
};
