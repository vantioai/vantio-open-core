"use strict";

const eg = require("../../internal/enterprise-governance/src/index.cjs");

function envelope(overrides) {
  return Object.assign({
    hosts: ["h1"],
    destinations: ["d1"],
    path_constraints: ["p1"],
    spend_cap: 50,
    size_cap: 50,
    actions: ["read", "connect"],
    domains: ["workload", "security", "recovery"],
  }, overrides || {});
}

function ceiling() {
  return envelope({
    destinations: ["d1", "d2"],
    spend_cap: 100,
    size_cap: 100,
  });
}

function world() {
  const store = eg.createCustomerHeldStore();
  eg.acceptOpaqueIdentity(store, { id: "root-a", kind: "customer" });
  eg.acceptOpaqueIdentity(store, { id: "cust-b", kind: "customer" });
  eg.acceptOpaqueIdentity(store, { id: "cust-c", kind: "customer" });
  eg.acceptOpaqueIdentity(store, { id: "work-w", kind: "workload" });
  eg.acceptOpaqueIdentity(store, { id: "vantio", kind: "vantio" });
  const founded = eg.foundRoot(store, {
    root_identity: "root-a",
    authority_ceiling: ceiling(),
    initial_policy: envelope(),
  });
  eg.recordRecognizedCustomer(store, { class: "ROOT", parties: ["root-a"], customer_id: "cust-b" });
  eg.recordRecognizedCustomer(store, { class: "ROOT", parties: ["root-a"], customer_id: "cust-c" });
  return { eg, store, founded };
}

function grantInput(extra) {
  return Object.assign({
    class: "WIDEN",
    delegator: "root-a",
    delegate: "work-w",
    domain: "workload",
    purpose: "connect from the named host",
    not_before: "2026-09-27T00:00:00.000Z",
    not_after: "2026-10-04T00:00:00.000Z",
    parties: ["root-a", "cust-b"],
    witness_ids: [],
    scope: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
    }),
    rollback_target: envelope({
      domains: ["workload"],
      actions: ["connect"],
      destinations: ["d1"],
      spend_cap: 10,
      size_cap: 10,
    }),
  }, extra || {});
}

function customerMaterial(extra) {
  return Object.assign({
    mode: "last-known",
    holder: "customer",
    hash: "abc123def456abc123",
    parties: ["root-a"],
    identities: [
      { id: "root-a", kind: "customer" },
      { id: "recovery-r", kind: "customer" },
      { id: "vantio", kind: "vantio" },
    ],
    material_root_ids: ["root-a"],
    material_recovery_ids: ["recovery-r"],
    pre_containment: envelope(),
    proposed_envelope: envelope({ spend_cap: 40 }),
    rollback_target: envelope({ spend_cap: 40 }),
  }, extra || {});
}

module.exports = {
  ceiling,
  customerMaterial,
  envelope,
  grantInput,
  world,
};
