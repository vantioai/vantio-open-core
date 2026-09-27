"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { api, catalogOf, ceilings, evaluate, grantRequest, root } = require("./fixture.cjs");

test("one step over a cumulative ceiling is denied and splits do not reset it", () => {
  const envelope = root({ ceilings: ceilings({ resource_budget: 5 }) });
  const whole = evaluate(envelope, { resource_units: 6, action: "send", destination: "dest-a" });
  assert.equal(whole.disposition, "DENY");
  assert.equal(whole.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE");
  assert.equal(whole.axis, "resource_budget");

  const first = evaluate(envelope, { resource_units: 3, step_id: "step-1", run_id: "run-1", sequence_id: "seq-1", process_id: "proc-1" });
  const second = evaluate(
    envelope,
    { resource_units: 3, step_id: "step-2", run_id: "run-2", sequence_id: "seq-2", process_id: "proc-2" },
    first.ledger,
  );
  assert.equal(first.disposition, "ALLOW");
  assert.equal(second.disposition, "DENY");
  assert.equal(second.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE");
  assert.equal(second.axis, "resource_budget");
  assert.deepEqual(second.ledger.consumption, first.ledger.consumption);
});

test("a later time window for the same principal does not reset the resource budget", () => {
  const early = root({ ceilings: ceilings({ resource_budget: 5 }), not_before: 0, not_after: 100 });
  const late = root({
    envelope_id: "env-late",
    ceilings: ceilings({ resource_budget: 5 }),
    not_before: 200,
    not_after: 300,
  });
  const first = evaluate(early, { resource_units: 3 }, undefined, undefined, 10);
  const second = evaluate(late, { resource_units: 3, step_id: "step-2" }, first.ledger, catalogOf(late), 250);
  assert.equal(first.disposition, "ALLOW");
  assert.equal(second.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE");
  assert.equal(second.axis, "resource_budget");
});

test("agent consensus is not an authorization source and does not multiply budget", () => {
  const granted = evaluate(root(), {
    authority_source: "consensus",
    consensus: { agents: ["agent-a", "agent-b", "agent-c"] },
  });
  assert.equal(granted.invariant, "CONSENSUS_IS_NOT_AUTHORIZATION");
  assert.equal(granted.reason, "consensus_is_not_a_source");
  assert.equal(granted.consensus_ignored, false);

  const unauthorized = evaluate(root(), {
    action: "activate",
    consensus: { agents: ["agent-a", "agent-b"] },
  });
  assert.equal(unauthorized.invariant, "CONSENSUS_IS_NOT_AUTHORIZATION");
  assert.equal(unauthorized.reason, "consensus_does_not_grant_action");

  const ignored = evaluate(root(), {
    consensus: { agents: ["agent-a", "agent-b", "agent-c", "agent-d"] },
    resource_units: 1,
  });
  assert.equal(ignored.disposition, "ALLOW");
  assert.equal(ignored.consensus_ignored, true);
  for (const value of Object.values(ignored.ledger.consumption)) assert.equal(value, 1);

  const vote = api.proposeDelegation(root(), grantRequest({ cause: "consensus" }));
  assert.equal(vote.invariant, "CONSENSUS_IS_NOT_AUTHORIZATION");
  assert.equal(vote.reason, "consensus_is_not_a_grant");
});

test("another process does not mint a principal or a fresh budget", () => {
  const envelope = root({ ceilings: ceilings({ resource_budget: 3 }) });
  const first = evaluate(envelope, { resource_units: 2, process_id: "proc-1" });
  const second = evaluate(envelope, { resource_units: 2, process_id: "proc-2", step_id: "step-2" }, first.ledger);
  assert.equal(first.disposition, "ALLOW");
  assert.equal(first.principal_id, "principal-a");
  assert.equal(second.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE");
  assert.equal(second.principal_id, "principal-a");

  const minted = evaluate(root(), { distinct_principal_per_process: true });
  assert.equal(minted.invariant, "PROCESS_COUNT_IS_NOT_PRINCIPAL");
  assert.equal(minted.reason, "process_does_not_mint_a_principal");

  const renamed = evaluate(root(), { principal_id: "principal-b" });
  assert.equal(renamed.invariant, "PROCESS_COUNT_IS_NOT_PRINCIPAL");

  const counted = evaluate(root(), { authority_source: "process_count" });
  assert.equal(counted.reason, "process_count_is_not_a_source");

  const spawned = api.proposeDelegation(root(), grantRequest({ cause: "process_spawn" }));
  assert.equal(spawned.invariant, "PROCESS_COUNT_IS_NOT_PRINCIPAL");
  assert.equal(spawned.reason, "process_spawn_is_not_a_grant");
  assert.equal(spawned.envelope, null);
});

test("a child envelope cannot exceed the parent and cannot add a binding", () => {
  const parent = root();
  const destination = api.proposeDelegation(parent, grantRequest({ destinations: ["dest-a", "dest-c"] }));
  assert.equal(destination.invariant, "CHILD_CANNOT_EXCEED_INHERITANCE");
  assert.equal(destination.reason, "destination_outside_parent");

  const ceiling = api.proposeDelegation(parent, grantRequest({ ceilings: ceilings({ lineage: 1000 }) }));
  assert.equal(ceiling.invariant, "CHILD_CANNOT_EXCEED_INHERITANCE");
  assert.equal(ceiling.reason, "ceiling_above_parent");
  assert.equal(ceiling.axis, "lineage");

  const window = api.proposeDelegation(parent, grantRequest({ not_after: 5000 }));
  assert.equal(window.reason, "window_outside_parent");
  assert.equal(window.axis, "time_window");

  const binding = api.proposeDelegation(
    parent,
    grantRequest({
      destinations: ["dest-a", "dest-b"],
      bound_uses: [
        { credential_id: "cred-a", destination: "dest-a" },
        { credential_id: "cred-a", destination: "dest-b" },
      ],
    }),
  );
  assert.equal(binding.reason, "binding_outside_parent");

  const allowed = api.proposeDelegation(parent, grantRequest());
  assert.equal(allowed.disposition, "ALLOW");
  assert.equal(allowed.envelope.parent_envelope_id, "env-root");
  assert.deepEqual(allowed.envelope.lineage, ["env-root"]);
  assert.equal(allowed.envelope.issued_against_parent_generation, 0);
  assert.deepEqual(allowed.envelope.reserved_rights_held, []);
  assert.equal(allowed.host_attachment, false);
});

test("delegation cannot create reserved rights or reserved domains", () => {
  const freeze = api.proposeDelegation(root(), grantRequest({ actions: ["observe", "freeze"] }));
  assert.equal(freeze.invariant, "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS");
  assert.equal(freeze.reason, "delegation_cannot_create_reserved_right");

  const domain = api.proposeDelegation(root(), grantRequest({ domains: ["workload", "security"] }));
  assert.equal(domain.reason, "delegation_cannot_create_reserved_domain");

  const recovery = api.proposeDelegation(root(), grantRequest({ domains: ["recovery"] }));
  assert.equal(recovery.invariant, "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS");

  const child = root({
    envelope_id: "env-child",
    parent_envelope_id: "env-root",
    lineage: ["env-root"],
    principal_id: "principal-b",
    issued_against_parent_generation: 0,
    reserved_rights_held: [],
    actions: ["observe"],
  });
  const exercised = evaluate(
    child,
    { action: "freeze", resource_units: 0 },
    undefined,
    catalogOf(root(), child),
  );
  assert.equal(exercised.invariant, "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS");
  assert.equal(exercised.reason, "reserved_right_not_held");

  const rootFreeze = evaluate(root(), { action: "freeze", resource_units: 0 });
  assert.equal(rootFreeze.disposition, "ALLOW");
  assert.equal(rootFreeze.doctrine_present, false);
});

test("a delegate cannot redelegate", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest());
  const again = api.proposeDelegation(
    grant.envelope,
    grantRequest({ envelope_id: "env-grand", principal_id: "principal-c" }),
  );
  assert.equal(again.rule, "REDELEGATION_FORBIDDEN");
  assert.equal(again.reason, "redelegation_forbidden");

  const grand = {
    ...grant.envelope,
    envelope_id: "env-grand",
    principal_id: "principal-c",
    parent_envelope_id: grant.envelope.envelope_id,
    lineage: ["env-root", grant.envelope.envelope_id],
    issued_against_parent_generation: grant.envelope.generation,
  };
  const evaluated = evaluate(grand, undefined, undefined, catalogOf(parent, grant.envelope, grand));
  assert.equal(evaluated.rule, "REDELEGATION_FORBIDDEN");
});

test("revocation reaches descendants and a stale descendant does not survive", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest({ actions: ["observe", "send", "revoke_grant"] }));
  const catalog = catalogOf(parent, grant.envelope);
  const revoked = api.revoke(catalog, api.emptyLedger(), parent.envelope_id, 10);
  assert.equal(revoked.disposition, "ALLOW");
  assert.equal(revoked.revoked_ids.includes("env-root"), true);
  assert.equal(revoked.revoked_ids.includes("env-child"), true);
  assert.equal(catalog[parent.envelope_id].state, "ACTIVE");
  assert.equal(grant.envelope.state, "ACTIVE");

  const updated = evaluate(
    revoked.catalog["env-child"],
    undefined,
    revoked.ledger,
    revoked.catalog,
  );
  assert.equal(updated.invariant, "REVOCATION_REACHES_DESCENDANTS");
  assert.equal(updated.reason, "ancestor_revoked");

  const stale = evaluate(grant.envelope, undefined, revoked.ledger, revoked.catalog);
  assert.equal(stale.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(stale.reason, "stale_descendant_after_ancestor_revocation");
  assert.equal(stale.ledger.consumption["lineage\0env-root"], undefined);

  const childOnly = api.revoke(catalog, api.emptyLedger(), "env-child", 10);
  const rootStill = evaluate(
    childOnly.catalog["env-root"],
    { action: "freeze", resource_units: 0 },
    childOnly.ledger,
    childOnly.catalog,
  );
  assert.equal(rootStill.disposition, "ALLOW");

  const upward = evaluate(
    grant.envelope,
    { action: "revoke_grant", revoke_target: "env-root", resource_units: 0 },
    undefined,
    catalog,
  );
  assert.equal(upward.invariant, "CHILD_CANNOT_EXCEED_INHERITANCE");
  assert.equal(upward.reason, "cannot_revoke_ancestor");

  const selfStale = evaluate(grant.envelope, undefined, childOnly.ledger, childOnly.catalog);
  assert.equal(selfStale.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(selfStale.reason, "stale_self_after_revocation");

  const driftedParent = { ...parent, generation: 4 };
  const drifted = evaluate(grant.envelope, undefined, undefined, catalogOf(driftedParent, grant.envelope));
  assert.equal(drifted.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(drifted.reason, "parent_generation_drift");
});

test("a receipt for one action does not authorize a different action", () => {
  const envelope = root();
  const issued = evaluate(envelope, {
    action: "send",
    destination: "dest-a",
    receipt_id: "rcpt-1",
  });
  assert.equal(issued.disposition, "ALLOW");
  assert.equal(issued.receipt.action, "send");

  const crossed = evaluate(
    envelope,
    { action: "observe", presented_receipt_id: "rcpt-1", step_id: "step-2" },
    issued.ledger,
  );
  assert.equal(crossed.invariant, "NO_REPLAY_ACROSS_ACTIONS");
  assert.equal(crossed.reason, "cross_action");

  const retargeted = evaluate(
    envelope,
    {
      action: "send",
      destination: "dest-b",
      presented_receipt_id: "rcpt-1",
      step_id: "step-3",
    },
    issued.ledger,
  );
  assert.equal(retargeted.invariant, "NO_REPLAY_ACROSS_ACTIONS");
  assert.equal(retargeted.reason, "cross_action_tuple");

  const bearer = evaluate(
    envelope,
    { action: "send", destination: "dest-a", presented_receipt_id: "rcpt-1", step_id: "step-4" },
    issued.ledger,
  );
  assert.equal(bearer.reason, "receipt_is_not_a_bearer_token");

  const missing = evaluate(envelope, { presented_receipt_id: "rcpt-missing" });
  assert.equal(missing.reason, "unknown_receipt");
});

test("sequentially allowed actions do not compose into an ungranted authority", () => {
  const envelope = root({
    actions: ["observe", "label_enforced", "propose", "record_approval", "exercise", "name_delegate", "narrow", "send", "hold_credential"],
  });
  const observed = evaluate(envelope, { action: "observe" });
  const labeled = evaluate(
    envelope,
    { action: "label_enforced", sequence_id: "seq-2", step_id: "step-2" },
    observed.ledger,
  );
  assert.equal(observed.disposition, "ALLOW");
  assert.equal(labeled.invariant, "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY");
  assert.equal(labeled.reason, "observe_then_label_enforced");

  const proposed = evaluate(envelope, { action: "propose", sequence_id: "seq-3" });
  const recorded = evaluate(
    envelope,
    { action: "record_approval", sequence_id: "seq-4", step_id: "step-4" },
    proposed.ledger,
  );
  assert.equal(recorded.reason, "propose_then_record_approval");

  const exercised = evaluate(envelope, { action: "exercise", sequence_id: "seq-5" });
  const named = evaluate(
    envelope,
    { action: "name_delegate", sequence_id: "seq-6", step_id: "step-6" },
    exercised.ledger,
  );
  assert.equal(named.reason, "exercise_then_name_delegate");

  const raised = evaluate(envelope, { action: "narrow", raises_ceiling: true });
  assert.equal(raised.reason, "raise_composes_widen");

  const secondEffect = evaluate(envelope, { action: "observe", composed_effect: "enforce" });
  assert.equal(secondEffect.reason, "one_step_does_not_compose_a_second_effect");

  const held = evaluate(envelope, { action: "hold_credential", credential_id: "cred-a", sequence_id: "seq-7" });
  const sent = evaluate(
    envelope,
    { action: "send", destination: "dest-b", sequence_id: "seq-8", step_id: "step-8" },
    held.ledger,
  );
  const paired = evaluate(
    envelope,
    {
      action: "send",
      destination: "dest-b",
      credential_id: "cred-a",
      sequence_id: "seq-9",
      step_id: "step-9",
    },
    sent.ledger,
  );
  assert.equal(held.disposition, "ALLOW");
  assert.equal(sent.disposition, "ALLOW");
  assert.equal(paired.reason, "unbound_credential_destination");
  assert.deepEqual(envelope.bound_uses, [{ credential_id: "cred-a", destination: "dest-a" }]);
});

test("parent and child share lineage consumption and composition history", () => {
  const parent = root({
    ceilings: ceilings({ lineage: 5 }),
    actions: ["observe", "label_enforced", "send", "narrow", "revoke_grant", "hold_credential"],
  });
  const grant = api.proposeDelegation(
    parent,
    grantRequest({
      ceilings: ceilings({ lineage: 5 }),
      actions: ["observe", "label_enforced"],
      destinations: [],
      credentials: [],
      bound_uses: [],
    }),
  );
  assert.equal(grant.disposition, "ALLOW");
  const spent = evaluate(parent, { resource_units: 4 }, undefined, catalogOf(parent));
  const childSpend = evaluate(
    grant.envelope,
    { resource_units: 2, step_id: "step-child" },
    spent.ledger,
    catalogOf(parent, grant.envelope),
  );
  assert.equal(spent.disposition, "ALLOW");
  assert.equal(childSpend.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE");
  assert.equal(childSpend.axis, "lineage");

  const observed = evaluate(parent, { action: "observe", resource_units: 0 }, undefined, catalogOf(parent));
  const labeled = evaluate(
    grant.envelope,
    { action: "label_enforced", resource_units: 0, sequence_id: "seq-child", step_id: "step-label" },
    observed.ledger,
    catalogOf(parent, grant.envelope),
  );
  assert.equal(labeled.reason, "observe_then_label_enforced");
});

test("explicit derived authority is still only the granted action", () => {
  const envelope = root({ actions: ["observe", "label_enforced", "enforce", "send"] });
  const observed = evaluate(envelope, { action: "observe", resource_units: 0 });
  const labeled = evaluate(
    envelope,
    { action: "label_enforced", resource_units: 0, step_id: "step-2" },
    observed.ledger,
  );
  assert.equal(labeled.disposition, "ALLOW");
  assert.equal(labeled.doctrine_present, false);
  assert.equal(labeled.host_attachment, false);
  assert.equal(labeled.enforcement, "EVALUATE_ONLY");
});
