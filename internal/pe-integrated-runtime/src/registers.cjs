"use strict";

const path = require("node:path");

const {
  COUNCIL_STATUS,
  HONESTY_FIELDS,
  POSTURE,
  PREFERRED_EXECUTION,
  PRODUCER_CLASSIFICATION,
  STARTING_REF,
} = require("./boundary.cjs");

const REGISTER_DIR = path.join(__dirname, "../../../docs/internal/wave3/pe-integration");

const ALLOWED_ROW_EXECUTION = new Set([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
  "NOT_PERFORMED",
]);

function loadJson(name) {
  return require(path.join(REGISTER_DIR, name));
}

function assertHonesty(doc, label) {
  if (doc.producer_classification !== PRODUCER_CLASSIFICATION) {
    throw new Error(label + " producer_classification");
  }
  if (doc.council_status !== COUNCIL_STATUS) throw new Error(label + " council_status");
  if (doc.council_verdict !== null) throw new Error(label + " council_verdict");
  if (doc.self_certified_council_pass !== false) throw new Error(label + " self_certified_council_pass");
  if (doc.starting_ref !== STARTING_REF) throw new Error(label + " starting_ref");
  if (doc.audience !== "INTERNAL_RESTRICTED") throw new Error(label + " audience");
  for (const field of HONESTY_FIELDS) {
    if (doc[field] !== POSTURE[field]) throw new Error(label + " honesty " + field);
  }
  if (JSON.stringify(doc.preferred_execution) !== JSON.stringify(PREFERRED_EXECUTION)) {
    throw new Error(label + " preferred_execution");
  }
}

function assertRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) throw new Error("integration rows missing");
  const ids = new Set();
  for (const row of rows) {
    if (ids.has(row.id)) throw new Error("duplicate integration row " + row.id);
    ids.add(row.id);
    if (!ALLOWED_ROW_EXECUTION.has(row.execution)) throw new Error("row execution " + row.id);
    if (row.host_attachment !== false) throw new Error("row host_attachment " + row.id);
    if (row.kernel_executed !== false) throw new Error("row kernel_executed " + row.id);
    if (row.active_protection !== false) throw new Error("row active_protection " + row.id);
    if (!Array.isArray(row.planes_not_applied) || row.planes_not_applied.length < 1) {
      throw new Error("row planes_not_applied " + row.id);
    }
  }
}

const RUNTIME_REGISTER = loadJson("RUNTIME-REGISTER.json");
const INTEGRATION_REGISTER = loadJson("INTEGRATION-REGISTER.json");
assertHonesty(RUNTIME_REGISTER, "RUNTIME-REGISTER");
assertHonesty(INTEGRATION_REGISTER, "INTEGRATION-REGISTER");
assertRows(INTEGRATION_REGISTER.rows);

module.exports = {
  INTEGRATION_REGISTER,
  REGISTER_DIR,
  RUNTIME_REGISTER,
};
