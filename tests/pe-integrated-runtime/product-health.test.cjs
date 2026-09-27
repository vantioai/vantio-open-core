"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const runtime = require("../../internal/pe-integrated-runtime/src/index.cjs");
const contract = require("../../packages/shared-health-runtime/contract.json");
const blocked = require("../../docs/programs/production-readiness/wave3/BLOCKED-INFRA.json");
const { attempt, policy } = require("../pe-egress/fixture.cjs");
const { baseInput, enforcingFact, observingFact, OPTIONS } = require("../shared-health-runtime/helpers.cjs");

const ROOT = path.join(__dirname, "../..");
const HISTORY = JSON.parse(fs.readFileSync(
  path.join(ROOT, "packages/pe-progressive-enforcement/fixtures/history.json"),
  "utf8",
)).events;

function must(result) {
  assert.equal(result.ok, true, `${result.code} ${JSON.stringify(result.problems)}`);
  return result;
}

function promote(rt) {
  const signal = { subject_ref: "agent-a", host: "api.example.com", byte_count: 120, at: 10 };
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "discover",
    input: { rule_id: "rule-host", actor: "ada", signal },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "observe",
    input: { rule_id: "rule-host", actor: "ada", observation: signal },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "propose",
    input: {
      rule_id: "rule-host",
      actor: "ada",
      effect: "DECLARED_HOST_MATCH",
      predicate: { host_equals: "api.example.com" },
    },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "simulate",
    input: { rule_id: "rule-host", actor: "ada", corpus: HISTORY },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "canary",
    input: {
      rule_id: "rule-host",
      actor: "ada",
      cohort: { cohort_id: "cohort-a", subject_refs: ["agent-a"] },
      samples: HISTORY.filter((row) => row.subject_ref === "agent-a"),
    },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "promote",
    input: { rule_id: "rule-host", actor: "ada", approver: "bao", rollout_request: "COHORT" },
  }));
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "decide",
    input: {
      rule_id: "rule-host",
      subject_ref: "agent-a",
      host: "api.example.com",
      byte_count: 120,
      at: 10,
    },
  }));
}

