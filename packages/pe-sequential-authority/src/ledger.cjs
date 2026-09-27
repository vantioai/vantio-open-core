"use strict";

function lineageRoot(envelope) {
  if (envelope.lineage.length === 0) return envelope.envelope_id;
  return envelope.lineage[0];
}

function budgetKey(parts) {
  return parts.join("\0");
}

function compositionKey(envelope) {
  return budgetKey(["composition", lineageRoot(envelope)]);
}

function stepCountKey(envelope, step) {
  return budgetKey(["steps", envelope.principal_id, step.sequence_id]);
}

function scopeKeys(envelope, step) {
  const keys = [
    ["sequence", budgetKey(["sequence", envelope.principal_id, step.sequence_id])],
    ["run", budgetKey(["run", envelope.principal_id, step.run_id])],
    ["workload", budgetKey(["workload", step.tenant_id, step.workload_id])],
    ["lineage", budgetKey(["lineage", lineageRoot(envelope)])],
    ["tenant", budgetKey(["tenant", step.tenant_id])],
    ["node", budgetKey(["node", step.node_id])],
    ["fleet", budgetKey(["fleet", step.fleet_id])],
    [
      "time_window",
      budgetKey([
        "time_window",
        envelope.principal_id,
        String(envelope.not_before),
        String(envelope.not_after),
      ]),
    ],
    ["resource_budget", budgetKey(["resource_budget", envelope.principal_id])],
  ];
  if (step.credential_id !== null) {
    keys.push(["credential", budgetKey(["credential", step.credential_id])]);
  }
  if (step.destination !== null) {
    keys.push(["destination", budgetKey(["destination", step.destination])]);
  }
  return keys;
}

function copyLedger(ledger) {
  const consumption = Object.create(null);
  for (const key of Object.keys(ledger.consumption)) consumption[key] = ledger.consumption[key];
  const receipts = Object.create(null);
  for (const key of Object.keys(ledger.receipts)) receipts[key] = { ...ledger.receipts[key] };
  const revocations = Object.create(null);
  for (const key of Object.keys(ledger.revocations)) revocations[key] = { ...ledger.revocations[key] };
  const sequences = Object.create(null);
  for (const key of Object.keys(ledger.sequences)) {
    sequences[key] = ledger.sequences[key].map((effect) => ({ ...effect }));
  }
  const stepCounts = Object.create(null);
  for (const key of Object.keys(ledger.step_counts)) stepCounts[key] = ledger.step_counts[key];
  return { consumption, receipts, revocations, sequences, step_counts: stepCounts };
}

function consumed(ledger, key) {
  const value = ledger.consumption[key];
  return value === undefined ? 0 : value;
}

function effectiveCeiling(envelope, catalog, axis) {
  let cap = envelope.ceilings[axis];
  for (const id of envelope.lineage) {
    const ancestor = catalog[id];
    if (!ancestor) return null;
    if (ancestor.ceilings[axis] < cap) cap = ancestor.ceilings[axis];
  }
  return cap;
}

function cloneEnvelope(envelope) {
  return {
    envelope_id: envelope.envelope_id,
    principal_id: envelope.principal_id,
    tenant_id: envelope.tenant_id,
    workload_ids: envelope.workload_ids.slice(),
    fleet_id: envelope.fleet_id,
    node_ids: envelope.node_ids.slice(),
    parent_envelope_id: envelope.parent_envelope_id,
    lineage: envelope.lineage.slice(),
    generation: envelope.generation,
    issued_against_parent_generation: envelope.issued_against_parent_generation,
    domains: envelope.domains.slice(),
    actions: envelope.actions.slice(),
    destinations: envelope.destinations.slice(),
    credentials: envelope.credentials.slice(),
    bound_uses: envelope.bound_uses.map((pair) => ({
      credential_id: pair.credential_id,
      destination: pair.destination,
    })),
    not_before: envelope.not_before,
    not_after: envelope.not_after,
    redelegation: envelope.redelegation,
    ceilings: { ...envelope.ceilings },
    max_steps: envelope.max_steps,
    state: envelope.state,
    reserved_rights_held: envelope.reserved_rights_held.slice(),
  };
}

module.exports = {
  budgetKey,
  cloneEnvelope,
  compositionKey,
  consumed,
  copyLedger,
  effectiveCeiling,
  lineageRoot,
  scopeKeys,
  stepCountKey,
};
