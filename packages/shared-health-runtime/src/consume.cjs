"use strict";

const contract = require("../contract.json");
const { isPlainObject, loadCatalog } = require("./catalog.cjs");

const HEALTHY = new Set(contract.healthy_tokens);
const STATES = new Set(contract.states);
const CLASSIFICATIONS = new Set(contract.failure_classifications);
const COMPONENTS = new Set(contract.components);
const OPTIMISTIC_SOURCES = new Set(contract.optimistic_evidence_sources);
const TOKEN_CLASSIFICATION = contract.token_failure_classification;
const NONBLOCKING = new Set(contract.nonblocking_errors);

function refusal(state, errors, presented) {
  return Object.freeze({
    accepted: false,
    green: false,
    proved: false,
    state,
    presented_state: presented,
    token_family: HEALTHY.has(state) ? "HEALTHY" : "NON_HEALTHY",
    errors: Object.freeze([...new Set(errors)]),
    live_phantom_enforcement_changed: false,
  });
}

function isIsoTimestamp(value) {
  return typeof value === "string"
    && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)
    && !Number.isNaN(Date.parse(value));
}

function isOptimisticSource(value) {
  return typeof value === "string" && OPTIMISTIC_SOURCES.has(value.trim().toLowerCase());
}

function collectErrors(record, catalog) {
  const errors = [];
  for (const field of contract.required_fields) {
    if (!Object.prototype.hasOwnProperty.call(record, field)) errors.push(`MISSING_${field.toUpperCase()}`);
  }
  if (record.record_type !== contract.record_type) errors.push("RECORD_TYPE");
  if (!STATES.has(record.state)) errors.push("STATE_ENUM");
  const componentKnown = COMPONENTS.has(record.component)
    || record.component === contract.unspecified_component;
  if (!componentKnown) errors.push("COMPONENT_ENUM");
  if (
    record.component === contract.unspecified_component
    && record.state !== "EVIDENCE_UNAVAILABLE"
    && record.state !== "ENFORCEMENT_UNKNOWN"
  ) {
    errors.push("COMPONENT_UNSPECIFIED");
  }
  const scopes = catalog.fields.platform_scope.values;
  if (!scopes.includes(record.scope)) errors.push("SCOPE_ENUM");
  if (record.freshness !== "UNKNOWN") errors.push("FRESHNESS_EMITTED");
  if (!CLASSIFICATIONS.has(record.failure_classification)) errors.push("FAILURE_CLASSIFICATION_ENUM");
  if (record.independent_verification_status !== "NOT_INDEPENDENTLY_VERIFIED") {
    errors.push("INDEPENDENT_VERIFICATION_NOT_MINTED");
  }
  if (record.recovery_verification !== "NOT_VERIFIED") errors.push("RECOVERY_VERIFICATION");
  if (typeof record.limitation !== "string" || record.limitation.trim() === "") errors.push("LIMITATION_REQUIRED");
  if (typeof record.safe_corrective_action !== "string" || record.safe_corrective_action.trim() === "") {
    errors.push("CORRECTIVE_ACTION_REQUIRED");
  }
  if (typeof record.evidence_source !== "string" || record.evidence_source.trim() === "") {
    errors.push("EVIDENCE_SOURCE_REQUIRED");
  }
  if (typeof record.source_version !== "string" || record.source_version.trim() === "") {
    errors.push("SOURCE_VERSION_REQUIRED");
  }
  if (typeof record.producer !== "string" || record.producer.trim() === "") errors.push("PRODUCER_REQUIRED");
  if (record.timestamp !== null && !isIsoTimestamp(record.timestamp)) errors.push("TIMESTAMP_INVALID");
  if (record.timestamp === null && record.state !== "EVIDENCE_UNAVAILABLE" && record.state !== "ENFORCEMENT_UNKNOWN") {
    errors.push("TIMESTAMP_REQUIRED");
  }
  if (record.last_known_good !== null && !isPlainObject(record.last_known_good)) {
    errors.push("LAST_KNOWN_GOOD_SHAPE");
  }
  if (isPlainObject(record.last_known_good)) {
    if (!STATES.has(record.last_known_good.state)) errors.push("LAST_KNOWN_GOOD_STATE");
    if (record.last_known_good.freshness !== "UNKNOWN") errors.push("LAST_KNOWN_GOOD_FRESHNESS");
    if (!isIsoTimestamp(record.last_known_good.timestamp)) errors.push("LAST_KNOWN_GOOD_TIMESTAMP");
    if (isOptimisticSource(record.last_known_good.evidence_source)) errors.push("LAST_KNOWN_GOOD_OPTIMISTIC");
    if (record.last_known_good.green === true || record.last_known_good.proved === true) {
      errors.push("LAST_KNOWN_GOOD_OPTIMISTIC");
    }
  }

  const audit = record.audit;
  if (!isPlainObject(audit)) {
    errors.push("AUDIT_REQUIRED");
    return errors;
  }
  if (audit.catalog_commit !== contract.catalog_commit) errors.push("CATALOG_COMMIT");
  if (audit.green !== false) errors.push("OPTIMISTIC_GREEN_REFUSED");
  if (audit.proved !== false) errors.push("PROVED_REFUSED");
  if (audit.live_phantom_enforcement_changed !== false) errors.push("LIVE_ENFORCEMENT_REFUSED");
  if (audit.this_runtime_executed !== false) errors.push("RUNTIME_EXECUTION_REFUSED");
  if (audit.stable_schema !== false) errors.push("STABLE_SCHEMA_REFUSED");
  if (audit.producer_classification !== contract.producer_classification) errors.push("PRODUCER_CLASSIFICATION");
  if (audit.council_status !== contract.council_status) errors.push("COUNCIL_STATUS");
  if (audit.schema_status !== contract.schema_status) errors.push("SCHEMA_STATUS");
  if (audit.runtime_name !== contract.runtime_name) errors.push("RUNTIME_NAME");
  if (typeof audit.derived_from_process_up !== "boolean") errors.push("PROCESS_FLAG");
  if (typeof audit.derived_from_http_success !== "boolean") errors.push("HTTP_FLAG");
  if (!Array.isArray(audit.errors)) errors.push("AUDIT_ERRORS");
  if (Object.prototype.hasOwnProperty.call(record, "coverage_percent")) errors.push("COVERAGE_PERCENT_FORBIDDEN");
  if (Object.prototype.hasOwnProperty.call(record, "proved") && record.proved === true) errors.push("PROVED_REFUSED");
  if (record.green === true) errors.push("OPTIMISTIC_GREEN_REFUSED");

  if (HEALTHY.has(record.state)) {
    if (audit.evidence_basis !== "PROTECTION_EVALUATION") errors.push("HEALTHY_BASIS");
    if (record.evidence_source !== "PROTECTION_EVALUATION") errors.push("HEALTHY_EVIDENCE_SOURCE");
    if (!contract.healthy_evidence_classes.includes(audit.evidence_class)) errors.push("EVIDENCE_CLASS_BLOCKS_HEALTHY_TOKEN");
    if (!contract.healthy_platform_statuses.includes(audit.platform_status)) {
      errors.push("PLATFORM_STATUS_BLOCKS_HEALTHY_TOKEN");
    }
    if (!contract.healthy_scopes.includes(record.scope)) errors.push("SCOPE_BLOCKS_HEALTHY_TOKEN");
    if (audit.derived_from_process_up === true || audit.derived_from_http_success === true) {
      errors.push("OPTIMISTIC_GREEN_REFUSED");
    }
    if (isOptimisticSource(record.evidence_source)) errors.push("OPTIMISTIC_GREEN_REFUSED");
    if (Array.isArray(audit.errors) && audit.errors.some((code) => !NONBLOCKING.has(code))) {
      errors.push("HEALTHY_TOKEN_HAS_ERRORS");
    }
    const expectedProtection = record.state === "HEALTHY_ENFORCING" ? "protected" : "observing";
    if (audit.catalog_protection_state !== expectedProtection) errors.push("PROTECTION_STATE_MISMATCH");
    if (record.failure_classification !== TOKEN_CLASSIFICATION[record.state]) {
      errors.push("FAILURE_CLASSIFICATION_CONTRADICTION");
    }
    if (audit.failure_classification_basis !== "TOKEN_MEANING") errors.push("FAILURE_CLASSIFICATION_BASIS");
  }

  if (record.state === "PARTIAL_COVERAGE") {
    if (!Array.isArray(audit.named_gaps) || audit.named_gaps.length === 0) errors.push("NAMED_GAP_REQUIRED");
  }
  if (record.state === "STALE" && record.freshness !== "UNKNOWN") errors.push("FRESHNESS_STALE_IS_NOT_A_STATE");
  if (TOKEN_CLASSIFICATION[record.state] && record.failure_classification !== TOKEN_CLASSIFICATION[record.state]) {
    errors.push("FAILURE_CLASSIFICATION_CONTRADICTION");
  }
  return errors;
}

