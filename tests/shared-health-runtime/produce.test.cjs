"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { consume, produce } = require("../../packages/shared-health-runtime/src/index.cjs");
const contract = require("../../packages/shared-health-runtime/contract.json");
const { NOW, OPTIONS, baseInput, blankFact, enforcingFact, observingFact } = require("./helpers.cjs");

function produced(input) {
  return produce(input, OPTIONS);
}

test("every emitted state carries the evidence fields and stays non-green", () => {
  const cases = [
    ["HEALTHY_ENFORCING", baseInput({ facts: [enforcingFact()] })],
    ["HEALTHY_OBSERVING", baseInput({ facts: [observingFact()] })],
    ["INTENTIONALLY_DISABLED", baseInput({ lifecycle: "intentionally_disabled" })],
    ["UNSUPPORTED", baseInput({ component: "HOST_PREREQUISITE", lifecycle: "unsupported" })],
    ["PARTIAL_COVERAGE", baseInput({ lifecycle: "partial_coverage", named_gaps: ["windows_and_macos"] })],
    ["DEGRADED", baseInput({ facts: [blankFact({ protection_state: "degraded", evidence_class: "NOT_INDEPENDENTLY_VERIFIED", platform_scope: "REFERENCE_HOST", platform_status: "UNVERIFIED" })] })],
    ["STALE", baseInput({ facts: [blankFact({ protection_state: "protection_stale", evidence_class: "NOT_INDEPENDENTLY_VERIFIED", platform_scope: "REFERENCE_HOST", platform_status: "UNVERIFIED" })] })],
    ["DISCONNECTED", baseInput({ component: "CONTROL_PLANE", lifecycle: "disconnected" })],
    ["EVIDENCE_UNAVAILABLE", {}],
    ["ENFORCEMENT_UNKNOWN", baseInput({ signals: { process_up: true, http_status: 200 } })],
    ["ROLLBACK_INCOMPLETE", baseInput({ lifecycle: "rollback_incomplete" })],
    ["UNINSTALL_INCOMPLETE", baseInput({ lifecycle: "uninstall_incomplete" })],
  ];
  assert.deepEqual(cases.map(([state]) => state), contract.states);
  for (const [state, input] of cases) {
    const record = produced(input);
    assert.equal(record.state, state, state);
    for (const field of contract.required_fields) {
      assert.equal(Object.hasOwn(record, field), true, `${state} ${field}`);
    }
    assert.equal(record.record_type, "SHARED_HEALTH_RUNTIME_STATE");
    assert.equal(record.freshness, "UNKNOWN");
    assert.equal(record.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
    assert.equal(record.recovery_verification, "NOT_VERIFIED");
    assert.equal(typeof record.limitation, "string");
    assert.match(record.limitation, /not a green light/);
    assert.equal(typeof record.safe_corrective_action, "string");
    assert.equal(record.safe_corrective_action.length > 0, true);
    assert.equal(record.audit.green, false);
    assert.equal(record.audit.proved, false);
    assert.equal(record.audit.live_phantom_enforcement_changed, false);
    assert.equal(record.audit.this_runtime_executed, false);
    assert.equal(record.audit.catalog_commit, contract.catalog_commit);
    assert.equal(record.audit.producer_classification, "SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL");
    assert.equal(record.audit.council_status, "PENDING_INDEPENDENT_COUNCIL");
    const reading = consume(record);
    assert.equal(reading.accepted, true, `${state} ${reading.errors.join(",")}`);
    assert.equal(reading.green, false);
    assert.equal(reading.proved, false);
    assert.equal(reading.state, state);
  }
});

test("healthy tokens keep token meaning and do not measure a latch", () => {
  const enforcing = produced(baseInput({ facts: [enforcingFact()] }));
  assert.equal(enforcing.failure_classification, "fail_closed");
  assert.equal(enforcing.audit.failure_classification_basis, "TOKEN_MEANING");
  assert.equal(enforcing.evidence_source, "PROTECTION_EVALUATION");
  assert.equal(enforcing.audit.catalog_protection_state, "protected");
  assert.equal(enforcing.audit.evidence_basis, "PROTECTION_EVALUATION");
  assert.match(enforcing.limitation, /did not execute enforcement/);

  const observing = produced(baseInput({ facts: [observingFact()] }));
  assert.equal(observing.failure_classification, "fail_open");
  assert.equal(observing.audit.catalog_protection_state, "observing");
  assert.match(observing.safe_corrective_action, /does not enable enforcement/);
});

test("policy stale is the STALE state with freshness UNKNOWN", () => {
  const record = produced(baseInput({
    facts: [blankFact({
      protection_state: "policy_stale",
      evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
      platform_scope: "REFERENCE_HOST",
      platform_status: "UNVERIFIED",
    })],
  }));
  assert.equal(record.state, "STALE");
  assert.equal(record.freshness, "UNKNOWN");
  assert.equal(record.audit.catalog_protection_state, "policy_stale");
});

test("quarantine stays inside DEGRADED", () => {
  const record = produced(baseInput({
    facts: [blankFact({
      protection_state: "quarantined",
      evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
      platform_scope: "REFERENCE_HOST",
      platform_status: "UNVERIFIED",
    })],
  }));
  assert.equal(record.state, "DEGRADED");
  assert.equal(record.audit.errors.includes("QUARANTINE_IS_NOT_A_SEPARATE_RUNTIME_STATE"), true);
  assert.match(record.limitation, /dual_control_executor_wired/);
});

test("a missing timestamp withholds lifecycle states", () => {
  const record = produced({
    component: "LOADER",
    scope: "REFERENCE_HOST",
    producer: "unit-test",
    source_version: "test-source",
    lifecycle: "rollback_incomplete",
  });
  assert.equal(record.state, "EVIDENCE_UNAVAILABLE");
  assert.equal(record.timestamp, null);
  assert.equal(record.audit.errors.includes("TIMESTAMP_REQUIRED"), true);
});

test("last known good is kept only when it is itself non-optimistic", () => {
  const good = {
    state: "DEGRADED",
    timestamp: NOW,
    evidence_source: "PROTECTION_EVALUATION",
    freshness: "UNKNOWN",
  };
  const kept = produced(baseInput({ lifecycle: "intentionally_disabled", last_known_good: good }));
  assert.deepEqual(kept.last_known_good, good);
  const dropped = produced(baseInput({
    lifecycle: "intentionally_disabled",
    last_known_good: { ...good, evidence_source: "http_200", freshness: "CURRENT" },
  }));
  assert.equal(dropped.last_known_good, null);
  assert.equal(dropped.state, "INTENTIONALLY_DISABLED");
  assert.equal(dropped.audit.errors.includes("LAST_KNOWN_GOOD_REJECTED"), true);
});

test("caller source version and producer are copied", () => {
  const record = produced(baseInput({ facts: [enforcingFact()] }));
  assert.equal(record.source_version, "test-source");
  assert.equal(record.producer, "unit-test");
  assert.equal(record.audit.source_version_kind, "CALLER_SUPPLIED");
  assert.equal(record.audit.emitted_at, NOW);
});

test("partial coverage keeps named gaps and refuses a percentage", () => {
  const record = produced(baseInput({
    lifecycle: "partial_coverage",
    named_gaps: ["windows_and_macos", "unpinned_image_digest"],
    coverage_percent: 85,
  }));
  assert.equal(record.state, "PARTIAL_COVERAGE");
  assert.deepEqual(record.audit.named_gaps, ["windows_and_macos", "unpinned_image_digest"]);
  assert.equal(Object.hasOwn(record, "coverage_percent"), false);
  assert.equal(record.audit.errors.includes("COVERAGE_PERCENT_FORBIDDEN"), true);
  const empty = produced(baseInput({ lifecycle: "partial_coverage", named_gaps: [] }));
  assert.equal(empty.state, "EVIDENCE_UNAVAILABLE");
  assert.equal(empty.audit.errors.includes("NAMED_GAP_REQUIRED"), true);
});
