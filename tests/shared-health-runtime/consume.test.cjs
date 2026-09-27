"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { consume, consumeFact, produce } = require("../../packages/shared-health-runtime/src/index.cjs");
const contract = require("../../packages/shared-health-runtime/contract.json");
const { OPTIONS, baseInput, blankFact, enforcingFact } = require("./helpers.cjs");

function forged(mutator) {
  const record = structuredClone(produce(baseInput({ facts: [enforcingFact()] }), OPTIONS));
  mutator(record);
  return record;
}

test("a qualified healthy token is accepted and the green bit stays false", () => {
  const record = produce(baseInput({ facts: [enforcingFact()] }), OPTIONS);
  const reading = consume(record);
  assert.equal(reading.accepted, true);
  assert.equal(reading.green, false);
  assert.equal(reading.proved, false);
  assert.equal(reading.token_family, "HEALTHY");
  assert.equal(reading.live_phantom_enforcement_changed, false);
  assert.equal(reading.state, "HEALTHY_ENFORCING");
});

test("consumption refuses optimistic green on a forged record", () => {
  const cases = [
    [(record) => { record.audit.green = true; }],
    [(record) => { record.green = true; }],
    [(record) => { record.audit.proved = true; }],
    [(record) => { record.audit.live_phantom_enforcement_changed = true; }],
    [(record) => { record.audit.this_runtime_executed = true; }],
    [(record) => { record.freshness = "CURRENT"; }],
    [(record) => { record.freshness = "STALE"; }],
    [(record) => { record.evidence_source = "http_200"; }],
    [(record) => { record.evidence_source = "process_up"; }],
    [(record) => { record.audit.derived_from_http_success = true; }],
    [(record) => { record.audit.derived_from_process_up = true; }],
    [(record) => { record.audit.evidence_basis = "REFUSED_OPTIMISTIC_SIGNAL"; }],
    [(record) => { record.audit.catalog_protection_state = "coverage_unknown"; }],
    [(record) => { record.audit.evidence_class = "NOT_INDEPENDENTLY_VERIFIED"; }],
    [(record) => { record.audit.evidence_class = "NOT_EXECUTED_IN_THIS_PASS"; }],
    [(record) => { record.audit.platform_status = "UNVERIFIED"; }],
    [(record) => { record.audit.platform_status = "TARGET_DESIGN"; }],
    [(record) => { record.scope = "STRANGER_HOST"; }],
    [(record) => { record.scope = "MANAGED_CLOUD"; }],
    [(record) => { record.failure_classification = "fail_open"; }],
    [(record) => { record.independent_verification_status = "COUNCIL_PASSED"; }],
    [(record) => { record.recovery_verification = "PASS"; }],
    [(record) => { record.audit.catalog_commit = "0".repeat(40); }],
    [(record) => { record.audit.council_status = "COUNCIL_PASSED"; }],
    [(record) => { record.audit.producer_classification = "SHARED_HEALTH_RUNTIME_COUNCIL_PASSED"; }],
  ];
  for (const [mutate] of cases) {
    const reading = consume(forged(mutate));
    assert.equal(reading.accepted, false);
    assert.equal(reading.green, false);
    assert.equal(reading.proved, false);
    assert.equal(reading.state, "ENFORCEMENT_UNKNOWN");
  }
});

test("a record missing evidence fields is not accepted and is not green", () => {
  const healthy = forged((copy) => {
    delete copy.limitation;
    delete copy.safe_corrective_action;
    delete copy.producer;
  });
  const healthyReading = consume(healthy);
  assert.equal(healthyReading.accepted, false);
  assert.equal(healthyReading.green, false);
  assert.equal(healthyReading.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(healthyReading.errors.includes("MISSING_LIMITATION"), true);
  assert.equal(healthyReading.errors.includes("MISSING_SAFE_CORRECTIVE_ACTION"), true);
  assert.equal(healthyReading.errors.includes("MISSING_PRODUCER"), true);

  const degraded = structuredClone(produce(baseInput({
    facts: [blankFact({
      protection_state: "degraded",
      evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
      platform_scope: "REFERENCE_HOST",
      platform_status: "UNVERIFIED",
    })],
  }), OPTIONS));
  delete degraded.limitation;
  const degradedReading = consume(degraded);
  assert.equal(degradedReading.accepted, false);
  assert.equal(degradedReading.green, false);
  assert.equal(degradedReading.state, "EVIDENCE_UNAVAILABLE");
});

test("consume does not mutate the caller record", () => {
  const record = produce(baseInput({ lifecycle: "unsupported" }), OPTIONS);
  const before = structuredClone(record);
  consume(record);
  assert.deepEqual(record, before);
});

test("consumeFact uses one catalog fact and does not paint HTTP success healthy", () => {
  const fact = {
    record_type: "SHARED_HEALTH_FACT",
    subject: "LOADER",
    fact_kind: "APPLICATION_STATUS",
    freshness: "UNKNOWN",
    protection_state: null,
    verifier_result: null,
    optics_display: null,
    sdk_action: null,
    application_status: "SUCCESS",
    evidence_class: null,
    platform_scope: null,
    platform_status: null,
    deployment_profile: null,
    compatibility_status: null,
    ledger_action_taken: null,
    pass_through_product_label: null,
    heartbeat_age_limit_s: null,
    interval_s: null,
  };
  const record = consumeFact(fact, baseInput(), OPTIONS);
  assert.equal(record.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(record.audit.derived_from_http_success, true);
  assert.equal(record.audit.green, false);
  assert.equal(consume(record).green, false);
});

test("an unknown state token is evidence unavailable to the consumer", () => {
  const reading = consume(forged((record) => {
    record.state = "HEALTHY";
  }));
  assert.equal(reading.accepted, false);
  assert.equal(reading.green, false);
  assert.equal(reading.presented_state, "HEALTHY");
});

test("the contract healthy tokens are the only HEALTHY family", () => {
  assert.deepEqual(contract.healthy_tokens, ["HEALTHY_ENFORCING", "HEALTHY_OBSERVING"]);
  assert.equal(contract.green_emitted, false);
  assert.deepEqual(contract.freshness_emitted, ["UNKNOWN"]);
});