function plane(status, execution) {
  return {
    present: status !== "ABSENT",
    status,
    execution,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

test("registers keep the product-health ceiling and the merged runtime classification", () => {
  assert.equal(runtime.PRODUCT_HEALTH_CLASSIFICATION, "W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL");
  assert.equal(runtime.PRODUCER_CLASSIFICATION, "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL");
  assert.equal(runtime.POSTURE.product_health_failure_truth, "W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL");
  assert.equal(runtime.POSTURE.eligible_plane, "NONE");
  assert.equal(runtime.POSTURE.named_eligible_plane, false);
  assert.equal(runtime.POSTURE.infra_requirement, "W3-INFRA-REQ-1");
  assert.equal(runtime.POSTURE.execution_ceiling, "HOST_ATTACHMENT_FALSE");
  assert.equal(runtime.POSTURE.healthy_enforcing_reported_as_host_enforcement, false);
  assert.equal(runtime.POSTURE.blocked_host_reported_as_host_enforcement, false);
  assert.equal(runtime.POSTURE.enforce_stage_reported_as_host_enforcement, false);
  assert.equal(runtime.POSTURE.promoted_match_reported_as_host_enforcement, false);
  assert.equal(runtime.POSTURE.missing_evidence_collapsed_to_success, false);
  assert.equal(runtime.POSTURE.unknown_evidence_collapsed_to_success, false);
  assert.equal(runtime.POSTURE.unavailable_evidence_collapsed_to_success, false);
  assert.equal(runtime.POSTURE.optimistic_success, false);
  assert.equal(runtime.RUNTIME_REGISTER.product_health_failure_truth, runtime.POSTURE.product_health_failure_truth);
  assert.equal(runtime.INTEGRATION_REGISTER.execution_ceiling, "HOST_ATTACHMENT_FALSE");
  assert.equal(runtime.PRODUCT_HEALTH_RUNTIME_REGISTER.producer_classification, runtime.PRODUCT_HEALTH_CLASSIFICATION);
  assert.equal(runtime.PRODUCT_HEALTH_RUNTIME_REGISTER.council_verdict, null);
  assert.deepEqual(runtime.PRODUCT_HEALTH_RUNTIME_REGISTER.vocabulary_states_added, []);
  const tokens = runtime.PRODUCT_HEALTH_INTEGRATION_REGISTER.rows.map((row) => row.token);
  assert.deepEqual(tokens, [
    "HEALTHY_ENFORCING",
    "BLOCKED_HOST",
    "ENFORCE",
    "PROMOTED_MATCH",
    "EVIDENCE_UNAVAILABLE",
    "ENFORCEMENT_UNKNOWN",
  ]);
  for (const row of runtime.PRODUCT_HEALTH_INTEGRATION_REGISTER.rows) {
    assert.equal(row.reported_as_host_enforcement, false, row.token);
    assert.equal(row.collapsed_to_success, false, row.token);
    assert.equal(row.plane === "OBSERVATION" || row.plane === "DECISION", true, row.token);
  }

  const pairs = [
    ["docs/internal/wave3/pe-integration/RUNTIME-REGISTER.json", "docs/programs/production-readiness/wave3/RUNTIME-REGISTER.json"],
    ["docs/internal/wave3/pe-integration/INTEGRATION-REGISTER.json", "docs/programs/production-readiness/wave3/INTEGRATION-REGISTER.json"],
    ["docs/internal/wave3/product-health/RUNTIME-REGISTER.json", "docs/programs/production-readiness/wave3/product-health/RUNTIME-REGISTER.json"],
    ["docs/internal/wave3/product-health/INTEGRATION-REGISTER.json", "docs/programs/production-readiness/wave3/product-health/INTEGRATION-REGISTER.json"],
    ["docs/internal/wave3/product-health/STATUS.json", "docs/programs/production-readiness/wave3/product-health/STATUS.json"],
  ];
  for (const [left, right] of pairs) {
    const a = fs.readFileSync(path.join(ROOT, left), "utf8");
    const b = fs.readFileSync(path.join(ROOT, right), "utf8");
    assert.equal(a, b, left);
  }

  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3\.1\.0"/);
  assert.equal(blocked.plane_id, "NONE");
  assert.equal(blocked.requirement.id, "W3-INFRA-REQ-1");
});

test("an empty runtime keeps missing evidence visible", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const reading = runtime.productHealth(rt);
  assert.equal(reading.kind, "W3_PRODUCT_HEALTH_FAILURE_TRUTH");
  assert.equal(reading.producer_classification, "W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL");
  assert.equal(reading.product_state, "EVIDENCE_UNAVAILABLE");
  assert.equal(reading.product_plane, "OBSERVATION");
  assert.equal(reading.product_success, false);
  assert.equal(reading.success_emitted, false);
  assert.equal(reading.optimistic_success, false);
  assert.equal(reading.green, false);
  assert.equal(reading.ok, true);
  assert.equal(reading.code, null);
  assert.equal(reading.eligible_plane, "NONE");
  assert.equal(reading.named_eligible_plane, false);
  assert.equal(reading.infra_requirement, "W3-INFRA-REQ-1");
  assert.equal(reading.execution_ceiling, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.ceiling_raised, false);
  assert.equal(reading.host_attachment, false);
  assert.equal(reading.host_attachment_status, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.host_enforcement.status, "ABSENT");
  assert.equal(reading.absent_planes.includes("HOST_ENFORCEMENT"), true);
  assert.equal(reading.healthier_token_selected, false);
  assert.deepEqual(reading.vocabulary.states, contract.states);
  assert.deepEqual(reading.vocabulary.states_added, []);
  assert.equal(contract.states.includes(reading.product_state), true);
  assert.equal(reading.visible_evidence.some((row) => row.field === "freshness" && row.value === "UNKNOWN" && row.collapsed_to_success === false), true);
  assert.equal(reading.visible_evidence.some((row) => row.state === "EVIDENCE_UNAVAILABLE" && row.evidence === "MISSING"), true);
  assert.equal(reading.visible_evidence.some((row) => row.collapsed_to_success === true), false);
  assert.deepEqual(runtime.snapshot(rt).product_health, reading);
});

test("a success or attachment request does not change the derived state", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const refused = runtime.productHealth(rt, {
    success: "SUCCESS",
    green: true,
    product_state: "HEALTHY_ENFORCING",
  });
  assert.equal(refused.code, "OPTIMISTIC_SUCCESS_REFUSED");
  assert.equal(refused.product_state, "EVIDENCE_UNAVAILABLE");
  assert.equal(refused.product_success, false);
  assert.equal(refused.optimistic_success, false);
  assert.equal(refused.requested_product_state_ignored, true);
  assert.equal(rt.host_attachment, false);

  const attached = runtime.productHealth(rt, { attach_host: true, load_ebpf: true, success: true });
  assert.equal(attached.code, "ATTACHMENT_REFUSED");
  assert.equal(attached.host_attachment, false);
  assert.equal(attached.ebpf_loaded, false);
  assert.equal(attached.product_state, "EVIDENCE_UNAVAILABLE");
  assert.equal(rt.ebpf_loaded, false);

  const malformed = runtime.productHealth(rt, "SUCCESS");
  assert.equal(malformed.code, "BAD_INPUT");
  assert.equal(malformed.product_state, "EVIDENCE_UNAVAILABLE");
  assert.equal(malformed.product_success, false);
});

