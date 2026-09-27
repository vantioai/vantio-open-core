"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { customerMaterial, envelope, grantInput, world } = require("./fixture.cjs");

function refused(result) {
  assert.notEqual(result.outcome, "APPROVED");
  assert.equal(result.satisfies_host_proof, false);
  assert.equal(result.vantio_sufficient, false);
  assert.equal(result.host_contacted, false);
}

test("rejected acts never authorize", () => {
  const { eg, store } = world();
  const acts = [
    "vantio_only_freeze",
    "vantio_only_revoke",
    "vantio_only_recover",
    "vendor_root_replacement",
    "unsigned_loosening",
    "console_attach",
    "billing_attach",
    "support_attach",
    "workload_self_approval",
    "same_person_dual_control",
    "wider_restore",
    "dry_run_activation",
    "second_enforcement_engine",
    "breakglass_off",
    "erase_evidence",
    "appoint_vantio",
    "mark_host_protected",
    "mark_host_enrolled",
    "mark_host_enforced",
  ];
  for (const act of acts) {
    const result = eg.proposeGrant(store, grantInput({ act }));
    assert.equal(result.outcome, "REJECTED", act);
    assert.equal(result.reason, act.toUpperCase(), act);
  }
  assert.equal(eg.snapshot(store).grant_count, 0);
  assert.equal(eg.refuseHostMark().outcome, "REJECTED");
  assert.equal(eg.refuseSecondEnforcementEngine().reason, "SECOND_ENFORCEMENT_ENGINE");
  assert.equal(eg.refuseDryRunActivation().reason, "DRY_RUN_ACTIVATION");
  assert.equal(eg.refuseBreakglass().class_defined, false);
});

test("Vantio and workloads cannot found or join the root", () => {
  const { eg } = world();
  const store = eg.createCustomerHeldStore();
  eg.acceptOpaqueIdentity(store, { id: "vantio", kind: "vantio" });
  const founded = eg.foundRoot(store, {
    root_identity: "vantio",
    authority_ceiling: envelope({ spend_cap: 100, size_cap: 100 }),
    initial_policy: envelope(),
  });
  assert.equal(founded.outcome, "REJECTED");
  assert.equal(founded.reason, "VANTIO_NOT_IN_ROOT_SET");
  eg.acceptOpaqueIdentity(store, { id: "work-w", kind: "workload" });
  const workloadRoot = eg.foundRoot(store, {
    root_identity: "work-w",
    authority_ceiling: envelope({ spend_cap: 100, size_cap: 100 }),
    initial_policy: envelope(),
  });
  assert.equal(workloadRoot.reason, "WORKLOAD_NOT_ROOT");
  const relabel = eg.acceptOpaqueIdentity(store, { id: "vantio", kind: "customer" });
  assert.equal(relabel.reason, "IDENTITY_KIND_CONFLICT");
});

