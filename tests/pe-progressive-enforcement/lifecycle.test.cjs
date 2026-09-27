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
  loadHistory,
  mutable,
  throughCanary,
} = require("./support.cjs");

function decide(engine, ev, ruleId = "rule-host") {
  return api.decide(engine, { rule_id: ruleId, ...ev });
}

test("the lifecycle lists every required stage in order", () => {
  assert.deepEqual(api.STAGES, [
    "DISCOVER",
    "OBSERVE",
    "PROPOSE",
    "SIMULATE",
    "CANARY",
    "ENFORCE",
    "REVIEW",
    "REVOKE_OR_ROLLBACK",
    "RETIRE",
    "VERIFY_REMOVAL",
  ]);
  assert.equal(api.PRODUCER_CLASSIFICATION, "PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL");
  assert.equal(api.POSTURE.council_verdict, null);
  assert.equal(api.POSTURE.self_certified_council_pass, false);
  assert.equal(api.POSTURE.auto_enforce_from_observation, false);
  assert.equal(api.POSTURE.host_attachment, "NOT_PERFORMED");
});

test("a rule can occupy each stage and ends removed", () => {
  const engine = create();
  const walked = throughCanary(engine);
  assert.equal(walked.simulation.impact.matched, 3);
  assert.equal(walked.simulation.impact.unmatched, 1);
  assert.equal(walked.simulation.impact.distinct_subjects, 3);
  assert.equal(walked.simulation.impact.byte_count_sum, 360);
  assert.equal(walked.simulation.shadow_decision_count, 4);
  assert.equal(walked.simulation.impact.label, "SHADOW");
  for (const shadow of api.listEvidence(engine, "SIMULATION")[0].body.decisions) {
    assert.equal(shadow.label, "SHADOW");
    assert.equal(shadow.applied_to_host, false);
    assert.equal(shadow.enforcement_attached, false);
  }

  const promoted = api.promote(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    rollout_request: "COHORT",
  });
  assert.equal(promoted.ok, true);
  assert.equal(promoted.stage, "ENFORCE");
  assert.equal(promoted.rollout_step, "COHORT");
  assertHeld(promoted);
  assert.deepEqual(api.activeEnforcement(engine), ["rule-host"]);

  const inside = decide(engine, event("agent-a", HOST, 90, 20));
  const outside = decide(engine, event("agent-b", HOST, 90, 21));
  assert.equal(inside.decision_class, "PROMOTED_MATCH");
  assert.equal(inside.applied_to_host, false);
  assert.equal(inside.enforcement_attached, false);
  assert.equal(outside.decision_class, "SHADOW");
  assertHeld(inside);

  const limited = api.advanceRollout(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    to_step: "LIMITED",
    prior_evidence_id: promoted.evidence_id,
    limited_subject_refs: ["agent-a", "agent-b"],
  });
  assert.equal(limited.ok, true);
  assert.equal(limited.stage, "ENFORCE");
  assert.equal(limited.rollout_step, "LIMITED");
  assert.equal(decide(engine, event("agent-b", HOST, 90, 22)).decision_class, "PROMOTED_MATCH");
  assert.equal(decide(engine, event("agent-c", HOST, 90, 23)).decision_class, "SHADOW");

  const skip = api.advanceRollout(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    to_step: "BROADER",
    prior_evidence_id: promoted.evidence_id,
    broader_subject_refs: ["agent-a", "agent-b", "agent-c"],
  });
  assert.equal(skip.code, "MISSING_EVIDENCE");

  const broader = api.advanceRollout(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    to_step: "BROADER",
    prior_evidence_id: limited.evidence_id,
    broader_subject_refs: ["agent-a", "agent-b", "agent-c"],
  });
  assert.equal(broader.ok, true);
  assert.equal(broader.rollout_step, "BROADER");
  assert.equal(decide(engine, event("agent-c", HOST, 90, 24)).decision_class, "PROMOTED_MATCH");

  const reviewed = api.review(engine, { rule_id: "rule-host", actor: "dee", verdict: "PASS" });
  assert.equal(reviewed.ok, true);
  assert.equal(reviewed.stage, "REVIEW");
  assert.equal(decide(engine, event("agent-a", HOST, 90, 25)).decision_class, "PROMOTED_MATCH");

  const rolled = api.revokeOrRollback(engine, {
    rule_id: "rule-host",
    actor: "ev",
    reason: "known-good restore",
  });
  assert.equal(rolled.ok, true);
  assert.equal(rolled.stage, "REVOKE_OR_ROLLBACK");
  assert.equal(rolled.restored_stage, "CANARY");
  assert.equal(rolled.in_active_set, false);
  assert.deepEqual(api.activeEnforcement(engine), []);
  assert.equal(decide(engine, event("agent-a", HOST, 90, 26)).decision_class, "ROLLED_BACK");

  const retired = api.retire(engine, { rule_id: "rule-host", actor: "fa" });
  assert.equal(retired.stage, "RETIRE");
  const removed = api.verifyRemoval(engine, { rule_id: "rule-host", actor: "fa" });
  assert.equal(removed.ok, true);
  assert.equal(removed.stage, "VERIFY_REMOVAL");
  assert.equal(removed.probe.decision_class, "RETIRED");
  assert.equal(decide(engine, event("agent-a", HOST, 90, 27)).decision_class, "REMOVED");

  const rule = api.listEvidence(engine, "DISCOVER");
  assert.equal(rule.length, 1);
  assert.deepEqual(
    [...engine.rules.get("rule-host").history.map((entry) => entry.to)],
    api.STAGES,
  );
  for (const kind of ["PROPOSAL", "SIMULATION", "IMPACT", "CANARY", "PROMOTION", "ROLLOUT", "REVIEW", "ROLLBACK", "RETIREMENT", "REMOVAL"]) {
    assert.equal(api.listEvidence(engine, kind).length > 0, true, kind);
  }
  assert.equal(EFFECT, "DECLARED_HOST_MATCH");
  assert.equal(PREDICATE.host_equals, HOST);
});

