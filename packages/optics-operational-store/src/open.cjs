"use strict";

const os = require("node:os");
const path = require("node:path");

const boundary = require("./boundary.cjs");

function evidenceRoot(explicit) {
  if (typeof explicit === "string" && explicit.length > 0) return path.resolve(explicit);
  if (typeof process.env.VANTIO_HOME === "string" && process.env.VANTIO_HOME.length > 0) {
    return path.resolve(process.env.VANTIO_HOME);
  }
  return path.join(os.homedir(), ".vantio");
}

function detach(value) {
  if (value === undefined) return null;
  try {
    return structuredClone(value);
  } catch {
    return null;
  }
}

function stopped(reason, applicationResult) {
  return {
    application_continues: true,
    application_result: detach(applicationResult),
    default_write_path: false,
    evidence_tier: boundary.EVIDENCE_TIER,
    file_created: false,
    founder_decision_9: boundary.FOUNDER_DECISION_9,
    node_binding: boundary.NODE_BINDING,
    opened: false,
    reason_code: reason,
    record: null,
    records: [],
    rows: [],
    schema_status: boundary.SCHEMA_STATUS,
    stored: false,
    writes_enabled: false,
  };
}

function sqlRejected(options) {
  if (!options || typeof options !== "object") return false;
  if (Object.prototype.hasOwnProperty.call(options, "sql")) return true;
  if (Object.prototype.hasOwnProperty.call(options, "statement")) return true;
  return false;
}

function openStore(options) {
  const settings = options && typeof options === "object" ? options : {};
  if (typeof options === "string" || sqlRejected(settings)) {
    return stopped("SQL_REJECTED", settings.applicationResult);
  }
  const root = evidenceRoot(settings.evidenceRoot);
  const result = stopped(boundary.REASON_NODE_BINDING, settings.applicationResult);
  result.evidence_root = root;
  result.store_path = path.join(root, "optics", "store.sqlite");
  result.pkg02_flags_ignored = true;
  return result;
}

function put(handle, record, options) {
  const settings = options && typeof options === "object" ? options : {};
  if (typeof record === "string" || sqlRejected(settings) || sqlRejected(record)) {
    return stopped("SQL_REJECTED", settings.applicationResult);
  }
  return stopped(boundary.REASON_NODE_BINDING, settings.applicationResult);
}

function getRecord(handle, options) {
  const settings = options && typeof options === "object" ? options : {};
  if (sqlRejected(settings)) return stopped("SQL_REJECTED", settings.applicationResult);
  return stopped(boundary.REASON_NODE_BINDING, settings.applicationResult);
}

function queryEnvelope(reason, limitation) {
  const result = stopped(reason, null);
  result.completeness = "UNAVAILABLE";
  result.completenessReasons = ["REQUIRED_EVIDENCE_UNAVAILABLE"];
  result.freshness = "UNKNOWN";
  result.integrityState = "UNKNOWN";
  result.limitation = limitation;
  return result;
}

function query(handle, request) {
  const settings = request && typeof request === "object" ? request : {};
  if (typeof request === "string" || sqlRejected(settings)) {
    return queryEnvelope("SQL_REJECTED", "Caller SQL is rejected. No store file was opened.");
  }
  return queryEnvelope(
    boundary.REASON_NODE_BINDING,
    "Node binding is unselected. No store file was opened.",
  );
}

module.exports = {
  evidenceRoot,
  getRecord,
  openStore,
  put,
  query,
};
