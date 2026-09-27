"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { ceiling, customerMaterial, envelope, grantInput, world } = require("./fixture.cjs");

test("customer root holds title and Vantio is outside the root set", () => {
  const { store, founded } = world();
  assert.equal(founded.outcome, "RECORDED");
  assert.equal(founded.title_holder, "customer_root");
  assert.equal(founded.vantio_in_root_set, false);
  assert.equal(founded.workload_authority_expanded, false);
  assert.equal(founded.external_identity_created, false);
  assert.equal(founded.identity_authenticated, false);
  assert.equal(founded.decisions_resolved, false);
  const snap = require("../../internal/enterprise-governance/src/index.cjs").snapshot(store);
  assert.deepEqual(snap.root_ids, ["root-a"]);
  assert.equal(snap.witness_counts_toward_quorum, false);
  assert.deepEqual(snap.title_domains, ["workload", "security", "recovery"]);
  assert.ok(snap.reserved_powers.includes("freeze"));
  assert.equal(snap.grant_count, 0);
  assert.equal(snap.host_enrolled, false);
});

test("host intent stays intent and does not enroll or protect", () => {
  const { eg, store } = world();
  const enroll = eg.recordHostIntent(store, {
    class: "ROOT",
    parties: ["root-a"],
    intent: "enroll",
    host_id: "h1",
  });
  assert.equal(enroll.outcome, "RECORDED");
  assert.equal(enroll.host_enrolled, false);
  assert.equal(enroll.host_protected, false);
  assert.equal(enroll.host_enforced, false);
  assert.equal(enroll.intent.performed_here, false);
  assert.equal(enroll.intent.mechanism, "PHANTOM_ENGINE_ON_CUSTOMER_HOST");
  const retire = eg.recordHostIntent(store, {
    class: "ROOT",
    parties: ["root-a"],
    intent: "retire",
    host_id: "h1",
  });
  assert.equal(retire.intent.retire_contradiction, "VISIBLE_UNRESOLVED");
  assert.equal(retire.host_enforced, false);
});

test("policy widen is approved and is not host attachment", () => {
  const { eg, store } = world();
  const widened = eg.recordPolicyDecision(store, {
    class: "WIDEN",
    parties: ["root-a", "cust-b"],
    witness_ids: ["vantio"],
    not_before: "2026-09-27T00:00:00.000Z",
    not_after: "2026-10-04T00:00:00.000Z",
    next_policy: envelope({ destinations: ["d1", "d2"] }),
    rollback_target: envelope(),
  });
  assert.equal(widened.outcome, "APPROVED");
  assert.equal(widened.enterprise_state, "APPROVED");
  assert.equal(widened.host_state, null);
  assert.equal(widened.verified_on_host, false);
  assert.equal(widened.active_set_by_enterprise_writer, false);
  const approval = store.approvals[store.approvals.length - 1];
  assert.equal(approval.quorum_count, 2);
  assert.deepEqual(approval.parties, ["root-a", "cust-b"]);
  assert.deepEqual(approval.witness_ids, ["vantio"]);
  assert.equal(approval.witness_counts_toward_quorum, false);
  assert.equal(approval.state, "APPROVED");
  assert.equal(approval.can_authorize_host, false);
});

test("a subset grant expires by clock at the record layer and does not mint title", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput());
  assert.equal(granted.outcome, "APPROVED");
  assert.equal(granted.enterprise_state, "APPROVED");
  assert.equal(granted.title_moved, false);
  assert.equal(granted.duration_limit, "NOT_SET");
  const snap = eg.snapshot(store);
  assert.equal(snap.title_holder, "customer_root");
  assert.ok(snap.reserved_powers.includes("remove_witness"));
  assert.equal(snap.grants[0].state, "APPROVED");
  assert.equal(snap.grants[0].redelegation, "forbidden");
  const quoted = eg.quoteHostReport(store, {
    source: "host_report",
    subject_id: granted.grant_id,
    quoted_outcome: "ACTIVE",
    envelope_version: snap.grants[0].version,
  });
  assert.equal(quoted.outcome, "QUOTED");
  assert.equal(quoted.enterprise_state, "APPROVED");
  assert.equal(quoted.quoted_host_outcome, "ACTIVE");
  assert.equal(quoted.verified_on_host, false);
  assert.equal(quoted.host_contacted, false);
  const display = eg.displayGrant(store.grants.get(granted.grant_id));
  assert.equal(display.display_active, true);
  assert.equal(display.display_source, "host_quote");
  assert.equal(display.enterprise_state, "APPROVED");
  const early = eg.noteClock(store, { now: "2019-06-01T00:00:00.000Z" });
  assert.equal(early.outcome, "RECORDED");
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "NOT_YET");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
  const open = eg.noteClock(store, { now: "2026-09-28T00:00:00.000Z" });
  assert.equal(open.outcome, "RECORDED");
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "OPEN");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, true);
  const clock = eg.noteClock(store, { now: "2099-06-01T00:00:00.000Z" });
  assert.equal(clock.outcome, "RECORDED");
  assert.deepEqual(clock.ended_grant_ids, [granted.grant_id]);
  assert.equal(clock.claimed_expired_state, false);
  assert.equal(clock.host_expanded_authority_cleared, "UNSATISFIED");
  assert.equal(store.grants.get(granted.grant_id).state, "APPROVED");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
});

