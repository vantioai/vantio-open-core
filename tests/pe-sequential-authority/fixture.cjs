"use strict";

const api = require("../../packages/pe-sequential-authority/src/index.cjs");

function ceilings(overrides) {
  const values = {};
  for (const axis of api.LIMIT_AXES) values[axis] = 100;
  if (overrides) {
    for (const axis of Object.keys(overrides)) values[axis] = overrides[axis];
  }
  return values;
}

function root(overrides) {
  const envelope = {
    envelope_id: "env-root",
    principal_id: "principal-a",
    tenant_id: "tenant-a",
    workload_ids: ["workload-a"],
    fleet_id: "fleet-a",
    node_ids: ["node-a"],
    parent_envelope_id: null,
    lineage: [],
    generation: 0,
    issued_against_parent_generation: null,
    domains: ["workload"],
    actions: ["observe", "send", "narrow", "revoke_grant", "hold_credential"],
    destinations: ["dest-a", "dest-b"],
    credentials: ["cred-a"],
    bound_uses: [{ credential_id: "cred-a", destination: "dest-a" }],
    not_before: 0,
    not_after: 1000,
    redelegation: "forbidden",
    ceilings: ceilings(),
    max_steps: 20,
    state: "ACTIVE",
    reserved_rights_held: ["freeze", "recover", "export", "revoke_root"],
  };
  if (!overrides) return envelope;
  return { ...envelope, ...overrides };
}

function step(overrides) {
  const value = {
    step_id: "step-1",
    action: "observe",
    authority_source: "envelope",
    sequence_id: "seq-1",
    run_id: "run-1",
    process_id: "proc-1",
    workload_id: "workload-a",
    tenant_id: "tenant-a",
    node_id: "node-a",
    fleet_id: "fleet-a",
    resource_units: 1,
  };
  if (!overrides) return value;
  return { ...value, ...overrides };
}

function grantRequest(overrides) {
  const request = {
    envelope_id: "env-child",
    principal_id: "principal-b",
    cause: "grant",
    tenant_id: "tenant-a",
    workload_ids: ["workload-a"],
    fleet_id: "fleet-a",
    node_ids: ["node-a"],
    domains: ["workload"],
    actions: ["observe", "send"],
    destinations: ["dest-a"],
    credentials: ["cred-a"],
    bound_uses: [{ credential_id: "cred-a", destination: "dest-a" }],
    not_before: 0,
    not_after: 1000,
    ceilings: ceilings(),
    max_steps: 10,
  };
  if (!overrides) return request;
  return { ...request, ...overrides };
}

function catalogOf(...envelopes) {
  const catalog = {};
  for (const envelope of envelopes) catalog[envelope.envelope_id] = envelope;
  return catalog;
}

function evaluate(envelope, stepOverrides, ledger, catalog, now) {
  return api.evaluate({
    envelope,
    catalog: catalog || catalogOf(envelope),
    ledger: ledger || api.emptyLedger(),
    step: step(stepOverrides),
    now: now === undefined ? 10 : now,
  });
}

module.exports = {
  api,
  catalogOf,
  ceilings,
  evaluate,
  grantRequest,
  root,
  step,
};
