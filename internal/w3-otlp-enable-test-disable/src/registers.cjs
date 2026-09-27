"use strict";

const fs = require("node:fs");
const path = require("node:path");

const {
  COUNCIL_STATUS,
  HARNESS_REGISTER,
  PRODUCER,
  PRODUCER_CLASSIFICATION,
  REST_FIELDS,
  SIGNALS_AT_REST,
  STARTING_REF,
} = require("./boundary.cjs");
const { freezeDeep, restState, restIsDisabled } = require("./rest.cjs");

const INTERNAL_REGISTER = path.join(
  __dirname,
  "../../../docs/internal/wave3/otlp-enable-test-disable/REST-REGISTER.json",
);
const PROGRAM_REGISTER = path.join(
  __dirname,
  "../../../docs/programs/production-readiness/wave3/OTLP-REST-REGISTER.json",
);

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function assertRegister(doc) {
  if (!doc || typeof doc !== "object") throw new Error("OTLP rest register missing");
  if (doc.document !== "W3_OTLP_REST_REGISTER") throw new Error("OTLP rest register document");
  if (doc.producer_classification !== PRODUCER_CLASSIFICATION) {
    throw new Error("OTLP rest register producer_classification");
  }
  if (doc.council_status !== COUNCIL_STATUS) throw new Error("OTLP rest register council_status");
  if (doc.council_verdict !== null) throw new Error("OTLP rest register council_verdict");
  if (doc.self_certified_council_pass !== false) throw new Error("OTLP rest register self_certified");
  if (doc.starting_ref !== STARTING_REF) throw new Error("OTLP rest register starting_ref");
  if (doc.audience !== "INTERNAL_RESTRICTED") throw new Error("OTLP rest register audience");
  if (doc.producer !== PRODUCER.id) throw new Error("OTLP rest register producer");
  if (doc.producer_url !== PRODUCER.url) throw new Error("OTLP rest register producer_url");
  if (doc.schema_status !== "unstable-pre-1.0") throw new Error("OTLP rest register schema_status");
  if (doc.stable_schema !== false) throw new Error("OTLP rest register stable_schema");
  if (doc.schema_url !== null) throw new Error("OTLP rest register schema_url");
  if (doc.adapter_council !== "PENDING_COUNCIL") throw new Error("OTLP rest register adapter_council");
  for (const key of Object.keys(REST_FIELDS)) {
    if (doc[key] !== REST_FIELDS[key]) throw new Error("OTLP rest register " + key);
  }
  if (!sameJson(doc.signals_at_rest, SIGNALS_AT_REST)) {
    throw new Error("OTLP rest register signals_at_rest");
  }
  if (!sameJson(doc.harness, HARNESS_REGISTER)) throw new Error("OTLP rest register harness");
  const live = restState();
  if (!restIsDisabled(live)) throw new Error("OTLP rest register live adapter is enabled");
  if (doc.default_enabled !== live.default_enabled) throw new Error("OTLP rest register default drift");
  if (doc.public_shipped_support !== live.public_shipped_support) {
    throw new Error("OTLP rest register public_shipped_support drift");
  }
  if (doc.founder_decision_12 !== live.founder_decision_12) {
    throw new Error("OTLP rest register founder_decision_12 drift");
  }
  if (doc.i3_status !== live.i3_status) throw new Error("OTLP rest register i3_status drift");
  if (!sameJson(doc.adapter_signal_labels, live.signals)) {
    throw new Error("OTLP rest register adapter_signal_labels");
  }
  if (doc.mapping.mapping_id !== live.mapping_id) throw new Error("OTLP rest register mapping_id");
  if (doc.mapping.mapping_version !== live.mapping_version) {
    throw new Error("OTLP rest register mapping_version");
  }
  if (doc.mapping.i3_status !== "NOT_AUTHORIZED") throw new Error("OTLP rest register mapping i3");
  if (doc.mapping.adapters_default_enabled !== false) {
    throw new Error("OTLP rest register mapping adapters");
  }
  if (doc.mapping.public_shipped_support !== false) {
    throw new Error("OTLP rest register mapping public support");
  }
}

function loadRestRegister() {
  const internalText = fs.readFileSync(INTERNAL_REGISTER, "utf8");
  const programText = fs.readFileSync(PROGRAM_REGISTER, "utf8");
  if (internalText !== programText) throw new Error("OTLP rest registers differ");
  const doc = JSON.parse(internalText);
  assertRegister(doc);
  return freezeDeep(doc);
}

const REST_REGISTER = loadRestRegister();

module.exports = {
  INTERNAL_REGISTER,
  PROGRAM_REGISTER,
  REST_REGISTER,
};