test("root and a security delegate can narrow without a second person", () => {
  const { eg, store } = world();
  const security = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    purpose: "lower caps inside this host",
    scope: envelope({ domains: ["security"], actions: ["read"], destinations: ["d1"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(security.outcome, "APPROVED");
  const byRoot = eg.recordPolicyDecision(store, {
    class: "ROOT",
    parties: ["root-a"],
    next_policy: envelope({ spend_cap: 45 }),
  });
  assert.equal(byRoot.outcome, "APPROVED");
  assert.equal(byRoot.reason, "POLICY_NARROWED");
  const byDelegate = eg.recordPolicyDecision(store, {
    class: "NARROW",
    parties: ["cust-c"],
    next_policy: envelope({ spend_cap: 40 }),
  });
  assert.equal(byDelegate.outcome, "APPROVED");
  assert.equal(eg.snapshot(store).policy.spend_cap, 40);
});

test("recovery and freeze record without Vantio and do not perform the host action", () => {
  const { eg, store } = world();
  eg.nameRecoveryParty(store, { class: "ROOT", parties: ["root-a"], party_id: "cust-c" });
  const named = eg.acceptOpaqueIdentity(store, { id: "recovery-r", kind: "customer" });
  assert.equal(named.external_identity_created, false);
  eg.nameRecoveryParty(store, { class: "ROOT", parties: ["root-a"], party_id: "recovery-r" });
  const recovered = eg.recover({
    store,
    material: customerMaterial({
      parties: ["recovery-r"],
      witness_ids: [],
    }),
  });
  assert.equal(recovered.outcome, "APPROVED");
  assert.equal(recovered.vantio_required, false);
  assert.equal(recovered.host_action_status, "UNSATISFIED");
  assert.equal(recovered.satisfies_host_proof, false);
  assert.equal(recovered.hosted_store_written, false);
  const frozen = eg.recordFreeze({ store, parties: ["root-a"] });
  assert.equal(frozen.outcome, "APPROVED");
  assert.equal(frozen.host_freeze_performed, false);
  assert.equal(frozen.host_action_status, "UNSATISFIED");
  assert.equal(frozen.vantio_required, false);
});

test("revocation returns exercise and leaves title with the customer root", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput());
  const revoked = eg.revokeGrant(store, {
    grant_id: granted.grant_id,
    class: "NARROW",
    parties: ["root-a"],
  });
  assert.equal(revoked.outcome, "APPROVED");
  assert.equal(revoked.title_holder, "customer_root");
  assert.equal(revoked.title_moved, false);
  assert.equal(revoked.host_expanded_authority_cleared, "UNSATISFIED");
  assert.equal(store.grants.get(granted.grant_id).state, "REVOKED");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
});

test("customer evidence copy survives a missing Vantio copy", () => {
  const { eg, store } = world();
  const exported = eg.exportEvidence(store, {
    holder: "customer",
    hash: "abc123def456abc123",
    parties: ["root-a"],
  });
  assert.equal(exported.outcome, "RECORDED");
  assert.equal(exported.customer_keeps_record, true);
  assert.equal(exported.vantio_copy_required, false);
  assert.equal(exported.host_action_status, "UNSATISFIED");
  const hashed = eg.hashEvidence(store, {
    holder: "customer",
    hash: "abc123def456abc123",
    parties: ["root-a"],
  });
  assert.equal(hashed.outcome, "RECORDED");
  assert.equal(eg.snapshot(store).evidence_count, 2);
});

test("spawn does not mint a grant and a child stays inside the parent subset", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput());
  const before = eg.snapshot(store).grant_count;
  const spawned = eg.noteSpawn(store, { parent_grant_id: granted.grant_id });
  assert.equal(spawned.outcome, "RECORDED");
  assert.equal(spawned.grant_minted, false);
  assert.equal(spawned.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(eg.snapshot(store).grant_count, before);
  const child = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    child_envelope: envelope({ domains: ["workload"], actions: ["connect"], destinations: ["d1"], spend_cap: 10, size_cap: 10 }),
  });
  assert.equal(child.outcome, "RECORDED");
  assert.equal(child.grant_minted, false);
  assert.equal(child.within_subset, true);
  assert.equal(eg.snapshot(store).grant_count, before);
});

test("inspect is read only for the root and a read grant", () => {
  const { eg, store } = world();
  const asRoot = eg.inspect(store, { class: "INSPECT", parties: ["root-a"] });
  assert.equal(asRoot.outcome, "APPROVED");
  assert.equal(asRoot.read_only, true);
  const granted = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    scope: envelope({ domains: ["workload"], actions: ["read"], destinations: ["d1"] }),
    rollback_target: envelope({ domains: ["workload"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(granted.outcome, "APPROVED");
  const asReader = eg.inspect(store, { class: "INSPECT", parties: ["cust-c"] });
  assert.equal(asReader.outcome, "APPROVED");
});

test("founding ceiling is explicit and a later widen stops at that ceiling", () => {
  const { eg, store } = world();
  assert.deepEqual(eg.snapshot(store).authority_ceiling.destinations, ["d1", "d2"]);
  const over = eg.recordPolicyDecision(store, {
    class: "WIDEN",
    parties: ["root-a", "cust-b"],
    not_after: "2026-10-04T00:00:00.000Z",
    next_policy: envelope({ destinations: ["d1", "d2", "d3"], spend_cap: 100 }),
    rollback_target: envelope(),
  });
  assert.equal(over.outcome, "REFUSED");
  assert.equal(over.reason, "EXCEEDS_ROOT_ENVELOPE");
  assert.equal(ceiling().spend_cap, 100);
});

test("recognition records a customer handle and does not create a grant or a credential", () => {
  const { eg, store, founded } = world();
  assert.equal(founded.credential_created, false);
  const again = eg.recordRecognizedCustomer(store, {
    class: "ROOT",
    parties: ["root-a"],
    customer_id: "cust-b",
  });
  assert.equal(again.grant_minted, false);
  assert.equal(again.in_root_set, false);
  assert.equal(again.external_identity_created, false);
  assert.equal(eg.snapshot(store).grant_count, 0);
});