test("same person, short quorum, and the grant recipient cannot satisfy WIDEN", () => {
  const { eg, store } = world();
  const same = eg.proposeGrant(store, grantInput({ parties: ["root-a", "root-a"] }));
  assert.equal(same.outcome, "REJECTED");
  assert.equal(same.reason, "SAME_PERSON_DUAL_CONTROL");
  const one = eg.proposeGrant(store, grantInput({ parties: ["root-a"] }));
  assert.equal(one.outcome, "PROPOSED");
  assert.equal(one.can_exercise, false);
  const three = eg.proposeGrant(store, grantInput({ parties: ["root-a", "cust-b", "cust-c"] }));
  assert.equal(three.reason, "WIDEN_QUORUM_EXACTLY_TWO");
  const self = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    parties: ["root-a", "cust-c"],
    scope: envelope({ domains: ["security"], actions: ["read"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(self.outcome, "REJECTED");
  assert.equal(self.reason, "SELF_APPROVAL");
  assert.equal(eg.quoteHostReport(store, {
    source: "host_report",
    subject_id: one.grant_id,
    quoted_outcome: "ACTIVE",
    envelope_version: 1,
  }).reason, "NOT_APPROVED");
});

test("agent consensus and role labels are not approval", () => {
  const { eg, store } = world();
  const consensus = eg.proposeGrant(store, grantInput({
    parties: [],
    agent_consensus: { votes: 4, agreed: true },
  }));
  assert.equal(consensus.reason, "CONSENSUS_IS_NOT_APPROVAL");
  assert.equal(consensus.agent_consensus_counted, false);
  const role = eg.recordPolicyDecision(store, {
    class: "ROOT",
    parties: [],
    role_labels: ["customer_root"],
    next_policy: envelope({ spend_cap: 40 }),
  });
  assert.equal(role.reason, "ROLE_IS_NOT_IDENTITY_PROOF");
  assert.equal(role.role_used_as_proof, false);
  const both = eg.proposeGrant(store, grantInput({ agent_consensus: { votes: 9 } }));
  assert.equal(both.outcome, "APPROVED");
  assert.equal(both.agent_consensus_counted, false);
  const unknown = eg.proposeGrant(store, grantInput({ parties: ["customer_root", "admin"] }));
  refused(unknown);
  assert.equal(unknown.reason, "UNKNOWN_IDENTITY");
});

test("workload and redelegation cannot mint security or recovery authority", () => {
  const { eg, store } = world();
  const security = eg.proposeGrant(store, grantInput({
    domain: "security",
    scope: envelope({ domains: ["security"], actions: ["read"] }),
    rollback_target: envelope({ domains: ["security"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(security.reason, "WORKLOAD_CANNOT_HOLD_SECURITY_OR_RECOVERY");
  const recovery = eg.proposeGrant(store, grantInput({ domain: "recovery" }));
  assert.equal(recovery.reason, "WORKLOAD_CANNOT_HOLD_SECURITY_OR_RECOVERY");
  const granted = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    scope: envelope({ domains: ["security"], actions: ["read"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(granted.outcome, "APPROVED");
  const redelegated = eg.proposeGrant(store, grantInput({
    delegator: "cust-c",
    delegate: "cust-b",
    domain: "security",
    scope: envelope({ domains: ["security"], actions: ["read"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(redelegated.reason, "REDELEGATION_FORBIDDEN");
  const allowedFlag = eg.proposeGrant(store, grantInput({ redelegation: "allowed" }));
  assert.equal(allowedFlag.reason, "REDELEGATION_NOT_ALLOWED");
});

test("a grant cannot widen the delegator envelope", () => {
  const { eg, store } = world();
  const destination = eg.proposeGrant(store, grantInput({
    scope: envelope({ domains: ["workload"], destinations: ["d1", "d2"], actions: ["connect"] }),
  }));
  assert.equal(destination.reason, "NOT_A_DELEGATION_WIDENS");
  const cap = eg.proposeGrant(store, grantInput({
    scope: envelope({ domains: ["workload"], actions: ["connect"], spend_cap: 80 }),
  }));
  assert.ok(cap.violations.includes("spend_cap_raised"));
  const path = eg.proposeGrant(store, grantInput({
    scope: envelope({ domains: ["workload"], actions: ["connect"], path_constraints: [] }),
  }));
  assert.ok(path.violations.some((item) => item.startsWith("path_constraint_removed")));
  const open = eg.proposeGrant(store, grantInput({ not_after: undefined, not_before: undefined }));
  assert.equal(open.reason, "EXPIRY_REQUIRED");
  const exclusive = eg.proposeGrant(store, grantInput({ exclusive_to_vantio: ["freeze"] }));
  assert.equal(exclusive.reason, "GRANT_HANDS_POWER_TO_VANTIO");
  assert.equal(eg.snapshot(store).grant_count, 0);
});

test("children cannot inherit more than the permitted subset", () => {
  const { eg, store } = world();
  const before = eg.noteSpawn(store, {});
  assert.equal(before.reason, "SPAWN_DOES_NOT_MINT");
  assert.equal(before.grant_minted, false);
  const granted = eg.proposeGrant(store, grantInput());
  const wider = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    child_envelope: envelope({ domains: ["workload", "security"], actions: ["connect"] }),
  });
  assert.equal(wider.reason, "CHILD_EXCEEDS_PERMITTED_SUBSET");
  assert.equal(wider.grant_minted, false);
  eg.noteClock(store, { now: "2099-06-01T00:00:00.000Z" });
  const after = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    now: "2099-06-01T00:00:00.000Z",
    child_envelope: envelope({ domains: ["workload"], actions: ["connect"], destinations: ["d1"], spend_cap: 50, size_cap: 50 }),
  });
  assert.equal(after.reason, "CHILD_EXCEEDS_PERMITTED_SUBSET");
  const rolled = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    now: "2099-06-01T00:00:00.000Z",
    child_envelope: envelope({ domains: ["workload"], actions: ["connect"], destinations: ["d1"], spend_cap: 10, size_cap: 10 }),
  });
  assert.equal(rolled.inheritance, "ROLLBACK_SCOPE_ONLY");
  assert.equal(rolled.grant_minted, false);
});

test("enterprise writer, console, and dry-run cannot assert ACTIVE", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput());
  for (const source of ["enterprise_writer", "approver_click", "console", "dry_run", "billing", "support"]) {
    const quote = eg.quoteHostReport(store, {
      source,
      subject_id: granted.grant_id,
      quoted_outcome: "ACTIVE",
      envelope_version: 1,
    });
    assert.equal(quote.outcome, "REJECTED", source);
    assert.equal(quote.reason, "ENTERPRISE_WRITER_CANNOT_ASSERT_ACTIVE");
  }
  const mismatch = eg.quoteHostReport(store, {
    source: "host_report",
    subject_id: granted.grant_id,
    quoted_outcome: "ACTIVE",
    envelope_version: 99,
  });
  assert.equal(mismatch.reason, "VERSION_MISMATCH");
  assert.equal(store.grants.get(granted.grant_id).state, "APPROVED");
  assert.equal(store.grants.get(granted.grant_id).host_quote, null);
});

test("delegates cannot perform root acts", () => {
  const { eg, store } = world();
  const owner = eg.changeOwnerSet(store, { class: "ROOT", parties: ["cust-b"], add: ["cust-c"] });
  assert.equal(owner.reason, "DELEGATE_CANNOT_ROOT");
  const witness = eg.removeWitness(store, { class: "ROOT", parties: ["cust-c"] });
  assert.equal(witness.reason, "DELEGATE_CANNOT_ROOT");
  const recovery = eg.nameRecoveryParty(store, { class: "ROOT", parties: ["cust-b"], party_id: "cust-c" });
  assert.equal(recovery.reason, "DELEGATE_CANNOT_ROOT");
  const appoint = eg.nameRecoveryParty(store, { class: "ROOT", parties: ["root-a"], party_id: "vantio" });
  assert.equal(appoint.outcome, "REJECTED");
  assert.equal(appoint.reason, "VANTIO_CANNOT_BE_RECOVERY_PARTY");
  const emptied = eg.changeOwnerSet(store, { class: "ROOT", parties: ["root-a"], remove: ["root-a"] });
  assert.equal(emptied.reason, "ROOT_SET_EMPTY");
  assert.deepEqual(eg.snapshot(store).root_ids, ["root-a"]);
});

test("narrow cannot appoint Vantio, erase evidence, or mark a host", () => {
  const { eg, store } = world();
  for (const act of ["appoint_vantio", "erase_evidence", "mark_host_protected", "mark_host_enrolled", "mark_host_enforced"]) {
    const result = eg.recordPolicyDecision(store, {
      class: "NARROW",
      act,
      parties: ["root-a"],
      next_policy: envelope({ spend_cap: 10 }),
    });
    assert.equal(result.outcome, "REJECTED", act);
  }
  const inspectWrite = eg.inspect(store, {
    class: "INSPECT",
    parties: ["root-a"],
    next_policy: envelope({ spend_cap: 10 }),
  });
  assert.equal(inspectWrite.reason, "INSPECT_IS_READ_ONLY");
});

test("recovery stays inside the three modes and the pre-containment envelope", () => {
  const { eg } = world();
  const wider = eg.recover({
    material: customerMaterial({
      proposed_envelope: envelope({ destinations: ["d1", "d2"] }),
    }),
  });
  assert.equal(wider.outcome, "REJECTED");
  assert.equal(wider.reason, "WIDER_THAN_CEILING");
  const fourth = eg.recover({ material: customerMaterial({ mode: "thaw" }) });
  assert.equal(fourth.reason, "RECOVERY_MODE_REJECTED");
  const quarantined = eg.recover({
    material: customerMaterial({ mode: "stay-quarantined", proposed_envelope: undefined }),
  });
  assert.equal(quarantined.outcome, "APPROVED");
  assert.equal(quarantined.thaw, false);
  assert.equal(quarantined.host_action_status, "UNSATISFIED");
  const observe = eg.recover({
    material: customerMaterial({
      mode: "observe-only",
      proposed_envelope: envelope({ destinations: ["d1", "d2"] }),
    }),
  });
  assert.equal(observe.reason, "WIDER_THAN_CEILING");
  const vantio = eg.recover({
    material: customerMaterial({ parties: ["vantio"] }),
  });
  assert.equal(vantio.reason, "VANTIO_ONLY_RECOVER");
});

test("a recorded freeze blocks later widening and a missing class is refused", () => {
  const { eg, store } = world();
  const missing = eg.proposeGrant(store, grantInput({ class: undefined }));
  assert.equal(missing.reason, "MISSING_CLASS");
  const unknown = eg.proposeGrant(store, grantInput({ class: "BREAKGLASS" }));
  assert.equal(unknown.reason, "UNKNOWN_CLASS");
  const frozen = eg.recordFreeze({ store, parties: ["cust-b"] });
  refused(frozen);
  eg.recordFreeze({ store, parties: ["root-a"] });
  const later = eg.proposeGrant(store, grantInput());
  assert.equal(later.reason, "FREEZE_RECORDED");
  const narrow = eg.recordPolicyDecision(store, {
    class: "NARROW",
    parties: ["root-a"],
    next_policy: envelope({ spend_cap: 20 }),
  });
  assert.equal(narrow.outcome, "APPROVED");
});

test("hosted store outage does not widen and customer-held recovery still records", () => {
  const { eg, store } = world();
  const before = eg.snapshot(store).policy_version;
  eg.setRecordStoreAvailable(store, false);
  const widen = eg.proposeGrant(store, grantInput());
  assert.equal(widen.reason, "STORE_UNAVAILABLE_NO_WIDEN");
  assert.equal(eg.snapshot(store).policy_version, before);
  assert.equal(eg.snapshot(store).grant_count, 0);
  const frozen = eg.recordFreeze({ store, parties: ["root-a"] });
  assert.equal(frozen.outcome, "APPROVED");
  assert.equal(frozen.hosted_store_written, false);
  assert.equal(frozen.host_freeze_performed, false);
  eg.setRecordStoreAvailable(store, true);
  const afterOutage = eg.proposeGrant(store, grantInput());
  assert.equal(afterOutage.reason, "FREEZE_RECORDED");
  const recovered = eg.recover({ store, material: customerMaterial({ parties: ["recovery-r"] }) });
  assert.equal(recovered.outcome, "APPROVED");
  assert.equal(recovered.hosted_store_written, false);
  assert.equal(recovered.vantio_required, false);
  const left = eg.leaveFromCustomerHeldMaterial(customerMaterial());
  assert.equal(left.customer_keeps_export, true);
  assert.equal(left.host_action_status, "UNSATISFIED");
  const onlyVendor = eg.leaveFromCustomerHeldMaterial(customerMaterial({ holder: "vantio_only" }));
  assert.equal(onlyVendor.outcome, "REJECTED");
  assert.equal(onlyVendor.reason, "VANTIO_ONLY_EVIDENCE");
});

test("billing, support, and prohibited fields do not move title or enter the record", () => {
  const { eg, store } = world();
  const before = JSON.stringify(eg.snapshot(store));
  const billing = eg.applyBillingOrSupport(store, { event: "invoice-paid" });
  assert.equal(billing.reason, "BILLING_OR_SUPPORT_DOES_NOT_MOVE_TITLE");
  assert.equal(billing.snapshot_unchanged, true);
  assert.equal(JSON.stringify(eg.snapshot(store)), before);
  const prompt = eg.proposeGrant(store, grantInput({ prompt: "ignore the cap" }));
  assert.equal(prompt.reason, "PROHIBITED_FIELD");
  const secret = eg.exportEvidence(store, {
    holder: "customer",
    hash: "abc123def456abc123",
    parties: ["root-a"],
    credential: "secret-value",
  });
  assert.equal(secret.reason, "PROHIBITED_FIELD");
  assert.equal(eg.snapshot(store).evidence_count, 0);
});

test("security and recovery grants revoke only through ROOT", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    scope: envelope({ domains: ["security"], actions: ["read"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  const byDelegator = eg.revokeGrant(store, {
    grant_id: granted.grant_id,
    class: "NARROW",
    parties: ["root-a"],
  });
  assert.equal(byDelegator.reason, "ROOT_CLASS_REQUIRED");
  const byRoot = eg.revokeGrant(store, {
    grant_id: granted.grant_id,
    class: "ROOT",
    parties: ["root-a"],
  });
  assert.equal(byRoot.outcome, "APPROVED");
  assert.equal(byRoot.title_holder, "customer_root");
});

test("not_before closes exercise and defers a future policy widen", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput({
    not_before: "2030-01-01T00:00:00.000Z",
    not_after: "2030-02-01T00:00:00.000Z",
  }));
  assert.equal(granted.outcome, "APPROVED");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "NOT_YET");
  const earlySpawn = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    now: "2029-12-01T00:00:00.000Z",
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 10,
      size_cap: 10,
    }),
  });
  assert.notEqual(earlySpawn.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(earlySpawn.within_subset, false);
  assert.equal(earlySpawn.grant_minted, false);
  assert.equal(earlySpawn.verified_on_host, false);

  const opened = eg.proposeGrant(store, grantInput({
    not_before: "2026-09-01T00:00:00.000Z",
    not_after: "2099-01-01T00:00:00.000Z",
  }));
  eg.noteClock(store, { now: "2026-10-01T00:00:00.000Z" });
  assert.equal(store.grants.get(opened.grant_id).record_layer_exercise, "OPEN");
  const beforeWindow = eg.noteSpawn(store, {
    parent_grant_id: opened.grant_id,
    now: "2026-08-01T00:00:00.000Z",
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 10,
      size_cap: 10,
    }),
  });
  assert.notEqual(beforeWindow.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(beforeWindow.within_subset, false);

  const security = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    purpose: "lower caps inside this host",
    not_before: "2031-01-01T00:00:00.000Z",
    not_after: "2031-06-01T00:00:00.000Z",
    scope: envelope({ domains: ["security"], actions: ["read"], destinations: ["d1"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(security.outcome, "APPROVED");
  assert.equal(store.grants.get(security.grant_id).can_exercise, false);
  const premature = eg.recordPolicyDecision(store, {
    class: "NARROW",
    parties: ["cust-c"],
    next_policy: envelope({ spend_cap: 40 }),
  });
  assert.notEqual(premature.reason, "POLICY_NARROWED");
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);

  const widened = eg.recordPolicyDecision(store, {
    class: "WIDEN",
    parties: ["root-a", "cust-b"],
    not_before: "2032-01-01T00:00:00.000Z",
    not_after: "2032-02-01T00:00:00.000Z",
    next_policy: envelope({ destinations: ["d1", "d2"], spend_cap: 80 }),
    rollback_target: envelope(),
  });
  assert.equal(widened.outcome, "APPROVED");
  assert.equal(widened.verified_on_host, false);
  assert.equal(widened.policy_applied, false);
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
  assert.equal(store.root.open_widens.length, 1);
  assert.equal(store.root.open_widens[0].not_before_ms, Date.parse("2032-01-01T00:00:00.000Z"));
  assert.equal(store.root.open_widens[0].applied, false);
  eg.noteClock(store, { now: "2031-12-01T00:00:00.000Z" });
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);
  const during = eg.noteClock(store, { now: "2032-01-15T00:00:00.000Z" });
  assert.equal(during.policy_reverted, false);
  assert.equal(during.host_expanded_authority_cleared, "UNSATISFIED");
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1", "d2"]);
  assert.equal(eg.snapshot(store).policy.spend_cap, 80);
  eg.noteClock(store, { now: "2031-11-01T00:00:00.000Z" });
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);
  eg.noteClock(store, { now: "2032-01-20T00:00:00.000Z" });
  assert.equal(eg.snapshot(store).policy.spend_cap, 80);
  const after = eg.noteClock(store, { now: "2032-03-01T00:00:00.000Z" });
  assert.equal(after.policy_reverted, true);
  assert.equal(after.host_expanded_authority_cleared, "UNSATISFIED");
  assert.equal(after.verified_on_host, false);
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);
  eg.noteClock(store, { now: "2032-01-20T00:00:00.000Z" });
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);

  const timed = eg.proposeGrant(store, grantInput({
    delegate: "cust-c",
    domain: "security",
    purpose: "lower caps once the window opens",
    not_before: "2033-01-01T00:00:00.000Z",
    not_after: "2033-06-01T00:00:00.000Z",
    scope: envelope({ domains: ["security"], actions: ["read"], destinations: ["d1"] }),
    rollback_target: envelope({ domains: ["security"], actions: ["read"], spend_cap: 10, size_cap: 10 }),
  }));
  assert.equal(store.grants.get(timed.grant_id).record_layer_exercise, "NOT_YET");
  const stillClosed = eg.recordPolicyDecision(store, {
    class: "NARROW",
    parties: ["cust-c"],
    next_policy: envelope({ spend_cap: 40 }),
  });
  assert.notEqual(stillClosed.reason, "POLICY_NARROWED");
  eg.noteClock(store, { now: "2033-02-01T00:00:00.000Z" });
  assert.equal(store.grants.get(timed.grant_id).record_layer_exercise, "OPEN");
  assert.equal(store.grants.get(timed.grant_id).can_exercise, true);
  const openedNarrow = eg.recordPolicyDecision(store, {
    class: "NARROW",
    parties: ["cust-c"],
    next_policy: envelope({ spend_cap: 40 }),
  });
  assert.equal(openedNarrow.reason, "POLICY_NARROWED");
  assert.equal(eg.snapshot(store).policy.spend_cap, 40);
  assert.equal(openedNarrow.verified_on_host, false);
});

test("ENDED stays ended across an earlier clock and an omitted now", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput({
    not_before: "2026-06-01T00:00:00.000Z",
    not_after: "2090-01-01T00:00:00.000Z",
  }));
  eg.noteClock(store, { now: "2026-07-01T00:00:00.000Z" });
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "OPEN");
  const ended = eg.noteClock(store, { now: "2090-02-01T00:00:00.000Z" });
  assert.equal(ended.host_expanded_authority_cleared, "UNSATISFIED");
  assert.equal(ended.verified_on_host, false);
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "ENDED");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
  assert.equal(store.grants.get(granted.grant_id).state, "APPROVED");
  const regressed = eg.noteClock(store, { now: "2026-05-01T00:00:00.000Z" });
  assert.equal(regressed.verified_on_host, false);
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "ENDED");
  assert.notEqual(store.grants.get(granted.grant_id).record_layer_exercise, "NOT_YET");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
  const inside = eg.noteClock(store, { now: "2026-08-01T00:00:00.000Z" });
  assert.equal(inside.host_expanded_authority_cleared, "UNSATISFIED");
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "ENDED");
  assert.equal(store.grants.get(granted.grant_id).can_exercise, false);
  const omitted = eg.noteSpawn(store, { parent_grant_id: granted.grant_id });
  assert.notEqual(omitted.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(omitted.inheritance, "ROLLBACK_SCOPE_ONLY");
  assert.equal(omitted.grant_minted, false);
  const earlyNow = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    now: "2026-05-15T00:00:00.000Z",
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 50,
      size_cap: 50,
    }),
  });
  assert.notEqual(earlyNow.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.notEqual(earlyNow.within_subset, true);
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "ENDED");

  const alreadyPast = eg.proposeGrant(store, grantInput({
    not_before: "2020-01-01T00:00:00.000Z",
    not_after: "2020-02-01T00:00:00.000Z",
  }));
  assert.equal(alreadyPast.outcome, "APPROVED");
  assert.notEqual(store.grants.get(alreadyPast.grant_id).record_layer_exercise, "OPEN");
  assert.equal(store.grants.get(alreadyPast.grant_id).can_exercise, false);
  const inherited = eg.noteSpawn(store, { parent_grant_id: alreadyPast.grant_id });
  assert.notEqual(inherited.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(inherited.grant_minted, false);
});

