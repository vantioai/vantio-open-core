"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const runtime = require("../../internal/pe-integrated-runtime/src/index.cjs");
const { listenCase, permitCase } = require("../pe-ingress/fixtures.cjs");
const { attempt, hostObservation, policy } = require("../pe-egress/fixture.cjs");
const { baseInput, enforcingFact, observingFact, OPTIONS } = require("../shared-health-runtime/helpers.cjs");
const seq = require("../pe-sequential-authority/fixture.cjs");

const HISTORY = JSON.parse(fs.readFileSync(
  path.join(__dirname, "../../packages/pe-progressive-enforcement/fixtures/history.json"),
  "utf8",
)).events;

function must(result) {
  assert.equal(result.ok, true, `${result.code} ${JSON.stringify(result.problems)}`);
  assert.equal(result.active_protection, false);
  assert.equal(result.host_attachment, false);
  assert.equal(result.ebpf_loaded, false);
  assert.equal(result.kernel_executed, false);
  assert.equal(result.applied_to_host, false);
  assert.equal(result.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.equal(result.planes.INDEPENDENT_VERIFICATION.status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.equal(result.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(result.planes.APPLICATION_ENFORCEMENT.applied, false);
  assert.equal(result.planes.HOST_ENFORCEMENT.active_protection, false);
  assert.equal(result.planes.APPLICATION_ENFORCEMENT.active_protection, false);
  return result;
}

function notEnforcement(result) {
  assert.notEqual(result.planes.HOST_ENFORCEMENT.status, "APPLIED");
  assert.notEqual(result.planes.APPLICATION_ENFORCEMENT.status, "APPLIED");
  assert.equal(result.planes.HOST_ENFORCEMENT.kernel_executed, false);
  assert.equal(result.quote && result.quote.kernel_executed === true, false);
}

test("registers and posture keep the council token unclosed", () => {
  assert.equal(runtime.PRODUCER_CLASSIFICATION, "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL");
  assert.equal(runtime.POSTURE.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(runtime.POSTURE.council_verdict, null);
  assert.equal(runtime.POSTURE.host_attachment, false);
  assert.equal(runtime.POSTURE.host_attachment_status, "HOST_ATTACHMENT_FALSE");
  assert.equal(runtime.POSTURE.clean_host_internal_proof, false);
  assert.equal(runtime.POSTURE.proved_external, false);
  assert.equal(runtime.POSTURE.active_protection, false);
  assert.equal(runtime.POSTURE.decision_reported_as_enforcement, false);
  assert.equal(runtime.POSTURE.contract_reported_as_kernel_enforcement, false);
  assert.equal(runtime.POSTURE.unattached_mechanism_reported_as_active_protection, false);
  assert.deepEqual(runtime.RUNTIME_REGISTER.preferred_execution, [
    "CONTRACT_ONLY",
    "EVALUATE_ONLY",
    "HOST_ATTACHMENT_FALSE",
  ]);
  assert.equal(runtime.RUNTIME_REGISTER.host_attachment, false);
  assert.equal(runtime.INTEGRATION_REGISTER.kernel_executed, false);
  for (const row of runtime.INTEGRATION_REGISTER.rows) {
    assert.equal(row.active_protection, false, row.id);
    assert.equal(row.host_attachment, false, row.id);
    assert.equal(row.kernel_executed, false, row.id);
    assert.equal(row.planes_not_applied.length > 0, true, row.id);
  }
});

test("shared health tokens stay observations", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const observing = must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ facts: [observingFact()] }),
    options: OPTIONS,
  }));
  assert.equal(observing.quote.state, "HEALTHY_OBSERVING");
  assert.equal(observing.quote.token_is_not_a_latch, true);
  assert.equal(observing.quote.green, false);
  assert.equal(observing.planes.OBSERVATION.status, "HEALTHY_OBSERVING");
  assert.equal(observing.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(observing.planes.HOST_ENFORCEMENT.execution, "HOST_ATTACHMENT_FALSE");
  assert.equal(observing.child.audit.live_phantom_enforcement_changed, false);

  const enforcing = must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ facts: [enforcingFact()] }),
    options: OPTIONS,
  }));
  assert.equal(enforcing.quote.state, "HEALTHY_ENFORCING");
  assert.equal(enforcing.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(enforcing.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(enforcing.active_protection, false);
  notEnforcement(enforcing);
  const healthOnly = runtime.snapshot(rt);
  assert.equal(healthOnly.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(healthOnly.planes.HOST_ENFORCEMENT.execution, "HOST_ATTACHMENT_FALSE");
  assert.equal(healthOnly.active_protection, false);
});

test("ingress observation and a held decision stay off the enforcement planes", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const input = listenCase();
  const before = JSON.stringify(input);
  const observed = must(runtime.integrate(rt, { op: "ingress", input }));
  assert.equal(JSON.stringify(input), before);
  assert.equal(observed.quote.authority, "OBSERVED_ONLY");
  assert.equal(observed.quote.packet_effect, "NOT_APPLIED");
  assert.equal(observed.planes.OBSERVATION.present, true);
  assert.equal(observed.planes.DECISION.status, "OBSERVED_ONLY");
  assert.equal(observed.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(observed.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(observed.policy_version.applied_to_host, false);
  assert.equal(observed.policy_version.version_id, "v3");

  const held = must(runtime.integrate(rt, { op: "ingress", input: permitCase() }));
  assert.equal(held.quote.authority, "HELD");
  assert.equal(held.planes.DECISION.status, "HELD");
  assert.equal(held.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(held.quote.ingress_protected_claim, false);
  assert.equal(held.quote.live_loader_mutated, false);
  notEnforcement(held);

  const revoked = must(runtime.integrate(rt, { op: "revoke_ingress", grant_id: held.quote.grant_id }));
  assert.equal(revoked.quote.reason, "revoked");
  assert.equal(revoked.quote.idp_revoke, "NOT_EXECUTED");
  assert.equal(revoked.planes.REVOCATION.status, "RECORDED_NOT_HOST");
  assert.equal(revoked.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
});

test("ingress rollback records a new version and does not apply it to a host", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  must(runtime.integrate(rt, { op: "ingress", input: permitCase() }));
  const rolled = must(runtime.integrate(rt, { op: "rollback_ingress" }));
  assert.equal(rolled.quote.reason, "rolled_back_not_granted");
  assert.equal(rolled.quote.packet_effect, "NOT_APPLIED");
  assert.match(rolled.policy_version.version_id, /^rollback:/);
  assert.equal(rolled.policy_version.origin, "ingress_rollback");
  assert.equal(rolled.policy_version.applied_to_host, false);
  assert.equal(rolled.policy_version.kernel_maps_changed, false);
  assert.equal(rolled.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
});

test("egress application decisions and host contracts stay unapplied", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
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
  assert.equal(denied.capability, "egress_application");
  assert.equal(denied.quote.result, "DENIED");
  assert.equal(denied.quote.live_wire_action, "BLOCKED_HOST");
  assert.equal(denied.quote.would_wire_applied, false);
  assert.equal(denied.planes.DECISION.status, "DENIED");
  assert.equal(denied.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(denied.planes.APPLICATION_ENFORCEMENT.execution, "EVALUATE_ONLY");
  assert.equal(denied.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(denied.quote.this_force_executed_host, false);
  assert.equal(denied.quote.this_force_executed_network, false);

  const host = must(runtime.integrate(rt, {
    op: "egress",
    input: {
      policy: policy({ blocked_ips: ["203.0.113.0/24"] }),
      path: { id: "host_tc_enrolled" },
      attempt: attempt({
        destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
        host_observation: hostObservation({ dropped: true }),
      }),
    },
  }));
  assert.equal(host.capability, "egress_host");
  assert.equal(host.quote.result, "DENIED");
  assert.equal(host.planes.DECISION.execution, "CONTRACT_ONLY");
  assert.equal(host.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(host.planes.HOST_ENFORCEMENT.execution, "CONTRACT_ONLY");
  assert.equal(host.planes.HOST_ENFORCEMENT.kernel_executed, false);
  assert.equal(host.quote.this_force_executed_host, false);
});

test("a cited file deny is a contract row and not kernel enforcement", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const decision = must(runtime.integrate(rt, {
    op: "host_contract",
    attempt: { surface: "files", op: "open", path: "/etc/crontab", uid: 1, pid: 100 },
  }));
  assert.equal(decision.quote.disposition, "DENIED_BY_CITED_MECHANISM");
  assert.equal(decision.quote.execution, "CONTRACT_ONLY");
  assert.equal(decision.quote.kernel_executed, false);
  assert.equal(decision.quote.cited_effect, "EACCES");
  assert.equal(decision.quote.cited_effect_applied, false);
  assert.equal(decision.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(decision.planes.DECISION.status, "DENIED_BY_CITED_MECHANISM");
  assert.equal(decision.active_protection, false);
});

test("descendant host inherit and descendant grants stay evaluate-only", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const inherited = must(runtime.integrate(rt, {
    op: "descendant_host",
    attempt: { surface: "descendants", op: "fork_inherit", trace_id: "0x0c1a" },
  }));
  assert.equal(inherited.quote.disposition, "INHERIT_NO_WIDEN");
  assert.equal(inherited.quote.kernel_executed, false);
  assert.equal(inherited.planes.HOST_ENFORCEMENT.execution, "CONTRACT_ONLY");
  assert.equal(inherited.planes.HOST_ENFORCEMENT.applied, false);

  const denied = must(runtime.integrate(rt, {
    op: "descendant_grant",
    parent: seq.root(),
    request: seq.grantRequest({ destinations: ["dest-a", "dest-c"] }),
  }));
  assert.equal(denied.quote.invariant, "CHILD_CANNOT_EXCEED_INHERITANCE");
  assert.equal(denied.quote.enforcement, "EVALUATE_ONLY");
  assert.equal(denied.quote.host_attachment, false);
  assert.equal(denied.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");

  const allowed = must(runtime.integrate(rt, {
    op: "descendant_grant",
    parent: seq.root(),
    request: seq.grantRequest(),
  }));
  assert.equal(allowed.quote.disposition, "ALLOW");
  assert.equal(allowed.quote.reason, "subset_grant");
  assert.equal(allowed.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(allowed.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(allowed.active_protection, false);
});

test("process lineage and sequential authority do not attach", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const counted = must(runtime.integrate(rt, {
    op: "lineage",
    input: {
      envelope: seq.root(),
      catalog: seq.catalogOf(seq.root()),
      ledger: seq.api.emptyLedger(),
      step: seq.step({ authority_source: "process_count" }),
      now: 10,
    },
  }));
  assert.equal(counted.capability, "process_lineage");
  assert.equal(counted.quote.reason, "process_count_is_not_a_source");
  assert.equal(counted.quote.axis, "lineage");
  assert.equal(counted.planes.OBSERVATION.status, "LINEAGE_EVALUATED");
  assert.equal(counted.quote.enforcement, "EVALUATE_ONLY");
  assert.equal(counted.quote.host_attachment, false);

  const allowed = must(runtime.integrate(rt, {
    op: "sequential",
    input: {
      envelope: seq.root(),
      catalog: seq.catalogOf(seq.root()),
      ledger: seq.api.emptyLedger(),
      step: seq.step(),
      now: 10,
    },
  }));
  assert.equal(allowed.capability, "sequential_aggregate");
  assert.equal(allowed.quote.disposition, "ALLOW");
  assert.equal(allowed.quote.doctrine_present, false);
  assert.equal(allowed.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(allowed.planes.DECISION.status, "ALLOW");

  const revoked = must(runtime.integrate(rt, {
    op: "revoke_sequential",
    catalog: seq.catalogOf(seq.root()),
    ledger: seq.api.emptyLedger(),
    envelope_id: "env-root",
    now: 10,
  }));
  assert.deepEqual(revoked.quote.revoked_ids, ["env-root"]);
  assert.equal(revoked.planes.REVOCATION.status, "RECORDED_NOT_HOST");
  assert.equal(revoked.quote.host_attachment, false);
});

test("progressive promotion is an in-process decision", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const signal = { subject_ref: "agent-a", host: "api.example.com", byte_count: 120, at: 10 };
  must(runtime.integrate(rt, {
    op: "progressive",
    step: "discover",
    input: { rule_id: "rule-host", actor: "ada", signal },
  }));
  const observed = must(runtime.integrate(rt, {
    op: "progressive",
    step: "observe",
    input: { rule_id: "rule-host", actor: "ada", observation: signal },
  }));
  assert.equal(observed.planes.OBSERVATION.present, true);
  assert.equal(observed.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(observed.quote.host_attachment, "NOT_PERFORMED");

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
  const promoted = must(runtime.integrate(rt, {
    op: "progressive",
    step: "promote",
    input: { rule_id: "rule-host", actor: "ada", approver: "bao", rollout_request: "COHORT" },
  }));
  assert.equal(promoted.quote.stage, "ENFORCE");
  assert.equal(promoted.planes.DECISION.status, "ENFORCE");
  assert.equal(promoted.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(promoted.quote.live_enforcement, false);
  assert.equal(promoted.quote.enforcement_attached, false);

  const match = must(runtime.integrate(rt, {
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
  assert.equal(match.quote.decision_class, "PROMOTED_MATCH");
  assert.equal(match.quote.applied_to_host, false);
  assert.equal(match.planes.DECISION.status, "PROMOTED_MATCH");
  assert.equal(match.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(match.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(match.planes.HOST_ENFORCEMENT.execution, "HOST_ATTACHMENT_FALSE");

  const view = runtime.snapshot(rt);
  assert.deepEqual(view.in_process_promoted_rule_ids, ["rule-host"]);
  assert.equal(view.in_process_promoted_rules_are_host_enforcement, false);
  assert.equal(view.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(view.active_protection, false);

  const rolled = must(runtime.integrate(rt, {
    op: "progressive",
    step: "revoke_or_rollback",
    input: { rule_id: "rule-host", actor: "cy", reason: "stop", lifecycle_op: "rollback" },
  }));
  assert.equal(rolled.quote.stage, "REVOKE_OR_ROLLBACK");
  assert.equal(rolled.planes.REVOCATION.status, "RECORDED_NOT_HOST");
  assert.equal(rolled.planes.HOST_ENFORCEMENT.applied, false);
  assert.deepEqual(runtime.snapshot(rt).in_process_promoted_rule_ids, []);
});

test("policy versions and uninstall are records", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const version = must(runtime.integrate(rt, {
    op: "policy_version",
    input: { version_id: "pol-1", digest: "abc", capability: "policy_versioning" },
  }));
  assert.equal(version.policy_version.applied_to_host, false);
  assert.equal(version.policy_version.kernel_maps_changed, false);
  assert.equal(version.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");

  const hostVersion = must(runtime.integrate(rt, {
    op: "host_contract",
    attempt: {
      surface: "policy_tampering",
      actor: "security",
      decision_id: "d1",
      version: "v9",
      actor_id: "sec-1",
      rollback_target: "v8",
    },
  }));
  assert.equal(hostVersion.quote.disposition, "ACCEPTED_CONTRACT_RECORD_ONLY");
  assert.equal(hostVersion.quote.maps_changed, false);
  assert.equal(hostVersion.quote.kernel_activated, false);
  assert.equal(hostVersion.policy_version.origin, "host_contract_citation");
  assert.equal(hostVersion.policy_version.applied_to_host, false);

  const removed = must(runtime.integrate(rt, {
    op: "uninstall",
    input: { reason: "operator record" },
  }));
  assert.equal(removed.quote.status, "RECORDED_NOT_PERFORMED");
  assert.equal(removed.quote.performed, false);
  assert.equal(removed.quote.files_removed, false);
  assert.equal(runtime.snapshot(rt).uninstall.performed, false);

  const evidence = must(runtime.integrate(rt, { op: "evidence" }));
  assert.equal(evidence.quote.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.equal(evidence.planes.EVIDENCE.status, "RECORDED");
  assert.equal(evidence.child.length > 0, true);
});

test("a composed case keeps every enforcement plane unapplied", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const composed = runtime.integrateAll(rt, [
    { op: "health", input: baseInput({ facts: [observingFact()] }), options: OPTIONS },
    { op: "ingress", input: listenCase() },
    {
      op: "egress",
      input: {
        policy: policy(),
        path: { id: "app_fetch" },
        attempt: attempt(),
      },
    },
  ]);
  assert.equal(composed.ok, true);
  assert.equal(composed.active_protection, false);
  assert.equal(composed.host_attachment, false);
  assert.equal(composed.ebpf_loaded, false);
  assert.equal(composed.snapshot.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(composed.snapshot.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(composed.snapshot.independent_verification_status, "NOT_INDEPENDENTLY_VERIFIED");
  assert.equal(composed.snapshot.clean_host_internal_proof, false);
  assert.equal(composed.snapshot.proved_external, false);
});
