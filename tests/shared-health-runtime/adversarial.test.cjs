"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { consume, evaluateFact, produce } = require("../../packages/shared-health-runtime/src/index.cjs");
const { OPTIONS, ROOT, baseInput, blankFact, enforcingFact } = require("./helpers.cjs");

const catalog = JSON.parse(fs.readFileSync(path.join(
  ROOT,
  "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json",
), "utf8"));

function produced(input) {
  const record = produce(input, OPTIONS);
  const reading = consume(record);
  assert.equal(reading.green, false);
  assert.equal(reading.proved, false);
  return record;
}

test("process up, HTTP 200, and a fresh heartbeat are not healthy tokens", () => {
  const record = produced(baseInput({
    requested_state: "HEALTHY_ENFORCING",
    signals: { process_up: true, http_status: 200, heartbeat_age_s: 1 },
  }));
  assert.equal(record.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(record.freshness, "UNKNOWN");
  assert.equal(record.audit.derived_from_process_up, true);
  assert.equal(record.audit.derived_from_http_success, true);
  assert.equal(record.audit.errors.includes("OPTIMISTIC_GREEN_REFUSED"), true);
  assert.equal(record.audit.errors.includes("HEARTBEAT_IS_NOT_FRESHNESS"), true);
  assert.equal(record.evidence_source, "REFUSED_OPTIMISTIC_SIGNAL");
});

test("catalog examples and rejected facts do not become healthy tokens", () => {
  for (const example of catalog.examples) {
    assert.deepEqual(evaluateFact(example.fact, catalog), [], example.id);
    const record = produced(baseInput({
      component: example.fact.subject,
      scope: "REPOSITORY_ONLY",
      facts: [example.fact],
    }));
    assert.equal(record.state === "HEALTHY_ENFORCING" || record.state === "HEALTHY_OBSERVING", false, example.id);
    assert.equal(record.freshness, "UNKNOWN", example.id);
  }
  for (const example of catalog.rejected_examples) {
    const errors = evaluateFact(example.fact, catalog);
    for (const code of example.violates) assert.equal(errors.includes(code), true, example.id);
    const record = produced(baseInput({ facts: [example.fact] }));
    assert.equal(record.state === "HEALTHY_ENFORCING" || record.state === "HEALTHY_OBSERVING", false, example.id);
  }
});

test("application SUCCESS, Optics SUCCESS, verifier PASS, and ledger OBSERVED stay off the healthy tokens", () => {
  const cases = [
    [blankFact({
      subject: "COVERAGE",
      fact_kind: "APPLICATION_STATUS",
      protection_state: null,
      application_status: "SUCCESS",
    }), "APPLICATION_SUCCESS_IS_NOT_ENFORCEMENT", true, false],
    [blankFact({
      subject: "COVERAGE",
      fact_kind: "OPTICS_DISPLAY_READING",
      protection_state: null,
      optics_display: "SUCCESS",
    }), "OPTICS_DISPLAY_IS_NOT_PROTECTION", false, false],
    [blankFact({
      subject: "COVERAGE",
      fact_kind: "OPTICS_DISPLAY_READING",
      protection_state: null,
      optics_display: "OBSERVED",
    }), "OPTICS_DISPLAY_IS_NOT_PROTECTION", false, false],
    [blankFact({
      subject: "HOST_PREREQUISITE",
      fact_kind: "VERIFIER_RUN",
      protection_state: null,
      verifier_result: "PASS",
    }), "VERIFIER_PASS_IS_NOT_ENFORCEMENT", false, false],
    [blankFact({
      subject: "ARTIFACT",
      fact_kind: "VERIFIER_RUN",
      protection_state: null,
      verifier_result: "OPTIONAL_COMPONENT_ABSENT",
    }), "OPTIONAL_COMPONENT_ABSENT_IS_NOT_PASS", false, false],
    [blankFact({
      subject: "LEDGER",
      fact_kind: "LEDGER_ACTION",
      protection_state: null,
      ledger_action_taken: "OBSERVED",
    }), "LEDGER_OBSERVED_IS_NOT_PROTECTED", false, false],
    [blankFact({
      subject: "LEDGER",
      fact_kind: "LEDGER_ACTION",
      protection_state: null,
      ledger_action_taken: "BLOCKED",
    }), "VERIFIER_BLOCKED_IS_NOT_LEDGER_BLOCKED", false, false],
    [blankFact({
      subject: "HOST_PREREQUISITE",
      fact_kind: "VERIFIER_RUN",
      protection_state: null,
      verifier_result: "BLOCKED",
    }), "VERIFIER_BLOCKED_IS_NOT_LEDGER_BLOCKED", false, false],
  ];
  for (const [fact, code, httpFlag] of cases) {
    const record = produced(baseInput({ component: fact.subject, scope: "REPOSITORY_ONLY", facts: [fact] }));
    assert.equal(record.state, "ENFORCEMENT_UNKNOWN", code);
    assert.equal(record.audit.errors.includes(code), true, code);
    assert.equal(record.audit.derived_from_http_success, httpFlag, code);
    assert.notEqual(record.audit.catalog_protection_state, "protected");
  }
});

test("loader liveness and control-plane heartbeat do not invent a healthy or disconnected state", () => {
  const liveness = produced(baseInput({
    facts: [blankFact({
      fact_kind: "LOADER_LIVENESS",
      protection_state: null,
      heartbeat_age_limit_s: 60,
    })],
  }));
  assert.equal(liveness.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(liveness.freshness, "UNKNOWN");
  assert.equal(liveness.audit.derived_from_process_up, true);
  assert.equal(liveness.audit.errors.includes("HEARTBEAT_IS_NOT_FRESHNESS"), true);

  const heartbeat = produced(baseInput({
    component: "CONTROL_PLANE",
    scope: "REPOSITORY_ONLY",
    facts: [blankFact({
      subject: "CONTROL_PLANE",
      fact_kind: "CONTROL_PLANE_HEARTBEAT",
      protection_state: null,
      interval_s: "NOT_COPIED",
    })],
  }));
  assert.equal(heartbeat.state, "ENFORCEMENT_UNKNOWN");
  assert.notEqual(heartbeat.state, "DISCONNECTED");
  assert.match(heartbeat.limitation, /does not set connected or disconnected/);
});

test("HTTP 200 beside a protection fact is ignored and does not erase the token", () => {
  const record = produced(baseInput({
    signals: { http_status: 200, process_up: true },
    facts: [enforcingFact()],
  }));
  assert.equal(record.state, "HEALTHY_ENFORCING");
  assert.equal(record.audit.derived_from_http_success, false);
  assert.equal(record.audit.derived_from_process_up, false);
  assert.equal(record.audit.http_status_ignored, true);
  assert.equal(record.audit.process_up_ignored, true);
  assert.equal(record.evidence_source, "PROTECTION_EVALUATION");
  assert.equal(consume(record).green, false);
});

test("unverified, unexecuted, stranger, and managed-cloud evidence cannot mint a healthy token", () => {
  const blocked = [
    enforcingFact({ evidence_class: "NOT_EXECUTED_IN_THIS_PASS" }),
    enforcingFact({ evidence_class: "NOT_INDEPENDENTLY_VERIFIED" }),
    enforcingFact({ platform_status: "UNVERIFIED" }),
    enforcingFact({ platform_status: "TARGET_DESIGN" }),
    enforcingFact({ platform_status: "DOCUMENTED_REQUIREMENT" }),
    enforcingFact({ platform_scope: "STRANGER_HOST" }),
  ];
  for (const fact of blocked) {
    const scope = fact.platform_scope === "STRANGER_HOST" ? "STRANGER_HOST" : "REFERENCE_HOST";
    const record = produced(baseInput({ scope, facts: [fact] }));
    assert.equal(record.state, "ENFORCEMENT_UNKNOWN");
    assert.notEqual(record.state, "HEALTHY_ENFORCING");
  }
  const kind = produced(baseInput({
    scope: "MANAGED_CLOUD",
    facts: [enforcingFact({ platform_scope: "KIND_LOCAL" })],
  }));
  assert.equal(kind.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(kind.audit.errors.includes("KIND_LOCAL_IS_NOT_MANAGED_CLOUD"), true);
});

test("contradictions and non-enrollment do not upgrade", () => {
  const mixed = produced(baseInput({
    facts: [
      enforcingFact(),
      enforcingFact({ protection_state: "degraded", evidence_class: "NOT_INDEPENDENTLY_VERIFIED", platform_status: "UNVERIFIED" }),
    ],
  }));
  assert.equal(mixed.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(mixed.audit.errors.includes("PROTECTION_FACTS_CONTRADICT"), true);

  const enrolled = produced(baseInput({
    facts: [blankFact({ protection_state: "not_enrolled" })],
  }));
  assert.equal(enrolled.state, "ENFORCEMENT_UNKNOWN");
  assert.notEqual(enrolled.state, "INTENTIONALLY_DISABLED");
  assert.equal(enrolled.audit.errors.includes("NOT_ENROLLED_IS_NOT_DISABLED"), true);

  const recovery = produced(baseInput({
    facts: [blankFact({ protection_state: "recovery_required" })],
  }));
  assert.equal(recovery.state, "ENFORCEMENT_UNKNOWN");
  assert.notEqual(recovery.state, "ROLLBACK_INCOMPLETE");
  assert.notEqual(recovery.state, "UNINSTALL_INCOMPLETE");
  assert.equal(recovery.audit.errors.includes("RECOVERY_REQUIRED_IS_NOT_ROLLBACK"), true);

  const unknown = produced(baseInput({
    facts: [blankFact({
      subject: "COVERAGE",
      protection_state: "coverage_unknown",
      evidence_class: "NOT_INDEPENDENTLY_VERIFIED",
      platform_scope: "REPOSITORY_ONLY",
      platform_status: "UNVERIFIED",
    })],
    component: "COVERAGE",
    scope: "REPOSITORY_ONLY",
  }));
  assert.equal(unknown.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(unknown.audit.errors.includes("COVERAGE_UNKNOWN_IS_NOT_HEALTHY"), true);
});

test("freshness CURRENT and a caller council pass are not copied onto a healthy token", () => {
  const current = produced(baseInput({
    freshness: "CURRENT",
    facts: [enforcingFact()],
  }));
  assert.equal(current.freshness, "UNKNOWN");
  assert.notEqual(current.state, "HEALTHY_ENFORCING");
  assert.equal(current.audit.errors.includes("FRESHNESS_WINDOW_NOT_SET"), true);

  const council = produced(baseInput({
    independent_verification_status: "COUNCIL_PASSED",
    facts: [enforcingFact()],
  }));
  assert.equal(council.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.notEqual(council.state, "HEALTHY_ENFORCING");
  assert.equal(council.audit.errors.includes("INDEPENDENT_VERIFICATION_NOT_MINTED"), true);
});

test("a fail-open claim cannot keep HEALTHY_ENFORCING", () => {
  const record = produced(baseInput({
    failure_classification: "fail_open",
    facts: [enforcingFact()],
  }));
  assert.equal(record.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(record.audit.errors.includes("FAILURE_CLASSIFICATION_CONTRADICTION"), true);
});

test("explicit disablement wins over process up", () => {
  const record = produced(baseInput({
    lifecycle: "intentionally_disabled",
    signals: { process_up: true, http_status: 200 },
  }));
  assert.equal(record.state, "INTENTIONALLY_DISABLED");
  assert.equal(record.failure_classification, "unsupported");
  assert.equal(record.audit.green, false);
  assert.equal(record.audit.derived_from_http_success, false);
  assert.equal(record.audit.derived_from_process_up, false);
  assert.equal(record.audit.http_status_ignored, true);
  assert.equal(record.audit.process_up_ignored, true);
});

test("every catalog protection state is handled by the producer switch", () => {
  const text = fs.readFileSync(path.join(ROOT, "packages/shared-health-runtime/src/produce.cjs"), "utf8");
  for (const state of catalog.fields.protection_state.values) {
    assert.equal(text.includes(`case "${state}":`), true, state);
  }
});

test("an unreadable catalog does not invent a healthy token", () => {
  const record = produce(baseInput({ facts: [enforcingFact()] }), {
    ...OPTIONS,
    catalogPath: path.join(ROOT, "docs/planning/shared-health-vocabulary/missing.json"),
  });
  assert.equal(record.state, "EVIDENCE_UNAVAILABLE");
  assert.equal(record.audit.green, false);
  assert.equal(record.audit.live_phantom_enforcement_changed, false);
  assert.equal(record.audit.errors.includes("CATALOG_UNREADABLE"), true);
  assert.equal(consume(record).green, false);
});

test("the runtime result is frozen and does not follow later caller edits", () => {
  const input = baseInput({ facts: [enforcingFact()] });
  const record = produce(input, OPTIONS);
  input.signals = { http_status: 200 };
  input.facts[0].protection_state = "coverage_unknown";
  assert.equal(record.state, "HEALTHY_ENFORCING");
  assert.throws(() => {
    record.audit.green = true;
  });
  assert.equal(record.audit.green, false);
});
