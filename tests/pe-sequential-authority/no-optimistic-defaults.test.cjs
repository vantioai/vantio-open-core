"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { api, evaluate, root, step } = require("./fixture.cjs");

test("incomplete input is rejected and does not throw", () => {
  assert.equal(api.evaluate(null).rule, "INPUT_REJECTED");
  assert.equal(api.evaluate(null).reason, "evaluate_not_object");
  assert.equal(api.evaluate({ envelope: root() }).reason, "evaluate_missing_catalog");
  const broken = root();
  delete broken.max_steps;
  assert.equal(evaluate(broken).reason, "envelope_missing_max_steps");
  const open = root({ redelegation: "allowed" });
  assert.equal(evaluate(open).reason, "redelegation_not_forbidden");
  const ceilings = root().ceilings;
  delete ceilings.fleet;
  assert.equal(evaluate(root({ ceilings })).reason, "ceilings_missing_fleet");
});

test("empty allow-lists do not mean every scope is allowed", () => {
  const envelope = root({
    actions: [],
    destinations: [],
    credentials: [],
    bound_uses: [],
    node_ids: [],
    workload_ids: ["workload-a"],
  });
  assert.equal(evaluate(envelope, { action: "send", destination: "dest-a" }).reason, "action_not_granted");
  const withSend = root({
    destinations: [],
    credentials: [],
    bound_uses: [],
    actions: ["send"],
  });
  assert.equal(evaluate(withSend, { action: "send", destination: "dest-a" }).reason, "destination_not_in_envelope");
});

test("unknown authority fields are rejected", () => {
  const envelope = root();
  envelope.host_attachment = true;
  assert.equal(evaluate(envelope).reason, "envelope_unknown_key");
  const decision = api.evaluate({
    envelope: root(),
    catalog: { "env-root": root() },
    ledger: api.emptyLedger(),
    step: { ...step(), doctrine_present: true },
    now: 10,
  });
  assert.equal(decision.reason, "step_unknown_key");
});

test("a denied step does not consume budget and does not mutate the caller ledger", () => {
  const ledger = api.emptyLedger();
  const before = JSON.stringify(ledger);
  const decision = evaluate(root({ ceilings: root().ceilings }), { resource_units: 1000 }, ledger);
  assert.equal(decision.disposition, "DENY");
  assert.equal(JSON.stringify(ledger), before);
  assert.equal(Object.keys(decision.ledger.consumption).length, 0);
});

test("reserved rights cannot be smuggled through the ordinary action list", () => {
  const decision = evaluate(root({ actions: ["observe", "freeze"] }));
  assert.equal(decision.reason, "reserved_listed_as_ordinary_action");
});