test("historical replay is shadow-only and does not move a proposed rule by itself", () => {
  const engine = create();
  api.discover(engine, {
    rule_id: "rule-host",
    actor: "ada",
    signal: event("agent-a", HOST, 10, 1),
  });
  api.observe(engine, {
    rule_id: "rule-host",
    actor: "ada",
    observation: event("agent-a", HOST, 10, 1),
  });
  api.propose(engine, {
    rule_id: "rule-host",
    actor: "ada",
    effect: EFFECT,
    predicate: PREDICATE,
  });
  const replay = api.replayHistory("rule-host", PREDICATE, loadHistory(), "SHADOW");
  assert.equal(replay.ok, true);
  assert.equal(replay.shadow_decision_count, 4);
  assert.equal(engine.rules.get("rule-host").stage, "PROPOSE");
  assert.deepEqual(api.activeEnforcement(engine), []);
  assert.equal(decide(engine, event("agent-a", HOST, 90, 2)).decision_class, "PROPOSAL");
});

test("staged rollout refuses a skip, a same-actor approval, and a first step past the cohort", () => {
  const engine = create();
  throughCanary(engine);
  assert.equal(api.promote(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "bo",
  }).code, "SAME_ACTOR");
  assert.equal(api.promote(engine, {
    rule_id: "rule-host",
    actor: "bo",
    approver: "cy",
    rollout_request: "BROADER",
  }).code, "ROLLOUT_NOT_FIRST_STEP");
  assert.equal(engine.rules.get("rule-host").stage, "CANARY");
  assert.deepEqual(api.activeEnforcement(engine), []);
});

test("review failure rolls back to the known-good snapshot", () => {
  const engine = create();
  throughCanary(engine);
  api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  const failed = api.review(engine, {
    rule_id: "rule-host",
    actor: "dee",
    verdict: "FAIL",
    reason: "impact too wide",
  });
  assert.equal(failed.stage, "REVOKE_OR_ROLLBACK");
  assert.equal(failed.restored_stage, "CANARY");
  assert.equal(decide(engine, event("agent-a", HOST, 90, 30)).decision_class, "ROLLED_BACK");
  assert.equal(api.review(engine, {
    rule_id: "rule-host",
    actor: "bo",
    verdict: "PASS",
  }).code, "WRONG_STAGE");
});

test("exception expiry does not promote and stops suppressing only an already promoted rule", () => {
  const clock = mutable(1000);
  const engine = clock.engine;
  throughCanary(engine);
  api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  const granted = api.grantException(engine, {
    rule_id: "rule-host",
    actor: "dee",
    subject_ref: "agent-a",
    not_after: 1500,
  });
  assert.equal(granted.ok, true);
  assert.equal(granted.stage, "ENFORCE");
  assert.equal(decide(engine, event("agent-a", HOST, 90, 1100)).decision_class, "EXCEPTION");
  clock.set(1500);
  const expired = api.expireDueExceptions(engine);
  assert.deepEqual(expired.expired, [granted.exception_id]);
  assert.equal(expired.promotions, 0);
  assert.equal(expired.stages_changed, false);
  assert.equal(expired.auto_promoted, false);
  assert.equal(engine.rules.get("rule-host").stage, "ENFORCE");
  assert.equal(decide(engine, event("agent-a", HOST, 90, 1500)).decision_class, "PROMOTED_MATCH");
});

