"use strict";

const contract = require("../contract.json");
const { evaluateFact, loadCatalog } = require("./catalog.cjs");
const { consume } = require("./consume.cjs");
const { produce } = require("./produce.cjs");

function consumeFact(fact, input = {}, options = {}) {
  const extra = input && typeof input === "object" ? { ...input } : {};
  delete extra.facts;
  return produce({ ...extra, facts: [fact] }, options);
}

module.exports = {
  AUDIENCE: contract.audience,
  CATALOG_COMMIT: contract.catalog_commit,
  COMPONENTS: Object.freeze(contract.components.slice()),
  FAILURE_CLASSIFICATIONS: Object.freeze(contract.failure_classifications.slice()),
  PRODUCER_CLASSIFICATION: contract.producer_classification,
  REQUIRED_FIELDS: Object.freeze(contract.required_fields.slice()),
  RUNTIME_NAME: contract.runtime_name,
  RUNTIME_VERSION: contract.runtime_version,
  STATES: Object.freeze(contract.states.slice()),
  consume,
  consumeFact,
  evaluateFact,
  loadCatalog,
  produce,
};
