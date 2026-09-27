"use strict";

const fs = require("node:fs");
const path = require("node:path");

const {
  CITED_REQUIREMENTS,
  COUNCIL_STATUS,
  HONESTY_FIELDS,
  POSTURE,
  PREFERRED_EXECUTION,
  PRODUCER_CLASSIFICATION,
  STARTING_REF,
} = require("./boundary.cjs");

const REGISTER_DIR = path.join(__dirname, "../../../docs/internal/wave3/enterprise-runtime");
const PROGRAM_DIR = path.join(__dirname, "../../../docs/programs/production-readiness/wave3");

const ALLOWED_ROW_EXECUTION = new Set([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
  "NOT_PERFORMED",
]);

const PAIRS = Object.freeze([
  ["RUNTIME-REGISTER.json", "ENTERPRISE-RUNTIME-REGISTER.json"],
  ["INTEGRATION-REGISTER.json", "ENTERPRISE-INTEGRATION-REGISTER.json"],
  ["STATUS.json", "ENTERPRISE-RUNTIME-STATUS.json"],
]);

function loadJson(dir, name) {
  return JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
}

function assertPair(internalName, programName) {
  const left = fs.readFileSync(path.join(REGISTER_DIR, internalName), "utf8");
  const right = fs.readFileSync(path.join(PROGRAM_DIR, programName), "utf8");
  if (left !== right) throw new Error("register drift " + internalName);
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
  for (const [id, state] of Object.entries(CITED_REQUIREMENTS)) {
    if (!doc.requirements_cited || doc.requirements_cited[id] !== state) {
      throw new Error(label + " requirement " + id);
    }
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
    if (row.live_customer_authority !== false) throw new Error("row live_customer_authority " + row.id);
    if (row.customer_authority_promoted !== false) throw new Error("row customer_authority_promoted " + row.id);
    if (!Array.isArray(row.planes_not_applied) || row.planes_not_applied.length < 1) {
      throw new Error("row planes_not_applied " + row.id);
    }
    if (!row.planes_not_applied.includes("HOST_ENFORCEMENT")) {
      throw new Error("row host plane " + row.id);
    }
    if (!row.planes_not_applied.includes("APPLICATION_ENFORCEMENT")) {
      throw new Error("row application plane " + row.id);
    }
  }
}

for (const [internalName, programName] of PAIRS) assertPair(internalName, programName);

const RUNTIME_REGISTER = loadJson(REGISTER_DIR, "RUNTIME-REGISTER.json");
const INTEGRATION_REGISTER = loadJson(REGISTER_DIR, "INTEGRATION-REGISTER.json");
const STATUS = loadJson(REGISTER_DIR, "STATUS.json");
assertHonesty(RUNTIME_REGISTER, "RUNTIME-REGISTER");
assertHonesty(INTEGRATION_REGISTER, "INTEGRATION-REGISTER");
assertHonesty(STATUS, "STATUS");
assertRows(INTEGRATION_REGISTER.rows);

module.exports = {
  INTEGRATION_REGISTER,
  REGISTER_DIR,
  RUNTIME_REGISTER,
  STATUS,
};
