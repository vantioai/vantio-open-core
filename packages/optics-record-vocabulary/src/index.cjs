"use strict";

const { POSTURE } = require("./boundary.cjs");
const { canonicalJson } = require("./canonical-json.cjs");
const { comparisonDocument } = require("./comparison.cjs");
const { evaluateFixture, evaluateFixtures } = require("./evaluate-fixture.cjs");
const { loadFixtures, loadVocabulary } = require("./load.cjs");
const { inspectAliasGraph, validateVocabulary } = require("./validate-vocabulary.cjs");

module.exports = {
  POSTURE,
  canonicalJson,
  comparisonDocument,
  evaluateFixture,
  evaluateFixtures,
  inspectAliasGraph,
  loadFixtures,
  loadVocabulary,
  validateVocabulary,
};
