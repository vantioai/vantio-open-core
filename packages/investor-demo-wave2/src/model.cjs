"use strict";

const { readFileSync } = require("node:fs");
const path = require("node:path");
const {
  CANARY,
  FIXED_TIME,
  HOSTNAME,
  ISO_TIME_RE,
  ORIGIN,
  PRODUCER,
  PRODUCER_VERSION,
  PRODUCER_VERSION_RE,
  TRACE_RE,
} = require("./constants.cjs");

const COVERAGE_ROWS = Object.freeze([
  { id: "node_require", disposition: "RECORDED_WHEN_WRAPPED", blocked: false },
  { id: "python_shield", disposition: "RECORDED_WHEN_WRAPPED", blocked: false },
  { id: "browser", disposition: "UNOBSERVED", blocked: false },
  { id: "unwrapped_process", disposition: "UNOBSERVED", blocked: false },
  { id: "python_without_sdk", disposition: "UNOBSERVED", blocked: false },
  { id: "other_runtime", disposition: "UNOBSERVED", blocked: false },
]);

function coverageReport() {
  const unobservedBlocked = COVERAGE_ROWS.some((row) => row.disposition === "UNOBSERVED" && row.blocked !== false);
  return {
    source: "docs/products/optics/SUPPORTED-PATHS.md",
    room_executed_agent: false,
    unobserved_means_blocked: false,
    rule_holds: unobservedBlocked === false,
    rows: COVERAGE_ROWS.map((row) => ({ ...row })),
  };
}

function isSubset(child, parent) {
  const lists = ["hosts", "destinations", "actions"];
  return lists.every((key) => {
    const childList = Array.isArray(child[key]) ? child[key] : [];
    const parentList = Array.isArray(parent[key]) ? parent[key] : [];
    return childList.every((item) => parentList.includes(item));
  });
}

function evaluateDescendant(input) {
  const refusals = [];
  if (input.redelegation !== "forbidden") refusals.push("REDELEGATION_NOT_DEFAULT");
  if (input.childRequestsRedelegation === true) refusals.push("REDELEGATION_FORBIDDEN");
  if ((input.domain === "security" || input.domain === "recovery")
    && (input.delegatorKind === "workload" || input.delegateKind === "workload")) {
    refusals.push("WORKLOAD_CANNOT_HOLD_DOMAIN");
  }
  if (!isSubset(input.childScope || {}, input.parentScope || {})) refusals.push("WIDENS_AUTHORITY");
  const state = refusals.length === 0 ? "PROPOSED" : "REFUSED";
  return {
    state,
    active: false,
    host_report: false,
    refusals,
    simulation_label: "SIMULATED_DEMO",
    counted_in_customer_activity: false,
    customer_identity: false,
  };
}

function loadProtectionStates(repoRoot) {
  const catalogPath = path.join(repoRoot, "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json");
  const catalog = JSON.parse(readFileSync(catalogPath, "utf8"));
  const values = catalog && catalog.fields && catalog.fields.protection_state
    ? catalog.fields.protection_state.values
    : null;
  if (!Array.isArray(values) || values.length === 0) {
    const error = new Error("HEALTH_CATALOG_UNAVAILABLE");
    error.code = "HEALTH_CATALOG_UNAVAILABLE";
    throw error;
  }
  return {
    source: "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json",
    catalog_id: catalog.catalog_id || null,
    values,
  };
}

function useProtectionState(catalog, state) {
  if (!catalog.values.includes(state)) {
    return { ok: false, state, reason: "UNKNOWN_STATE", host_executed: false };
  }
  return { ok: true, state, reason: null, host_executed: false, simulation_label: "SIMULATED_DEMO" };
}

function assertProducerVersion(version) {
  if (!PRODUCER_VERSION_RE.test(version)) {
    const error = new Error("REFUSED_PRODUCER_VERSION");
    error.code = "REFUSED_PRODUCER_VERSION";
    throw error;
  }
}

function buildEnvelope(options) {
  assertProducerVersion(PRODUCER_VERSION);
  const traceId = options.traceId || "0x00000000000000a2";
  const startedAt = options.startedAt || FIXED_TIME;
  if (!TRACE_RE.test(traceId)) {
    const error = new Error("REFUSED_TRACE_ID");
    error.code = "REFUSED_TRACE_ID";
    throw error;
  }
  if (!ISO_TIME_RE.test(startedAt)) {
    const error = new Error("REFUSED_TIMESTAMP");
    error.code = "REFUSED_TIMESTAMP";
    throw error;
  }
  if (options.evidenceOrigin && options.evidenceOrigin !== ORIGIN) {
    const error = new Error("REFUSED_ORIGIN");
    error.code = "REFUSED_ORIGIN";
    throw error;
  }
  return {
    schema: "vantio.investor-demo.event-envelope/v1",
    schema_status: "unstable-pre-1.0",
    implementation_status: "INTERNAL_WAVE2",
    simulation_label: "SIMULATED_DEMO",
    evidence_origin: ORIGIN,
    producer: PRODUCER,
    producer_version: PRODUCER_VERSION,
    counted_in_customer_activity: false,
    network: "none",
    hostname: HOSTNAME,
    action: "OBSERVED",
    content: null,
    bytes: 0,
    duration_ms: 0,
    trace_id: traceId,
    started_at: startedAt,
  };
}

function dropCanaryPayload() {
  const attempted = { prompt: CANARY, completion: CANARY };
  const stored = { content: null, bytes: 0 };
  const storedText = JSON.stringify(stored);
  return {
    stored,
    canary_presented: true,
    canary_present_in_stored_record: storedText.includes(CANARY),
    attempted_was_not_written: true,
    enforcement_applied: false,
    retained_attempt: attempted.prompt === CANARY,
  };
}

module.exports = {
  COVERAGE_ROWS,
  assertProducerVersion,
  buildEnvelope,
  coverageReport,
  dropCanaryPayload,
  evaluateDescendant,
  loadProtectionStates,
  useProtectionState,
};