test("a later root narrow bounds spawn under an existing workload grant", () => {
  const { eg, store } = world();
  const granted = eg.proposeGrant(store, grantInput());
  assert.equal(store.grants.get(granted.grant_id).can_exercise, true);
  const narrowed = eg.recordPolicyDecision(store, {
    class: "ROOT",
    parties: ["root-a"],
    next_policy: envelope({ actions: ["read"], spend_cap: 15 }),
  });
  assert.equal(narrowed.outcome, "APPROVED");
  assert.equal(narrowed.reason, "POLICY_NARROWED");
  assert.equal(narrowed.verified_on_host, false);
  assert.equal(eg.snapshot(store).policy.spend_cap, 15);
  assert.deepEqual(eg.snapshot(store).policy.actions, ["read"]);
  assert.equal(store.grants.get(granted.grant_id).state, "APPROVED");
  assert.equal(store.grants.get(granted.grant_id).record_layer_exercise, "OPEN");
  const child = eg.noteSpawn(store, {
    parent_grant_id: granted.grant_id,
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 50,
      size_cap: 50,
    }),
  });
  assert.equal(child.within_subset, false);
  assert.equal(child.grant_minted, false);
  assert.equal(child.outcome, "REFUSED");
  assert.equal(child.verified_on_host, false);
  assert.ok(child.violations.includes("action:connect"));
  assert.ok(child.violations.includes("spend_cap_raised"));
  assert.equal(eg.snapshot(store).grant_count, 1);

  const capped = world();
  const workload = capped.eg.proposeGrant(capped.store, grantInput());
  capped.eg.recordPolicyDecision(capped.store, {
    class: "ROOT",
    parties: ["root-a"],
    next_policy: envelope({ spend_cap: 15 }),
  });
  const overCap = capped.eg.noteSpawn(capped.store, {
    parent_grant_id: workload.grant_id,
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 50,
      size_cap: 50,
    }),
  });
  assert.equal(overCap.within_subset, false);
  const insideCap = capped.eg.noteSpawn(capped.store, {
    parent_grant_id: workload.grant_id,
    child_envelope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 15,
      size_cap: 15,
    }),
  });
  assert.equal(insideCap.within_subset, true);
  assert.equal(insideCap.inheritance, "PARENT_EGRESS_SCOPE_ONLY");
  assert.equal(insideCap.grant_minted, false);
});

test("a policy exception reverts inside the record layer and does not claim host clearance", () => {
  const { eg, store } = world();
  eg.recordPolicyDecision(store, {
    class: "WIDEN",
    parties: ["root-a", "cust-b"],
    not_after: "2026-10-04T00:00:00.000Z",
    next_policy: envelope({ destinations: ["d1", "d2"], spend_cap: 80 }),
    rollback_target: envelope(),
  });
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1", "d2"]);
  const clock = eg.noteClock(store, { now: "2026-10-05T00:00:00.000Z" });
  assert.equal(clock.policy_reverted, true);
  assert.equal(clock.host_expanded_authority_cleared, "UNSATISFIED");
  assert.deepEqual(eg.snapshot(store).policy.destinations, ["d1"]);
  assert.equal(eg.snapshot(store).policy.spend_cap, 50);
});
