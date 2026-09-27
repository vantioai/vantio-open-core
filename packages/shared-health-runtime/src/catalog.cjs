"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const contract = require("../contract.json");

const REPO_ROOT = path.resolve(__dirname, "../../..");
const DEFAULT_CATALOG_PATH = path.join(
  REPO_ROOT,
  "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json",
);
const DEFAULT_PE_PACKET_PATH = path.join(
  REPO_ROOT,
  "docs/planning/phantom-engine-production/HEALTH-VOCABULARY.json",
);

function isPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

function readJsonFile(filePath) {
  const text = fs.readFileSync(filePath);
  const digest = crypto.createHash("sha256").update(text).digest("hex");
  return { json: JSON.parse(text.toString("utf8")), digest };
}

function loadCatalog(options = {}) {
  const catalogPath = options.catalogPath || DEFAULT_CATALOG_PATH;
  const pePacketPath = options.pePacketPath || DEFAULT_PE_PACKET_PATH;
  let catalogFile;
  let peFile;
  try {
    catalogFile = readJsonFile(catalogPath);
    peFile = readJsonFile(pePacketPath);
  } catch (error) {
    return {
      ok: false,
      errors: ["CATALOG_UNREADABLE"],
      limitation: "The bound shared health catalog could not be read. No health token was inferred.",
      detail: error instanceof Error ? error.message : "unreadable",
    };
  }

  const catalog = catalogFile.json;
  const pe = peFile.json;
  const errors = [];
  if (options.catalogPath === undefined && catalogFile.digest !== contract.catalog_sha256) {
    errors.push("CATALOG_BINDING_MISMATCH");
  }
  if (options.pePacketPath === undefined && peFile.digest !== contract.pe_packet_sha256) {
    errors.push("CATALOG_BINDING_MISMATCH");
  }
  if (!isPlainObject(pe) || !isPlainObject(pe.binding) || !isPlainObject(catalog)) {
    errors.push("CATALOG_BINDING_MISMATCH");
  } else {
    if (pe.vocabulary_status !== contract.catalog_commit) errors.push("CATALOG_BINDING_MISMATCH");
    if (pe.workstream_4 !== contract.catalog_commit) errors.push("CATALOG_BINDING_MISMATCH");
    if (pe.binding.catalog_commit !== contract.catalog_commit) errors.push("CATALOG_BINDING_MISMATCH");
    if (pe.binding.vocabulary_status_meaning !== contract.vocabulary_status_meaning) {
      errors.push("CATALOG_BINDING_MISMATCH");
    }
    if (pe.binding.workstream_4_meaning !== contract.workstream_4_meaning) {
      errors.push("CATALOG_BINDING_MISMATCH");
    }
    if (!isPlainObject(catalog.freshness) || catalog.freshness.rule_id !== contract.freshness_rule) {
      errors.push("CATALOG_BINDING_MISMATCH");
    }
  }
  if (errors.length > 0) {
    return {
      ok: false,
      errors: [...new Set(errors)],
      limitation: "The shared health catalog binding did not match the pinned commit. No health token was inferred.",
    };
  }
  return { ok: true, catalog, pe, errors: [] };
}

function evaluateFact(fact, catalog) {
  const errors = [];
  if (!isPlainObject(fact) || !isPlainObject(catalog)) {
    return ["FACT_SHAPE"];
  }
  const fields = catalog.fields;
  if (!isPlainObject(fields) || !isPlainObject(catalog.fact_rules)) {
    return ["FACT_SHAPE"];
  }
  if (fact.record_type !== "SHARED_HEALTH_FACT") errors.push("RECORD_TYPE");
  if (!Array.isArray(catalog.subjects) || !catalog.subjects.includes(fact.subject)) errors.push("SUBJECT_ENUM");
  if (!Array.isArray(catalog.fact_kinds) || !catalog.fact_kinds.includes(fact.fact_kind)) {
    errors.push("FACT_KIND_ENUM");
  }
  if (fact.freshness !== "UNKNOWN") errors.push("FRESHNESS_EMITTED");

  for (const [field, gate] of Object.entries(catalog.fact_rules.field_gates)) {
    if (!isPlainObject(gate)) {
      errors.push("FACT_SHAPE");
      continue;
    }
    const value = fact[field];
    if (fact.fact_kind === gate.fact_kind) {
      if (Array.isArray(gate.subjects) && !gate.subjects.includes(fact.subject)) errors.push(gate.subject_error);
      if (Object.prototype.hasOwnProperty.call(gate, "exact") && value !== gate.exact) errors.push(gate.exact_error);
      if (gate.enum_field && !fields[gate.enum_field].values.includes(value)) errors.push(gate.enum_error);
    } else if (value !== null) {
      errors.push(gate.null_error);
    }
  }

  for (const [field, code] of Object.entries(catalog.fact_rules.optional_enums)) {
    const value = fact[field];
    if (value !== null && !fields[field].values.includes(value)) errors.push(code);
  }

  const control = catalog.fact_rules.control_plane;
  if (isPlainObject(control)) {
    if (fact.fact_kind === control.fact_kind) {
      if (fact.subject !== control.subject) errors.push(control.subject_error);
      if (fact.interval_s !== control.interval_s) errors.push(control.interval_error);
    } else if (fact.interval_s !== null) {
      errors.push(control.null_error);
    }
  } else {
    errors.push("FACT_SHAPE");
  }

  if (Object.prototype.hasOwnProperty.call(fact, "coverage_percent")) errors.push("COVERAGE_PERCENT_FORBIDDEN");
  if (Object.prototype.hasOwnProperty.call(fact, "customer_validation")) errors.push("CUSTOMER_VALIDATION_FORBIDDEN");
  if (fact.platform_status === "proved" || fact.proved === true) errors.push("PROVED_TOKEN_FORBIDDEN");

  return [...new Set(errors)].sort();
}

module.exports = {
  DEFAULT_CATALOG_PATH,
  DEFAULT_PE_PACKET_PATH,
  evaluateFact,
  isPlainObject,
  loadCatalog,
};