test("process up and HTTP 200 stay enforcement unknown", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const recorded = must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ signals: { process_up: true, http_status: 200 } }),
    options: OPTIONS,
  }));
  assert.equal(recorded.quote.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(recorded.quote.green, false);
  const reading = runtime.productHealth(rt);
  assert.equal(reading.product_state, "ENFORCEMENT_UNKNOWN");
  assert.equal(reading.product_plane, "OBSERVATION");
  assert.equal(reading.product_success, false);
  assert.equal(reading.success_emitted, false);
  assert.equal(reading.unknown_evidence_collapsed_to_success, false);
  assert.equal(reading.health_observations.length, 1);
  assert.equal(reading.health_observations[0].evidence, "UNKNOWN");
  assert.equal(reading.health_observations[0].reported_as_host_enforcement, false);
  assert.equal(reading.health_observations[0].plane, "OBSERVATION");
  assert.equal(reading.host_enforcement.status, "NOT_APPLIED");
  assert.equal(reading.host_enforcement.execution, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.host_enforcement.applied, false);
});

test("disagreed health states stay visible and do not pick the healthier token", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ facts: [enforcingFact()] }),
    options: OPTIONS,
  }));
  must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ facts: [observingFact()] }),
    options: OPTIONS,
  }));
  const reading = runtime.productHealth(rt);
  assert.equal(reading.product_state, "ENFORCEMENT_UNKNOWN");
  assert.equal(reading.rollup_reason, "health_states_disagree");
  assert.equal(reading.healthier_token_selected, false);
  assert.deepEqual(reading.visible_states, ["HEALTHY_ENFORCING", "HEALTHY_OBSERVING"]);
  assert.equal(reading.health_observations[0].failure_classification, "fail_closed");
  assert.equal(reading.health_observations[0].failure_classification_basis, "TOKEN_MEANING");
  assert.equal(reading.health_observations[0].plane, "OBSERVATION");
  assert.equal(reading.health_observations[0].reported_as_host_enforcement, false);
  assert.equal(reading.health_observations[1].failure_classification, "fail_open");
  assert.equal(reading.health_observations[1].plane, "OBSERVATION");
  assert.equal(reading.healthy_enforcing_reported_as_host_enforcement, false);
  assert.equal(reading.host_enforcement.applied, false);
  assert.equal(reading.product_success, false);
});