test("an exception cannot be granted before promotion", () => {
  const engine = create();
  api.discover(engine, {
    rule_id: "rule-host",
    actor: "ada",
    signal: event("agent-a", HOST, 10, 1),
  });
  api.observe(engine, {
    rule_id: "rule-host",
    actor: "ada",
    observation: event("agent-a", HOST, 10, 1),
  });
  const early = api.grantException(engine, {
    rule_id: "rule-host",
    actor: "ada",
    subject_ref: "agent-a",
    not_after: 5000,
  });
  assert.equal(early.code, "EXCEPTION_BEFORE_PROMOTION");
  const expired = api.expireDueExceptions(engine, { now: 9000, enforce: true });
  assert.equal(expired.promotions, 0);
  assert.equal(expired.stages_changed, false);
  assert.equal(engine.rules.get("rule-host").stage, "OBSERVE");
});

test("emergency freeze blocks promotion and promoted matches and still allows rollback", () => {
  const engine = create();
  throughCanary(engine, "held");
  const frozen = api.freeze(engine, { actor: "ev", reason: "stop expansion" });
  assert.equal(frozen.ok, true);
  const blocked = api.promote(engine, { rule_id: "held", actor: "bo", approver: "cy" });
  assert.equal(blocked.code, "FROZEN");
  assert.equal(engine.rules.get("held").stage, "CANARY");
  api.thaw(engine, { actor: "ev" });
  api.promote(engine, { rule_id: "held", actor: "bo", approver: "cy" });
  const stages = engine.rules.get("held").stage;
  api.freeze(engine, { actor: "ev", reason: "second freeze" });
  assert.equal(decide(engine, event("agent-a", HOST, 90, 40), "held").decision_class, "FROZEN");
  assert.equal(api.advanceRollout(engine, {
    rule_id: "held",
    actor: "bo",
    approver: "cy",
    to_step: "LIMITED",
    prior_evidence_id: engine.rules.get("held").promotion.evidence_id,
    limited_subject_refs: ["agent-a", "agent-b"],
  }).code, "FROZEN");
  const rolled = api.revokeOrRollback(engine, { rule_id: "held", actor: "ev", reason: "freeze rollback" });
  assert.equal(rolled.stage, "REVOKE_OR_ROLLBACK");
  const thawed = api.thaw(engine, { actor: "fa" });
  assert.equal(thawed.stages_changed, false);
  assert.equal(engine.rules.get("held").stage, "REVOKE_OR_ROLLBACK");
  assert.equal(stages, "ENFORCE");
});

test("verifyRemoval stays retired when the rule is still armed", () => {
  const engine = create();
  throughCanary(engine);
  api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  api.review(engine, { rule_id: "rule-host", actor: "dee", verdict: "PASS" });
  api.revokeOrRollback(engine, { rule_id: "rule-host", actor: "ev", reason: "pull back" });
  api.retire(engine, { rule_id: "rule-host", actor: "fa" });
  engine.active.add("rule-host");
  const probe = api.verifyRemoval(engine, { rule_id: "rule-host", actor: "fa" });
  assert.equal(probe.code, "STILL_ARMED");
  assert.equal(engine.rules.get("rule-host").stage, "RETIRE");
  engine.active.delete("rule-host");
  assert.equal(api.verifyRemoval(engine, { rule_id: "rule-host", actor: "fa" }).stage, "VERIFY_REMOVAL");
});

test("a stage-only mutation does not count as promotion", () => {
  const engine = create();
  throughCanary(engine);
  engine.rules.get("rule-host").stage = "ENFORCE";
  const decision = decide(engine, event("agent-a", HOST, 90, 50));
  assert.equal(decision.decision_class, "REFUSED");
  assert.equal(decision.enforcement_attached, false);
  assert.deepEqual(api.activeEnforcement(engine), []);
});

test("promotion evidence cites replay, shadow count, canary impact, and the known-good snapshot", () => {
  const engine = create();
  const walked = throughCanary(engine);
  const promoted = api.promote(engine, { rule_id: "rule-host", actor: "bo", approver: "cy" });
  const body = api.listEvidence(engine, "PROMOTION")[0].body;
  assert.equal(body.replay_digest, walked.simulation.replay_digest);
  assert.equal(body.shadow_decision_count, 4);
  assert.equal(body.canary_impact.label, "CANARY");
  assert.equal(body.per_rule_impact.label, "SHADOW");
  assert.equal(body.known_good_snapshot_id, promoted.known_good_snapshot_id);
  assert.equal(body.auto_promoted, false);
  assert.equal(body.rollout_step, "COHORT");
  assert.equal(engine.rules.get("rule-host").known_good.snapshot.stage, "CANARY");
});
