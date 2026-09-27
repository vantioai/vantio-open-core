"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  EFFECT,
  HOST,
  PREDICATE,
  api,
  assertHeld,
  create,
  event,
  throughCanary,
} = require("./support.cjs");

function decide(engine, ev, extra = {}) {
  return api.decide(engine, { rule_id: "rule-host", ...ev, ...extra });
}

function quiet(result) {
  assertHeld(result);
  assert.notEqual(result.stage, "ENFORCE");
  assert.notEqual(result.decision_class, "PROMOTED_MATCH");
}

test("observations never become enforced policy, including an enforce flag", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  const discovered = api.discover(engine, {
    rule_id: "rule-host",
    actor: "ada",
    signal: { ...signal, enforce: true, prompt: "synthetic-prompt-value" },
  });
  assert.equal(discovered.stage, "DISCOVER");
  assert.equal(discovered.control_attempt.includes("enforce"), true);
  for (let index = 0; index < 64; index += 1) {
    const observed = api.observe(engine, {
      rule_id: "rule-host",
      actor: "ada",
      enforce: true,
      auto: true,
      stage: "ENFORCE",
      observation: { ...signal, at: index + 2, prompt: "synthetic-prompt-value", api_key: "sk-test-value" },
    });
    assert.equal(observed.ok, true);
    assert.equal(observed.stage, "OBSERVE");
    assert.equal(observed.proposal_created, false);
    assertHeld(observed);
  }
  assert.deepEqual(api.activeEnforcement(engine), []);
  const decision = decide(engine, event("agent-a", HOST, 12, 99), {
    enforce: true,
    stage: "ENFORCE",
    auto_promote: true,
  });
  assert.equal(decision.decision_class, "OBSERVATION");
  assert.equal(decision.lifecycle_stage, "OBSERVE");
  quiet(decision);
  const dumped = JSON.stringify(engine.evidence);
  assert.equal(dumped.includes("synthetic-prompt-value"), false);
  assert.equal(dumped.includes("sk-test-value"), false);
});

test("ingest may create a proposal and stops there", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  const proposed = api.ingest(engine, {
    rule_id: "rule-host",
    actor: "ada",
    signal,
    observations: [signal, event("agent-a", HOST, 20, 2)],
    propose: true,
    effect: EFFECT,
    predicate: PREDICATE,
    enforce: true,
    auto: true,
    stage: "ENFORCE",
    promote: true,
  });
  assert.equal(proposed.ok, true);
  assert.equal(proposed.stage, "PROPOSE");
  assert.equal(proposed.proposal_created, true);
  assert.equal(proposed.control_attempt.includes("enforce"), true);
  assertHeld(proposed);
  assert.deepEqual(api.activeEnforcement(engine), []);
  assert.equal(decide(engine, event("agent-a", HOST, 20, 3)).decision_class, "PROPOSAL");
});

test("ingest without propose stays on observe", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  const ingested = api.ingest(engine, {
    rule_id: "rule-host",
    actor: "ada",
    signal,
    observations: [signal],
    propose: "ENFORCE",
    enforce: true,
  });
  assert.equal(ingested.stage, "OBSERVE");
  assert.equal(ingested.proposal_created, false);
  assert.deepEqual(api.activeEnforcement(engine), []);
});

test("rejected actors and skipped stages cannot promote", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  assert.equal(api.discover(engine, { rule_id: "rule-host", actor: "auto", signal }).code, "AUTO_REJECTED");
  assert.equal(api.discover(engine, { rule_id: "rule-host", actor: "ada", signal }).stage, "DISCOVER");
  assert.equal(api.promote(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
  }).code, "WRONG_STAGE");
  assert.equal(api.simulate(engine, {
    rule_id: "rule-host",
    actor: "ada",
    corpus: [signal],
    auto: true,
  }).code, "AUTO_REJECTED");
  assert.equal(engine.rules.get("rule-host").stage, "DISCOVER");
});

