"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { api, ceilings, evaluate, root } = require("./fixture.cjs");

function deniesAggregate(axis, stepOverrides) {
  const envelope = root({ ceilings: ceilings({ [axis]: 3 }) });
  const first = evaluate(envelope, { resource_units: 2, step_id: "step-1", ...stepOverrides });
  const second = evaluate(
    envelope,
    { resource_units: 2, step_id: "step-2", ...stepOverrides },
    first.ledger,
  );
  assert.equal(first.disposition, "ALLOW", axis);
  assert.equal(second.disposition, "DENY", axis);
  assert.equal(second.invariant, "SPLIT_CANNOT_BYPASS_AGGREGATE", axis);
  assert.equal(second.axis, axis);
}

test("every limit axis is enforced", () => {
  assert.deepEqual(api.LIMIT_AXES, [
    "action",
    "sequence",
    "run",
    "workload",
    "lineage",
    "credential",
    "destination",
    "tenant",
    "node",
    "fleet",
    "time_window",
    "resource_budget",
  ]);
});

test("action ceiling is a per-step limit", () => {
  const decision = evaluate(root({ ceilings: ceilings({ action: 5 }) }), { resource_units: 6 });
  assert.equal(decision.rule, "LIMIT");
  assert.equal(decision.axis, "action");
  assert.equal(decision.reason, "action_ceiling");
  assert.equal(decision.invariant, null);
});

test("an ungranted action stays denied when no consensus is offered", () => {
  const decision = evaluate(root({ actions: [] }), { action: "observe" });
  assert.equal(decision.rule, "LIMIT");
  assert.equal(decision.reason, "action_not_granted");
});

test("sequence, run, workload, credential, destination, tenant, node, and fleet ceilings accumulate", () => {
  deniesAggregate("sequence");
  deniesAggregate("run");
  deniesAggregate("workload");
  deniesAggregate("credential", { credential_id: "cred-a" });
  deniesAggregate("destination", { action: "send", destination: "dest-a" });
  deniesAggregate("tenant");
  deniesAggregate("node");
  deniesAggregate("fleet");
  deniesAggregate("time_window");
  deniesAggregate("resource_budget");
});

test("lineage ceiling is shared by the root aggregate", () => {
  deniesAggregate("lineage");
});

test("membership limits deny a scope outside the envelope", () => {
  const envelope = root({ destinations: [], credentials: [], bound_uses: [], node_ids: ["node-a"] });
  assert.equal(evaluate(envelope, { tenant_id: "tenant-b" }).reason, "tenant_not_in_envelope");
  assert.equal(evaluate(envelope, { fleet_id: "fleet-b" }).reason, "fleet_not_in_envelope");
  assert.equal(evaluate(envelope, { workload_id: "workload-b" }).reason, "workload_not_in_envelope");
  assert.equal(evaluate(envelope, { node_id: "node-b" }).reason, "node_not_in_envelope");
  assert.equal(evaluate(envelope, { destination: "dest-a", action: "send" }).reason, "destination_not_in_envelope");
  assert.equal(evaluate(envelope, { credential_id: "cred-a" }).reason, "credential_not_in_envelope");
});

test("time window bounds are closed at not_after and open at not_before", () => {
  const envelope = root({ not_before: 10, not_after: 20 });
  assert.equal(evaluate(envelope, undefined, undefined, undefined, 9).reason, "not_yet_valid");
  assert.equal(evaluate(envelope, undefined, undefined, undefined, 20).reason, "outside_window");
  assert.equal(evaluate(envelope, undefined, undefined, undefined, 10).disposition, "ALLOW");
  assert.equal(evaluate(envelope, undefined, undefined, undefined, 19).disposition, "ALLOW");
});

test("sequence length has a step ceiling that budget-free steps still consume", () => {
  const envelope = root({ max_steps: 2 });
  const first = evaluate(envelope, { resource_units: 0, step_id: "step-1" });
  const second = evaluate(envelope, { resource_units: 0, step_id: "step-2" }, first.ledger);
  const third = evaluate(envelope, { resource_units: 0, step_id: "step-3" }, second.ledger);
  assert.equal(first.disposition, "ALLOW");
  assert.equal(second.disposition, "ALLOW");
  assert.equal(third.rule, "LIMIT");
  assert.equal(third.reason, "sequence_step_ceiling");
  assert.equal(third.axis, "sequence");
});