test("HEALTHY_ENFORCING, BLOCKED_HOST, ENFORCE, and PROMOTED_MATCH stay off host enforcement", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const health = must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ facts: [enforcingFact()] }),
    options: OPTIONS,
  }));
  assert.equal(health.quote.state, "HEALTHY_ENFORCING");
  assert.equal(health.quote.failure_classification, "fail_closed");
  assert.equal(health.quote.failure_classification_basis, "TOKEN_MEANING");
  assert.equal(health.quote.evidence_source, "PROTECTION_EVALUATION");
  assert.equal(health.planes.OBSERVATION.status, "HEALTHY_ENFORCING");
  assert.equal(health.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");

  const denied = must(runtime.integrate(rt, {
    op: "egress",
    input: {
      policy: policy({ blocked_hosts: ["evil.example"] }),
      path: { id: "app_fetch" },
      attempt: attempt({
        destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
      }),
    },
  }));
  assert.equal(denied.quote.live_wire_action, "BLOCKED_HOST");
  assert.equal(denied.planes.DECISION.status, "DENIED");
  assert.equal(denied.planes.HOST_ENFORCEMENT.applied, false);

  promote(rt);
  const reading = runtime.productHealth(rt);
  assert.equal(reading.ok, true, reading.code);
  assert.equal(reading.product_state, "HEALTHY_ENFORCING");
  assert.equal(reading.product_plane, "OBSERVATION");
  assert.equal(reading.product_success, false);
  assert.equal(reading.green, false);
  assert.equal(reading.proved, false);
  assert.equal(reading.active_protection, false);
  assert.equal(reading.host_attachment, false);
  assert.equal(reading.host_attachment_status, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.execution_ceiling, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.eligible_plane, "NONE");
  assert.equal(reading.infra_requirement, "W3-INFRA-REQ-1");
  assert.equal(reading.healthy_enforcing_reported_as_host_enforcement, false);
  assert.equal(reading.blocked_host_reported_as_host_enforcement, false);
  assert.equal(reading.enforce_stage_reported_as_host_enforcement, false);
  assert.equal(reading.promoted_match_reported_as_host_enforcement, false);
  assert.equal(reading.reported_as_host_enforcement, false);
  assert.equal(reading.decision_reported_as_enforcement, false);
  assert.equal(reading.host_enforcement.status, "NOT_APPLIED");
  assert.equal(reading.host_enforcement.execution, "HOST_ATTACHMENT_FALSE");
  assert.equal(reading.host_enforcement.applied, false);
  assert.equal(reading.host_enforcement.kernel_executed, false);
  assert.equal(reading.application_enforcement.applied, false);

  const enforcing = reading.health_observations.find((row) => row.token === "HEALTHY_ENFORCING");
  const blockedHost = reading.decision_citations.find((row) => row.token === "BLOCKED_HOST");
  const enforce = reading.decision_citations.find((row) => row.token === "ENFORCE");
  const promoted = reading.decision_citations.find((row) => row.token === "PROMOTED_MATCH");
  assert.equal(enforcing.plane, "OBSERVATION");
  assert.equal(enforcing.required_plane, "OBSERVATION");
  assert.equal(enforcing.reported_as_host_enforcement, false);
  assert.equal(enforcing.token_is_not_a_latch, true);
  assert.equal(enforcing.failure_classification, "fail_closed");
  assert.equal(blockedHost.plane, "DECISION");
  assert.equal(blockedHost.failure_classification, null);
  assert.equal(blockedHost.reported_as_host_enforcement, false);
  assert.equal(blockedHost.application_enforcement_applied, false);
  assert.equal(enforce.plane, "DECISION");
  assert.equal(enforce.reported_as_host_enforcement, false);
  assert.equal(promoted.plane, "DECISION");
  assert.equal(promoted.reported_as_host_enforcement, false);
  assert.equal(reading.freshness, "UNKNOWN");
  assert.equal(reading.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.equal(runtime.snapshot(rt).in_process_promoted_rules_are_host_enforcement, false);
  assert.equal(runtime.snapshot(rt).host_attachment, false);
});

test("a host plane that repeats a health token stays a honesty fault", () => {
  const host = plane("HEALTHY_ENFORCING", "HOST_ATTACHMENT_FALSE");
  const observation = plane("HEALTHY_ENFORCING", "EVALUATE_ONLY");
  const absent = plane("ABSENT", null);
  const contribution = {
    capability: "shared_health",
    op: "health",
    quote: {
      state: "HEALTHY_ENFORCING",
      freshness: "UNKNOWN",
      failure_classification: "fail_closed",
      failure_classification_basis: "TOKEN_MEANING",
      evidence_source: "PROTECTION_EVALUATION",
      green: false,
      proved: false,
      token_is_not_a_latch: true,
    },
    planes: {
      OBSERVATION: observation,
      DECISION: absent,
      APPLICATION_ENFORCEMENT: plane("NOT_APPLIED", "EVALUATE_ONLY"),
      HOST_ENFORCEMENT: host,
      CONTAINMENT: absent,
      REVOCATION: absent,
      EVIDENCE: plane("QUOTED", "EVALUATE_ONLY"),
      INDEPENDENT_VERIFICATION: plane("NOT_INDEPENDENTLY_VERIFIED", "NOT_PERFORMED"),
    },
  };
  const reading = runtime.composeProductHealth({ contributions: [contribution] }, {
    planes: contribution.planes,
    request: {},
  });
  assert.equal(reading.code, "HONESTY_FAULT");
  assert.equal(reading.ok, false);
  assert.equal(reading.product_success, false);
  assert.equal(reading.success_emitted, false);
  assert.equal(reading.healthy_enforcing_reported_as_host_enforcement, true);
  assert.equal(reading.health_observations[0].plane, "HOST_ENFORCEMENT");
  assert.equal(reading.health_observations[0].required_plane, "OBSERVATION");
  assert.equal(reading.health_observations[0].reported_as_host_enforcement, true);
  assert.equal(reading.green, false);
});