test("a proposal requires an observation and a bounded predicate", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  api.discover(engine, { rule_id: "rule-host", actor: "ada", signal });
  api.observe(engine, { rule_id: "rule-host", actor: "ada", observation: signal });
  assert.equal(api.propose(engine, {
    rule_id: "rule-host",
    actor: "ada",
    effect: EFFECT,
    predicate: {},
    enforce: true,
  }).code, "AUTO_REJECTED");
  assert.equal(api.propose(engine, {
    rule_id: "rule-host",
    actor: "ada",
    effect: EFFECT,
    predicate: {},
  }).code, "WIDE_PREDICATE");
  assert.equal(engine.rules.get("rule-host").stage, "OBSERVE");
  const proposed = api.propose(engine, {
    rule_id: "rule-host",
    actor: "ada",
    effect: EFFECT,
    predicate: PREDICATE,
  });
  assert.equal(proposed.stage, "PROPOSE");
  assert.equal(api.canary(engine, {
    rule_id: "rule-host",
    actor: "ada",
    cohort: { cohort_id: "cohort-a", subject_refs: ["*"] },
    samples: [signal],
  }).code, "WRONG_STAGE");
});

test("canary refuses an unbounded cohort and does not arm enforcement", () => {
  const engine = create();
  throughCanary(engine);
  const second = create();
  const signal = event("agent-a", HOST, 12, 1);
  api.discover(second, { rule_id: "rule-host", actor: "ada", signal });
  api.observe(second, { rule_id: "rule-host", actor: "ada", observation: signal });
  api.propose(second, { rule_id: "rule-host", actor: "ada", effect: EFFECT, predicate: PREDICATE });
  api.simulate(second, { rule_id: "rule-host", actor: "ada", corpus: [signal, event("agent-b", "other.example.com", 4, 2)] });
  assert.equal(api.canary(second, {
    rule_id: "rule-host",
    actor: "ada",
    cohort: { cohort_id: "all", subject_refs: ["*"] },
    samples: [signal],
  }).code, "COHORT_UNBOUNDED");
  assert.equal(second.rules.get("rule-host").stage, "SIMULATE");
  assert.equal(decide(second, event("agent-a", HOST, 12, 3)).decision_class, "SHADOW");
  assert.deepEqual(api.activeEnforcement(second), []);
});

test("extra observations after promotion do not widen rollout", () => {
  const engine = create();
  throughCanary(engine);
  const promoted = api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  for (let index = 0; index < 30; index += 1) {
    const observed = api.observe(engine, {
      rule_id: "rule-host",
      actor: "ada",
      observation: event("agent-c", HOST, 10, 100 + index),
      from_observations: true,
    });
    assert.equal(observed.stage, "ENFORCE");
    assert.equal(observed.rollout_step, "COHORT");
  }
  assert.equal(api.advanceRollout(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    to_step: "LIMITED",
    prior_evidence_id: promoted.evidence_id,
    limited_subject_refs: ["agent-a", "agent-b"],
    from_observations: true,
  }).code, "AUTO_REJECTED");
  assert.equal(engine.rules.get("rule-host").rollout.step, "COHORT");
  assert.equal(decide(engine, event("agent-c", HOST, 10, 200)).decision_class, "SHADOW");
});

test("simulation refuses a corpus that carries a prompt and stores nothing from it", () => {
  const engine = create();
  const signal = event("agent-a", HOST, 12, 1);
  api.discover(engine, { rule_id: "rule-host", actor: "ada", signal });
  api.observe(engine, { rule_id: "rule-host", actor: "ada", observation: signal });
  api.propose(engine, { rule_id: "rule-host", actor: "ada", effect: EFFECT, predicate: PREDICATE });
  const refused = api.simulate(engine, {
    rule_id: "rule-host",
    actor: "ada",
    corpus: [{ ...signal, prompt: "synthetic-prompt-value" }],
  });
  assert.equal(refused.code, "BAD_CORPUS");
  assert.equal(engine.rules.get("rule-host").stage, "PROPOSE");
  assert.equal(JSON.stringify(engine).includes("synthetic-prompt-value"), false);
});

test("the same person cannot review their own promotion", () => {
  const engine = create();
  throughCanary(engine);
  api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  assert.equal(api.review(engine, { rule_id: "rule-host", actor: "bo", verdict: "PASS" }).code, "SAME_ACTOR");
  assert.equal(api.review(engine, { rule_id: "rule-host", actor: "cy", verdict: "PASS" }).code, "SAME_ACTOR");
  assert.equal(engine.rules.get("rule-host").stage, "ENFORCE");
});
