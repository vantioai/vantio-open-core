"use strict";

const path = require("node:path");

const ROOT = path.resolve(__dirname, "../..");
const NOW = "2026-09-27T11:13:00.000Z";
const OPTIONS = Object.freeze({ now: NOW });

function blankFact(overrides = {}) {
  return {
    record_type: "SHARED_HEALTH_FACT",
    subject: "LOADER",
    fact_kind: "PROTECTION_EVALUATION",
    freshness: "UNKNOWN",
    protection_state: null,
    verifier_result: null,
    optics_display: null,
    sdk_action: null,
    application_status: null,
    evidence_class: null,
    platform_scope: null,
    platform_status: null,
    deployment_profile: null,
    compatibility_status: null,
    ledger_action_taken: null,
    pass_through_product_label: null,
    heartbeat_age_limit_s: null,
    interval_s: null,
    ...overrides,
  };
}

function baseInput(overrides = {}) {
  return {
    component: "LOADER",
    scope: "REFERENCE_HOST",
    timestamp: NOW,
    producer: "unit-test",
    source_version: "test-source",
    ...overrides,
  };
}

function enforcingFact(overrides = {}) {
  return blankFact({
    protection_state: "protected",
    evidence_class: "OBSERVED_FROM_REPOSITORY_EVIDENCE",
    platform_scope: "REFERENCE_HOST",
    platform_status: "VERIFIED_ON_REFERENCE_HOST",
    ...overrides,
  });
}

function observingFact(overrides = {}) {
  return enforcingFact({ protection_state: "observing", ...overrides });
}

module.exports = {
  NOW,
  OPTIONS,
  ROOT,
  baseInput,
  blankFact,
  enforcingFact,
  observingFact,
};