function consume(record) {
  const presented = isPlainObject(record) && typeof record.state === "string" ? record.state : null;
  if (!isPlainObject(record)) return refusal("EVIDENCE_UNAVAILABLE", ["RECORD_SHAPE"], presented);
  const loaded = loadCatalog();
  if (!loaded.ok) return refusal("EVIDENCE_UNAVAILABLE", loaded.errors, presented);
  const errors = collectErrors(record, loaded.catalog);
  if (errors.length > 0) {
    const optimistic = errors.some((code) => {
      return code === "OPTIMISTIC_GREEN_REFUSED"
        || code === "HEALTHY_BASIS"
        || code === "HEALTHY_EVIDENCE_SOURCE"
        || code === "EVIDENCE_CLASS_BLOCKS_HEALTHY_TOKEN"
        || code === "PLATFORM_STATUS_BLOCKS_HEALTHY_TOKEN"
        || code === "SCOPE_BLOCKS_HEALTHY_TOKEN"
        || code === "PROTECTION_STATE_MISMATCH"
        || code === "PROVED_REFUSED"
        || code === "FRESHNESS_EMITTED"
        || code === "LIVE_ENFORCEMENT_REFUSED";
    });
    const reported = HEALTHY.has(presented) || optimistic ? "ENFORCEMENT_UNKNOWN" : "EVIDENCE_UNAVAILABLE";
    return refusal(reported, errors, presented);
  }
  return Object.freeze({
    accepted: true,
    green: false,
    proved: false,
    state: record.state,
    presented_state: record.state,
    token_family: HEALTHY.has(record.state) ? "HEALTHY" : "NON_HEALTHY",
    errors: Object.freeze([]),
    live_phantom_enforcement_changed: false,
  });
}

module.exports = {
  consume,
};
