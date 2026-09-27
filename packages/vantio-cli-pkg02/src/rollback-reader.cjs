"use strict";

const fs = require("node:fs");

const boundary = require("./boundary.cjs");

function hasOwn(object, key) {
  return !!object && typeof object === "object" && Object.prototype.hasOwnProperty.call(object, key);
}

function readText(filePath) {
  const before = fs.readFileSync(filePath);
  return { before, parsed: JSON.parse(before.toString("utf8")) };
}

function bytesUnchanged(filePath, before) {
  const after = fs.readFileSync(filePath);
  return before.equals(after);
}

function explainCanonical(document) {
  const record = document && typeof document === "object" ? document : null;
  const optics = record && hasOwn(record, "optics_status") ? record.optics_status : null;
  const events = record && Array.isArray(record.events) ? record.events : [];
  const eventOptics = [];
  for (let i = 0; i < events.length; i += 1) {
    if (events[i] && hasOwn(events[i], "optics_status")) eventOptics.push(events[i].optics_status);
  }
  return {
    activates_unit_d: true,
    activates_unit_e: false,
    classification: "FULL",
    evidence_origin: record && hasOwn(record, "evidence_origin") ? record.evidence_origin : null,
    events: eventOptics,
    optics_status: optics,
    producer: record && record.producer ? record.producer : null,
    schema_status: record && hasOwn(record, "schema_status") ? record.schema_status : null,
    schema_version: record && hasOwn(record, "schema_version") ? record.schema_version : null,
    shipped_product: false,
    unknown_status_becomes_success: false,
    writer_version: record && record.cli_or_sdk_version ? record.cli_or_sdk_version : null,
  };
}

function readRolledBack(filePath) {
  const loaded = readText(filePath);
  const parsed = loaded.parsed;
  const unchanged = bytesUnchanged(filePath, loaded.before);
  const canonical = parsed
    && parsed.record_type === "run_envelope"
    && parsed.schema_version === boundary.SCHEMA_VERSION
    && parsed.schema_status === boundary.SCHEMA_STATUS;
  if (!canonical) {
    return {
      activates_unit_d: false,
      activates_unit_e: false,
      bytes_identical: unchanged,
      classification: "LEGACY_SHAPE",
      optics_status: "UNAVAILABLE",
      rewritten: false,
      schema_marker_visible: false,
      schema_status: parsed && hasOwn(parsed, "schema_status") ? parsed.schema_status : null,
      schema_version: parsed && hasOwn(parsed, "schema_version") ? parsed.schema_version : null,
      unknown_status_becomes_success: false,
    };
  }
  return {
    activates_unit_d: true,
    activates_unit_e: false,
    bytes_identical: unchanged,
    classification: "UNSUPPORTED",
    evidence_origin: hasOwn(parsed, "evidence_origin") ? parsed.evidence_origin : null,
    optics_status: "UNSUPPORTED",
    rewritten: false,
    schema_marker_visible: parsed.schema_status != null && parsed.schema_version != null,
    schema_status: parsed.schema_status,
    schema_version: parsed.schema_version,
    unknown_status_becomes_success: false,
  };
}

module.exports = {
  explainCanonical,
  readRolledBack,
};
