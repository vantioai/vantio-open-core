"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const composition = require("../../internal/enterprise-runtime-integration/src/index.cjs");
const eg = require("../../internal/enterprise-governance/src/index.cjs");
const { envelope, grantInput, world } = require("../enterprise-e1-e3/fixture.cjs");
const { attempt, hostObservation, policy } = require("../pe-egress/fixture.cjs");
const { baseInput, enforcingFact, OPTIONS } = require("../shared-health-runtime/helpers.cjs");

function must(result) {
  assert.equal(result.ok, true, `${result.code} ${JSON.stringify(result.problems || result.quote)}`);
  assert.equal(result.live_customer_authority, false);
  assert.equal(result.customer_authority_promoted, false);
  assert.equal(result.host_attachment, false);
  assert.equal(result.kernel_executed, false);
  assert.equal(result.active_protection, false);
  assert.equal(result.applied_to_host, false);
  assert.equal(result.record_layer_only, true);
  assert.equal(result.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(result.planes.APPLICATION_ENFORCEMENT.applied, false);
  assert.equal(result.planes.INDEPENDENT_VERIFICATION.status, "NOT_INDEPENDENTLY_VERIFIED");
  return result;
}

function opened() {
  const { store } = world();
  return composition.createComposition({ store, now: () => 5000 });
}

test("registers keep the council token and the wave 2 close", () => {
  assert.equal(composition.PRODUCER_CLASSIFICATION, "W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL");
  assert.equal(composition.WAVE2_CLOSE, "ENTERPRISE_E1_E3_INTERNAL_MERGED_RECORD_LAYER_ONLY_NO_LIVE_CUSTOMER_AUTHORITY");
  assert.equal(composition.POSTURE.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(composition.POSTURE.council_verdict, null);
  assert.equal(composition.POSTURE.live_customer_authority, false);
  assert.equal(composition.POSTURE.record_layer_only, true);
  assert.equal(composition.POSTURE.host_attachment, false);
  assert.equal(composition.POSTURE.host_attachment_status, "HOST_ATTACHMENT_FALSE");
  assert.equal(composition.POSTURE.active_protection, false);
  assert.equal(composition.POSTURE.published, false);
  assert.equal(composition.POSTURE.announced, false);
  assert.equal(composition.POSTURE.frozen_version_reopened, false);
  assert.equal(composition.POSTURE.decision_reported_as_enforcement, false);
  assert.equal(composition.STATUS.producer_classification, composition.PRODUCER_CLASSIFICATION);
  assert.equal(composition.CITED_REQUIREMENTS["EG-E2-8"], "RECORD_LAYER_ONLY_HOST_UNSATISFIED");
  assert.equal(composition.CITED_REQUIREMENTS["EG-E3-8"], "HOST_UNSATISFIED");
  for (const row of composition.INTEGRATION_REGISTER.rows) {
    assert.equal(row.live_customer_authority, false, row.id);
    assert.equal(row.customer_authority_promoted, false, row.id);
    assert.equal(row.host_attachment, false, row.id);
    assert.equal(row.kernel_executed, false, row.id);
    assert.equal(row.active_protection, false, row.id);
    assert.equal(row.planes_not_applied.includes("HOST_ENFORCEMENT"), true, row.id);
    assert.equal(row.planes_not_applied.includes("APPLICATION_ENFORCEMENT"), true, row.id);
  }
});

test("an approved narrow stays a decision and does not apply enforcement", () => {
  const comp = opened();
  const narrowed = must(composition.integrate(comp, {
    op: "policy",
    input: {
      class: "NARROW",
      parties: ["root-a"],
      next_policy: envelope({ spend_cap: 40 }),
    },
  }));
  assert.equal(narrowed.quote.outcome, "APPROVED");
  assert.equal(narrowed.quote.reason, "POLICY_NARROWED");
  assert.equal(narrowed.quote.record_policy_written, true);
  assert.equal(narrowed.quote.applied_to_host, false);
  assert.equal(narrowed.quote.live_customer_authority, false);
  assert.equal(narrowed.planes.DECISION.status, "APPROVED");
  assert.equal(narrowed.planes.DECISION.execution, "EVALUATE_ONLY");
  assert.equal(narrowed.planes.OBSERVATION.status, "ABSENT");
  assert.equal(narrowed.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(narrowed.planes.APPLICATION_ENFORCEMENT.execution, "EVALUATE_ONLY");
  assert.equal(narrowed.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(narrowed.planes.HOST_ENFORCEMENT.execution, "HOST_ATTACHMENT_FALSE");
  assert.notEqual(narrowed.planes.APPLICATION_ENFORCEMENT.status, narrowed.planes.DECISION.status);
  assert.equal(narrowed.child.live_customer_authority, false);
  assert.equal(narrowed.child.host_contacted, false);
  const view = composition.snapshot(comp);
  assert.equal(view.live_customer_authority, false);
  assert.equal(view.wave2_close, composition.WAVE2_CLOSE);
  assert.equal(view.enterprise.host_enrolled, false);
  assert.equal(view.enterprise.policy_version, 2);
  assert.equal(view.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(view.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(view.pe.host_attachment, false);
  assert.equal(view.pe.kernel_executed, false);
});

test("an enroll intent records the ask and leaves the host unattached", () => {
  const comp = opened();
  const intent = must(composition.integrate(comp, {
    op: "host_intent",
    input: { class: "ROOT", parties: ["root-a"], intent: "enroll", host_id: "h1" },
  }));
  assert.equal(intent.quote.outcome, "RECORDED");
  assert.equal(intent.child.intent.enrolled, false);
  assert.equal(intent.child.intent.protected, false);
  assert.equal(intent.child.intent.enforced, false);
  assert.equal(intent.child.intent.performed_here, false);
  assert.equal(intent.child.host_enrolled, false);
  assert.equal(intent.planes.OBSERVATION.status, "HOST_INTENT_RECORDED");
  assert.equal(intent.planes.OBSERVATION.execution, "NOT_PERFORMED");
  assert.equal(intent.planes.DECISION.status, "RECORDED");
  assert.equal(intent.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(intent.planes.HOST_ENFORCEMENT.execution, "HOST_ATTACHMENT_FALSE");
  assert.equal(comp.pe.host_attachment, false);
  assert.equal(comp.pe.ebpf_loaded, false);
  assert.equal(comp.pe.active_protection, false);
  assert.equal(composition.snapshot(comp).enterprise.host_enrolled, false);
});

test("a cited enterprise policy version is stored with applied_to_host false", () => {
  const comp = opened();
  must(composition.integrate(comp, {
    op: "policy",
    input: {
      class: "NARROW",
      parties: ["root-a"],
      next_policy: envelope({ spend_cap: 40 }),
    },
  }));
  const cited = must(composition.integrate(comp, { op: "cite_policy" }));
  assert.equal(cited.quote.version_id, "eg-policy-2");
  assert.equal(cited.quote.applied_to_host, false);
  assert.equal(cited.quote.kernel_maps_changed, false);
  assert.equal(cited.quote.citation_is_not_a_proof, true);
  assert.equal(cited.quote.certification, false);
  assert.equal(cited.planes.DECISION.status, "RECORDED");
  assert.equal(cited.planes.DECISION.execution, "NOT_PERFORMED");
  assert.equal(cited.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  const view = composition.snapshot(comp);
  assert.equal(view.pe.policy_versions.length, 1);
  assert.equal(view.pe.policy_versions[0].version_id, "eg-policy-2");
  assert.equal(view.pe.policy_versions[0].applied_to_host, false);
  assert.equal(view.pe.policy_versions[0].kernel_maps_changed, false);
  assert.equal(view.pe.policy_versions[0].capability, "enterprise_record_citation");
});

test("a joint record and a PE deny keep the four planes apart", () => {
  const comp = opened();
  const joined = composition.compose(comp, {
    enterprise: {
      op: "policy",
      input: {
        class: "NARROW",
        parties: ["root-a"],
        next_policy: envelope({ spend_cap: 30 }),
      },
    },
    pe: {
      op: "egress",
      input: {
        policy: policy({ blocked_hosts: ["evil.example"] }),
        path: { id: "app_fetch" },
        attempt: attempt({
          destination: { hostname: "evil.example", port: "443", protocol: "https", in_product_scope: true },
        }),
      },
    },
  });
  assert.equal(joined.ok, true, JSON.stringify(joined.enterprise && joined.enterprise.problems));
  assert.equal(joined.enterprise.quote.outcome, "APPROVED");
  assert.equal(joined.pe.quote.result, "DENIED");
  assert.equal(joined.pe.quote.would_wire_applied, false);
  assert.equal(joined.planes.DECISION.status, "SEPARATED");
  assert.equal(joined.separation.decision, "SEPARATED");
  assert.equal(joined.separation.application_enforcement, "NOT_APPLIED");
  assert.equal(joined.separation.host_enforcement, "NOT_APPLIED");
  assert.notEqual(joined.separation.decision, joined.separation.application_enforcement);
  assert.notEqual(joined.separation.decision, joined.separation.host_enforcement);
  assert.equal(joined.planes.APPLICATION_ENFORCEMENT.applied, false);
  assert.equal(joined.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(joined.live_customer_authority, false);
  assert.equal(joined.customer_authority_promoted, false);
  const view = composition.snapshot(comp);
  assert.equal(view.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(view.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(view.pe.active_protection, false);
  assert.equal(view.enterprise.host_protected, false);
});

test("an ended grant stays ended and does not clear a host", () => {
  const comp = opened();
  const granted = must(composition.integrate(comp, { op: "grant", input: grantInput() }));
  assert.equal(granted.quote.outcome, "APPROVED");
  assert.equal(granted.child.grant_id.length > 0, true);
  const ended = must(composition.integrate(comp, {
    op: "clock",
    input: { now: "2100-01-01T00:00:00.000Z" },
  }));
  assert.equal(ended.child.ended_grant_ids.length, 1);
  assert.equal(ended.child.host_expanded_authority_cleared, "UNSATISFIED");
  const back = must(composition.integrate(comp, {
    op: "clock",
    input: { now: "2030-01-01T00:00:00.000Z" },
  }));
  assert.equal(back.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(back.quote.host_expanded_authority_cleared, "UNSATISFIED");
  const grants = eg.snapshot(comp.store).grants;
  assert.equal(grants.length, 1);
  assert.equal(grants[0].record_layer_exercise, "ENDED");
  assert.equal(grants[0].can_exercise, false);
  assert.equal(grants[0].host_expanded_authority_cleared, "UNSATISFIED");
  const before = comp.store.grants.size;
  const spawned = must(composition.integrate(comp, {
    op: "spawn",
    input: { parent_grant_id: granted.child.grant_id },
  }));
  assert.equal(spawned.child.grant_minted, false);
  assert.equal(comp.store.grants.size, before);
  assert.equal(spawned.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
});

test("a host-path contract stays CONTRACT_ONLY beside an enroll record", () => {
  const comp = opened();
  const joined = composition.compose(comp, {
    enterprise: {
      op: "host_intent",
      input: { class: "ROOT", parties: ["root-a"], intent: "enroll", host_id: "h1" },
    },
    pe: {
      op: "egress",
      input: {
        policy: policy({ blocked_ips: ["203.0.113.0/24"] }),
        path: { id: "host_tc_enrolled" },
        attempt: attempt({
          destination: { ip: "203.0.113.9", port: "443", protocol: "tcp" },
          host_observation: hostObservation({ dropped: true }),
        }),
      },
    },
  });
  assert.equal(joined.ok, true, JSON.stringify(joined.pe && joined.pe.problems));
  assert.equal(joined.enterprise.child.intent.enrolled, false);
  assert.equal(joined.pe.quote.result, "DENIED");
  assert.equal(joined.planes.DECISION.status, "SEPARATED");
  assert.equal(joined.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(joined.planes.HOST_ENFORCEMENT.execution, "CONTRACT_ONLY");
  assert.equal(joined.planes.HOST_ENFORCEMENT.kernel_executed, false);
  assert.equal(joined.planes.HOST_ENFORCEMENT.host_attachment, false);
  assert.equal(joined.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(joined.separation.observation, "HOST_INTENT_RECORDED");
  assert.notEqual(joined.separation.observation, joined.separation.host_enforcement);
  assert.equal(comp.pe.ebpf_loaded, false);
  assert.equal(comp.host_attachment, false);
});

test("a freeze and a health token stay off host enforcement", () => {
  const comp = opened();
  const frozen = must(composition.integrate(comp, {
    op: "freeze",
    input: { parties: ["root-a"] },
  }));
  assert.equal(frozen.quote.outcome, "APPROVED");
  assert.equal(frozen.child.host_freeze_performed, false);
  assert.equal(frozen.planes.CONTAINMENT.status, "DECISION_RECORDED_ONLY");
  assert.equal(frozen.planes.CONTAINMENT.execution, "NOT_PERFORMED");
  assert.equal(frozen.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  const health = must(composition.integrate(comp, {
    op: "pe",
    pe: {
      op: "health",
      input: baseInput({ facts: [enforcingFact()] }),
      options: OPTIONS,
    },
  }));
  assert.equal(health.quote.state, "HEALTHY_ENFORCING");
  assert.equal(health.planes.OBSERVATION.status, "HEALTHY_ENFORCING");
  assert.equal(health.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(health.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(health.active_protection, false);
  assert.equal(composition.snapshot(comp).pe.ebpf_loaded, false);
});

test("billing does not move title and a refused host mark stays a decision", () => {
  const comp = opened();
  const billing = must(composition.integrate(comp, {
    op: "billing_or_support",
    input: { source: "billing" },
  }));
  assert.equal(billing.quote.outcome, "REFUSED");
  assert.equal(billing.child.title_holder, "customer_root");
  assert.equal(billing.planes.DECISION.status, "REFUSED");
  assert.equal(billing.planes.HOST_ENFORCEMENT.applied, false);
  const marked = must(composition.integrate(comp, { op: "refuse_host_mark" }));
  assert.equal(marked.quote.outcome, "REJECTED");
  assert.equal(marked.planes.APPLICATION_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(eg.snapshot(comp.store).host_enrolled, false);
});
