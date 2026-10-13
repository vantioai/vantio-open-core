"use strict";

// Unsigned Optics observation fragment.
// Enterprise seals this object in vantio-enterprise-private. This module does
// not sign, does not enforce, and does not claim a host proof.

const { createHash } = require("node:crypto");
const { canonicalJson } = require("./canonical.cjs");

const SCHEMA_ID = "vantio.optics.observation-fragment";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;

function enforcementAction(action) {
  if (typeof action !== "string" || action === "") return false;
  if (action === "OBSERVED") return false;
  if (action === "ALLOWED" || action === "REDACTED") return true;
  return action.startsWith("BLOCKED") || action.startsWith("DRY_RUN");
}

function intOrNull(value) {
  if (value == null) return null;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) return null;
  return value;
}

function textOrNull(value) {
  return typeof value === "string" ? value : null;
}

function buildObservationFragment(record, producer, producerVersion) {
  if (!record || typeof record !== "object" || Array.isArray(record)) {
    return { ok: false, reason: "MALFORMED", fragment: null };
  }
  const summary = record.summary && typeof record.summary === "object" ? record.summary : {};
  if (summary.blocked || summary.redacted) {
    return { ok: false, reason: "ENFORCEMENT_ACTION_EXCLUDED", fragment: null };
  }
  const rawCalls = record.calls == null ? [] : record.calls;
  if (!Array.isArray(rawCalls)) return { ok: false, reason: "MALFORMED", fragment: null };
  const calls = [];
  for (const call of rawCalls) {
    if (!call || typeof call !== "object" || Array.isArray(call)) {
      return { ok: false, reason: "MALFORMED", fragment: null };
    }
    if (enforcementAction(call.action)) {
      return { ok: false, reason: "ENFORCEMENT_ACTION_EXCLUDED", fragment: null };
    }
    const status = call.status != null ? call.status : call.http_status;
    calls.push({
      action: call.action === "OBSERVED" ? "OBSERVED" : null,
      application_status: textOrNull(call.applicationStatus || call.application_status),
      hostname: textOrNull(call.hostname),
      http_status: intOrNull(status),
      method: textOrNull(call.method),
      optics_status: textOrNull(call.opticsStatus || call.optics_status),
      path: textOrNull(call.path),
      response_bytes: intOrNull(call.bytes != null ? call.bytes : call.response_bytes),
    });
  }
  const body = {
    calls,
    claim_ceiling: "OBSERVATION_ONLY",
    enforcement_attached: false,
    live_enforcement: "NOT_APPLICABLE",
    producer,
    producer_version: producerVersion,
    product: "optics",
    role: "observation",
    schema_id: SCHEMA_ID,
    schema_status: SCHEMA_STATUS,
    schema_version: SCHEMA_VERSION,
    trace_id: textOrNull(record.trace_id) || "",
  };
  const digest = createHash("sha256").update(canonicalJson(body), "utf8").digest("hex");
  body.record_sha256 = `sha256:${digest}`;
  return { ok: true, reason: null, fragment: body };
}

function fragmentDigestMatches(fragment) {
  if (!fragment || typeof fragment !== "object") return false;
  const body = Object.assign({}, fragment);
  delete body.record_sha256;
  const digest = `sha256:${createHash("sha256").update(canonicalJson(body), "utf8").digest("hex")}`;
  return fragment.record_sha256 === digest;
}

module.exports = {
  SCHEMA_ID,
  buildObservationFragment,
  fragmentDigestMatches,
};
