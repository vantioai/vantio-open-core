"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { api, catalogOf, evaluate, grantRequest, root } = require("./fixture.cjs");

test("a pre-revoke ACTIVE child object is denied when the catalog entry is REVOKED and the ledger is empty", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest({ actions: ["observe", "send", "revoke_grant"] }));
  assert.equal(grant.disposition, "ALLOW");
  assert.equal(grant.envelope.state, "ACTIVE");
  const catalog = catalogOf(parent, grant.envelope);
  const childOnly = api.revoke(catalog, api.emptyLedger(), "env-child", 10);
  assert.equal(childOnly.disposition, "ALLOW");
  assert.equal(childOnly.catalog["env-child"].state, "REVOKED");
  assert.equal(childOnly.catalog["env-root"].state, "ACTIVE");
  assert.equal(grant.envelope.state, "ACTIVE");
  assert.equal(catalog["env-child"].state, "ACTIVE");

  const stale = evaluate(grant.envelope, undefined, api.emptyLedger(), childOnly.catalog);
  assert.equal(stale.disposition, "DENY");
  assert.equal(stale.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(stale.reason, "stale_self_after_revocation");
  assert.equal(stale.axis, "lineage");
  assert.equal(stale.host_attachment, false);
  assert.equal(stale.enforcement, "EVALUATE_ONLY");
  assert.equal(stale.doctrine_present, false);
  assert.equal(stale.revoke_transition, null);
  assert.equal(Object.keys(stale.ledger.revocations).length, 0);
  assert.equal(Object.keys(stale.ledger.consumption).length, 0);
  assert.equal(grant.envelope.state, "ACTIVE");
  assert.equal(childOnly.catalog["env-child"].state, "REVOKED");
});

test("ancestor REVOKED in the catalog and a ledger mark still deny a stale ACTIVE descendant", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest());
  const catalog = catalogOf(parent, grant.envelope);
  const revoked = api.revoke(catalog, api.emptyLedger(), parent.envelope_id, 10);

  const catalogOnly = evaluate(grant.envelope, undefined, api.emptyLedger(), revoked.catalog);
  assert.equal(catalogOnly.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(catalogOnly.reason, "stale_descendant_after_ancestor_revocation");
  assert.equal(catalogOnly.host_attachment, false);
  assert.equal(catalogOnly.enforcement, "EVALUATE_ONLY");

  const markedParent = { ...parent, generation: 4, state: "REVOKED" };
  const driftedRevoked = evaluate(grant.envelope, undefined, api.emptyLedger(), catalogOf(markedParent, grant.envelope));
  assert.equal(driftedRevoked.disposition, "DENY");
  assert.equal(driftedRevoked.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(driftedRevoked.reason, "stale_descendant_after_ancestor_revocation");

  const ledgerOnly = evaluate(grant.envelope, undefined, revoked.ledger, catalogOf(parent, grant.envelope));
  assert.equal(ledgerOnly.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(ledgerOnly.reason, "stale_descendant_after_ancestor_revocation");
  assert.equal(Object.keys(ledgerOnly.ledger.consumption).length, 0);
});

test("parent generation drift denies when the catalog parent is EXPIRED or otherwise non-ACTIVE", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest());
  assert.equal(grant.envelope.issued_against_parent_generation, 0);
  assert.equal(grant.envelope.state, "ACTIVE");

  const expiredParent = { ...parent, state: "EXPIRED", generation: 4 };
  const expired = evaluate(grant.envelope, undefined, api.emptyLedger(), catalogOf(expiredParent, grant.envelope));
  assert.equal(expired.disposition, "DENY");
  assert.equal(expired.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
  assert.equal(expired.reason, "parent_generation_drift");
  assert.equal(expired.axis, "lineage");
  assert.equal(expired.host_attachment, false);
  assert.equal(expired.enforcement, "EVALUATE_ONLY");
  assert.equal(expired.doctrine_present, false);
  assert.equal(Object.keys(expired.ledger.consumption).length, 0);
  assert.equal(grant.envelope.state, "ACTIVE");

  const activeParent = { ...parent, state: "ACTIVE", generation: 4 };
  const active = evaluate(grant.envelope, undefined, api.emptyLedger(), catalogOf(activeParent, grant.envelope));
  assert.equal(active.reason, "parent_generation_drift");
  assert.equal(active.invariant, "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION");
});

test("evaluate of revoke_grant returns a transition and does not mark the catalog or ledger", () => {
  const parent = root();
  const grant = api.proposeDelegation(parent, grantRequest({ actions: ["observe", "revoke_grant"] }));
  const catalog = catalogOf(parent, grant.envelope);
  const ledger = api.emptyLedger();
  const decision = evaluate(
    parent,
    { action: "revoke_grant", revoke_target: "env-child", resource_units: 0 },
    ledger,
    catalog,
  );
  assert.equal(decision.disposition, "ALLOW");
  assert.equal(decision.revoke_transition, "env-child");
  assert.equal(decision.catalog, null);
  assert.equal(decision.invariant, null);
  assert.equal(catalog["env-child"].state, "ACTIVE");
  assert.equal(catalog["env-root"].state, "ACTIVE");
  assert.equal(Object.keys(decision.ledger.revocations).length, 0);
  assert.equal(Object.keys(ledger.revocations).length, 0);
  assert.equal(decision.host_attachment, false);
  assert.equal(decision.enforcement, "EVALUATE_ONLY");
  assert.equal(decision.doctrine_present, false);
});
