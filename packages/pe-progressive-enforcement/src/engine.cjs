"use strict";

const {
  MAX_BROADER,
  MAX_COHORT,
  MAX_LIMITED,
  MAX_OBSERVATIONS,
  REJECTED_ACTORS,
  ROLLOUT_STEPS,
  STAGES,
} = require("./boundary.cjs");
const { digest } = require("./canonical.cjs");
const { recordEvidence } = require("./evidence.cjs");
const {
  isStrictSuperset,
  matches,
  structuralEvent,
  uniqueIds,
  validId,
  validatePredicate,
} = require("./predicate.cjs");
const { replayHistory } = require("./replay.cjs");

function createEngine(options = {}) {
  const now = typeof options.now === "function" ? options.now : () => Date.now();
  return {
    now,
    seq: 0,
    rules: new Map(),
    evidence: [],
    freeze: null,
    active: new Set(),
  };
}

function refuse(code, extra = {}) {
  return {
    ok: false,
    code,
    enforced: false,
    auto_promoted: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
    ...extra,
  };
}

function clock(engine) {
  const at = engine.now();
  if (!Number.isSafeInteger(at) || at < 0) return null;
  return at;
}

function checkActor(actor) {
  if (typeof actor !== "string" || !/^[a-z0-9][a-z0-9._:-]{0,63}$/.test(actor)) return "BAD_ACTOR";
  if (REJECTED_ACTORS.has(actor)) return "AUTO_REJECTED";
  return null;
}

function controlAttempt(input) {
  if (!input || typeof input !== "object") return [];
  const found = [];
  for (const key of ["enforce", "auto", "automatic", "auto_promote", "promote", "stage"]) {
    if (Object.hasOwn(input, key) && input[key] !== false && input[key] !== undefined) found.push(key);
  }
  return found;
}

function blankRule(ruleId, at) {
  return {
    rule_id: ruleId,
    stage: null,
    signal: null,
    observations: [],
    predicate: null,
    effect: null,
    proposal: null,
    simulation: null,
    canary: null,
    promotion: null,
    review: null,
    known_good: null,
    restored_known_good: null,
    rollout: { step: "NONE", cohort: [], limited: [], broader: [] },
    exceptions: [],
    history: [],
    created_at: at,
  };
}

function transition(engine, rule, to, op, actor, evidence) {
  const from = rule.stage;
  rule.stage = to;
  rule.history.push({
    from,
    to,
    op,
    actor,
    evidence_id: evidence.evidence_id,
    at: evidence.at,
  });
}

function view(engine, rule) {
  return {
    rule_id: rule.rule_id,
    stage: rule.stage,
    observation_count: rule.observations.length,
    rollout_step: rule.rollout.step,
    history: rule.history.map((entry) => entry.to),
    in_active_set: engine.active.has(rule.rule_id),
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
    auto_promoted: false,
  };
}

function accept(engine, rule, extra = {}) {
  return {
    ok: true,
    ...view(engine, rule),
    ...extra,
    auto_promoted: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
  };
}

function requireRule(engine, ruleId) {
  if (!validId(ruleId)) return { ok: false, code: "BAD_INPUT" };
  const rule = engine.rules.get(ruleId);
  if (!rule) return { ok: false, code: "UNKNOWN_RULE" };
  return { ok: true, rule };
}

function requireStage(rule, expected) {
  return rule.stage === expected ? null : "WRONG_STAGE";
}

function requireOneOf(rule, expected) {
  return expected.includes(rule.stage) ? null : "WRONG_STAGE";
}

function unhandledStage(stage) {
  const unexpected = stage;
  throw new Error(`unhandled lifecycle stage: ${String(unexpected)}`);
}

function decisionClassForStage(stage) {
  switch (stage) {
    case "DISCOVER":
    case "OBSERVE":
      return "OBSERVATION";
    case "PROPOSE":
      return "PROPOSAL";
    case "SIMULATE":
      return "SHADOW";
    case "CANARY":
      return "CANARY";
    case "ENFORCE":
    case "REVIEW":
      return "PROMOTED_MATCH";
    case "REVOKE_OR_ROLLBACK":
      return "ROLLED_BACK";
    case "RETIRE":
      return "RETIRED";
    case "VERIFY_REMOVAL":
      return "REMOVED";
    case null:
      return "REFUSED";
    default:
      return unhandledStage(stage);
  }
}

function rolloutMembers(rule) {
  switch (rule.rollout.step) {
    case "NONE":
      return [];
    case "COHORT":
      return rule.rollout.cohort;
    case "LIMITED":
      return rule.rollout.limited;
    case "BROADER":
      return rule.rollout.broader;
    default: {
      const unexpected = rule.rollout.step;
      throw new Error(`unhandled rollout step: ${String(unexpected)}`);
    }
  }
}

function promotionArmed(engine, rule) {
  return (rule.stage === "ENFORCE" || rule.stage === "REVIEW")
    && engine.active.has(rule.rule_id)
    && rule.promotion !== null
    && rule.known_good !== null
    && rule.rollout.step !== "NONE";
}

function activeException(rule, subjectRef, now) {
  return rule.exceptions.some((item) => (
    item.status === "ACTIVE"
    && item.subject_ref === subjectRef
    && item.not_after > now
  ));
}

function knownGoodSnapshot(rule) {
  return {
    stage: rule.stage,
    rollout_step: rule.rollout.step,
    effect: rule.effect,
    predicate: rule.predicate ? { ...rule.predicate } : null,
    proposal_id: rule.proposal ? rule.proposal.evidence_id : null,
    simulation_id: rule.simulation ? rule.simulation.evidence_id : null,
    canary_id: rule.canary ? rule.canary.evidence_id : null,
    cohort: rule.rollout.cohort.slice(),
  };
}

function discover(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (!input || !validId(input.rule_id)) return refuse("BAD_INPUT");
  if (engine.rules.has(input.rule_id)) {
    return refuse("ALREADY_EXISTS", { stage: engine.rules.get(input.rule_id).stage });
  }
  const signal = structuralEvent(input.signal);
  if (!signal.ok) return refuse(signal.code);
  const rule = blankRule(input.rule_id, clock(engine));
  rule.signal = signal.value;
  engine.rules.set(rule.rule_id, rule);
  const evidence = recordEvidence(engine, "DISCOVER", {
    rule_id: rule.rule_id,
    actor: input.actor,
    signal: signal.value,
  });
  transition(engine, rule, "DISCOVER", "discover", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id, control_attempt: controlAttempt(input.signal) });
}

function observe(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  if (rule.observations.length >= MAX_OBSERVATIONS) {
    return refuse("OBSERVATION_CAP", { stage: rule.stage });
  }
  const event = structuralEvent(input.observation || input);
  if (!event.ok) return refuse(event.code, { stage: rule.stage });
  rule.observations.push(event.value);
  const evidence = recordEvidence(engine, "OBSERVATION", {
    rule_id: rule.rule_id,
    actor: input.actor,
    observation: event.value,
    observation_count: rule.observations.length,
  });
  if (rule.stage === "DISCOVER") transition(engine, rule, "OBSERVE", "observe", input.actor, evidence);
  const observedControls = controlAttempt(input);
  if (input.observation) observedControls.push(...controlAttempt(input.observation));
  return accept(engine, rule, {
    evidence_id: evidence.evidence_id,
    proposal_created: false,
    control_attempt: observedControls,
  });
}

function propose(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (input && (input.auto === true || input.enforce === true || input.auto_promote === true)) {
    return refuse("AUTO_REJECTED");
  }
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "OBSERVE");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (rule.observations.length < 1) return refuse("MISSING_OBSERVATION", { stage: rule.stage });
  const predicate = validatePredicate(input.effect, input.predicate);
  if (!predicate.ok) return refuse(predicate.code, { stage: rule.stage });
  rule.predicate = predicate.value;
  rule.effect = input.effect;
  const evidence = recordEvidence(engine, "PROPOSAL", {
    rule_id: rule.rule_id,
    actor: input.actor,
    effect: input.effect,
    predicate: predicate.value,
    observation_count: rule.observations.length,
    auto_promoted: false,
  });
  rule.proposal = {
    evidence_id: evidence.evidence_id,
    actor: input.actor,
    effect: input.effect,
    predicate: predicate.value,
  };
  transition(engine, rule, "PROPOSE", "propose", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id, proposal_created: true });
}

function simulate(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (input && (input.auto === true || input.enforce === true || input.auto_promote === true)) {
    return refuse("AUTO_REJECTED");
  }
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "PROPOSE");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!rule.proposal) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  const replay = replayHistory(rule.rule_id, rule.predicate, input.corpus, "SHADOW");
  if (!replay.ok) return refuse(replay.code, { stage: rule.stage });
  const evidence = recordEvidence(engine, "SIMULATION", {
    rule_id: rule.rule_id,
    actor: input.actor,
    proposal_id: rule.proposal.evidence_id,
    replay_digest: replay.replay_digest,
    shadow_decision_count: replay.shadow_decision_count,
    impact: replay.impact,
    decisions: replay.decisions,
  });
  const impactEvidence = recordEvidence(engine, "IMPACT", {
    rule_id: rule.rule_id,
    impact: replay.impact,
  });
  rule.simulation = {
    evidence_id: evidence.evidence_id,
    impact_id: impactEvidence.evidence_id,
    replay_digest: replay.replay_digest,
    shadow_decision_count: replay.shadow_decision_count,
    impact: replay.impact,
    decisions: replay.decisions,
  };
  transition(engine, rule, "SIMULATE", "simulate", input.actor, evidence);
  return accept(engine, rule, {
    evidence_id: evidence.evidence_id,
    replay_digest: replay.replay_digest,
    impact: replay.impact,
    shadow_decision_count: replay.shadow_decision_count,
  });
}

function canary(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (input && (input.auto === true || input.enforce === true || input.auto_promote === true)) {
    return refuse("AUTO_REJECTED");
  }
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "SIMULATE");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!rule.simulation) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  const cohort = input.cohort;
  if (!cohort || !validId(cohort.cohort_id)) return refuse("COHORT_UNBOUNDED", { stage: rule.stage });
  const members = uniqueIds(cohort.subject_refs, MAX_COHORT);
  if (!members) return refuse("COHORT_UNBOUNDED", { stage: rule.stage });
  const samples = input.samples;
  if (!Array.isArray(samples) || samples.length < 1) return refuse("BAD_CORPUS", { stage: rule.stage });
  for (const sample of samples) {
    const parsed = structuralEvent(sample, "reject");
    if (!parsed.ok) return refuse("BAD_CORPUS", { stage: rule.stage });
    if (!members.includes(parsed.value.subject_ref)) return refuse("CANARY_SAMPLE_OUTSIDE", { stage: rule.stage });
  }
  const replay = replayHistory(rule.rule_id, rule.predicate, samples, "CANARY");
  if (!replay.ok) return refuse(replay.code, { stage: rule.stage });
  const evidence = recordEvidence(engine, "CANARY", {
    rule_id: rule.rule_id,
    actor: input.actor,
    cohort_id: cohort.cohort_id,
    subject_refs: members,
    simulation_id: rule.simulation.evidence_id,
    replay_digest: replay.replay_digest,
    impact: replay.impact,
    decisions: replay.decisions,
  });
  rule.canary = {
    evidence_id: evidence.evidence_id,
    cohort_id: cohort.cohort_id,
    subject_refs: members,
    replay_digest: replay.replay_digest,
    impact: replay.impact,
    decisions: replay.decisions,
  };
  rule.rollout.cohort = members.slice();
  transition(engine, rule, "CANARY", "canary", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id, impact: replay.impact });
}

function promote(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const approverError = checkActor(input && input.approver);
  if (approverError) return refuse(approverError);
  if (input.auto === true || input.enforce === true || input.auto_promote === true || input.automatic === true) {
    return refuse("AUTO_REJECTED");
  }
  if (input.actor === input.approver) return refuse("SAME_ACTOR");
  if (engine.freeze) return refuse("FROZEN");
  const found = requireRule(engine, input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "CANARY");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!rule.proposal || !rule.simulation || !rule.canary) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  if (rule.simulation.shadow_decision_count < 1) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  const requested = input.rollout_request === undefined ? "COHORT" : input.rollout_request;
  if (requested !== "COHORT") return refuse("ROLLOUT_NOT_FIRST_STEP", { stage: rule.stage });
  const snapshot = knownGoodSnapshot(rule);
  const snapshotId = `snap_${digest(snapshot).slice(0, 16)}`;
  rule.known_good = { snapshot_id: snapshotId, snapshot };
  const evidence = recordEvidence(engine, "PROMOTION", {
    rule_id: rule.rule_id,
    actor: input.actor,
    approver: input.approver,
    proposal_id: rule.proposal.evidence_id,
    simulation_id: rule.simulation.evidence_id,
    replay_digest: rule.simulation.replay_digest,
    shadow_decision_count: rule.simulation.shadow_decision_count,
    canary_id: rule.canary.evidence_id,
    canary_impact: rule.canary.impact,
    per_rule_impact: rule.simulation.impact,
    known_good_snapshot_id: snapshotId,
    rollout_step: "COHORT",
    auto_promoted: false,
  });
  rule.promotion = {
    evidence_id: evidence.evidence_id,
    actor: input.actor,
    approver: input.approver,
    snapshot_id: snapshotId,
  };
  rule.rollout.step = "COHORT";
  engine.active.add(rule.rule_id);
  transition(engine, rule, "ENFORCE", "promote", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id, known_good_snapshot_id: snapshotId });
}

function nextRollout(step) {
  const index = ROLLOUT_STEPS.indexOf(step);
  if (index < 0 || index >= ROLLOUT_STEPS.length - 1) return null;
  return ROLLOUT_STEPS[index + 1];
}

function advanceRollout(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const approverError = checkActor(input && input.approver);
  if (approverError) return refuse(approverError);
  if (input.auto === true || input.enforce === true || input.auto_promote === true || input.from_observations === true) {
    return refuse("AUTO_REJECTED");
  }
  if (input.actor === input.approver) return refuse("SAME_ACTOR");
  if (engine.freeze) return refuse("FROZEN");
  const found = requireRule(engine, input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireOneOf(rule, ["ENFORCE", "REVIEW"]);
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!promotionArmed(engine, rule)) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  const expected = nextRollout(rule.rollout.step);
  if (!expected || input.to_step !== expected) return refuse("ROLLOUT_SKIP", { stage: rule.stage, rollout_step: rule.rollout.step });
  const prior = rule.rollout.evidence_id || rule.promotion.evidence_id;
  if (input.prior_evidence_id !== prior) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  let members;
  if (expected === "LIMITED") {
    members = uniqueIds(input.limited_subject_refs, MAX_LIMITED);
    if (!members || !isStrictSuperset(members, rule.rollout.cohort)) {
      return refuse("ROLLOUT_NOT_SUPERSET", { stage: rule.stage });
    }
    rule.rollout.limited = members;
  } else if (expected === "BROADER") {
    members = uniqueIds(input.broader_subject_refs, MAX_BROADER);
    if (!members || !isStrictSuperset(members, rule.rollout.limited)) {
      return refuse("ROLLOUT_NOT_SUPERSET", { stage: rule.stage });
    }
    rule.rollout.broader = members;
  } else {
    return refuse("ROLLOUT_SKIP", { stage: rule.stage });
  }
  const evidence = recordEvidence(engine, "ROLLOUT", {
    rule_id: rule.rule_id,
    actor: input.actor,
    approver: input.approver,
    from_step: rule.rollout.step,
    to_step: expected,
    subject_refs: members,
    prior_evidence_id: input.prior_evidence_id,
    auto_promoted: false,
  });
  rule.rollout.step = expected;
  rule.rollout.evidence_id = evidence.evidence_id;
  return accept(engine, rule, { evidence_id: evidence.evidence_id });
}

function revokeOrRollback(engine, input, op) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireOneOf(rule, ["ENFORCE", "REVIEW"]);
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!rule.known_good) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  if (typeof input.reason !== "string" || input.reason.length < 1 || input.reason.length > 200) {
    return refuse("BAD_INPUT", { stage: rule.stage });
  }
  const evidence = recordEvidence(engine, "ROLLBACK", {
    rule_id: rule.rule_id,
    actor: input.actor,
    reason: input.reason,
    known_good_snapshot_id: rule.known_good.snapshot_id,
    restored_stage: rule.known_good.snapshot.stage,
    op,
  });
  rule.restored_known_good = rule.known_good;
  rule.rollout.step = "NONE";
  engine.active.delete(rule.rule_id);
  transition(engine, rule, "REVOKE_OR_ROLLBACK", op, input.actor, evidence);
  return accept(engine, rule, {
    evidence_id: evidence.evidence_id,
    known_good_snapshot_id: rule.known_good.snapshot_id,
    restored_stage: rule.known_good.snapshot.stage,
  });
}

function review(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "ENFORCE");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  if (!rule.promotion) return refuse("MISSING_EVIDENCE", { stage: rule.stage });
  if (input.actor === rule.promotion.actor || input.actor === rule.promotion.approver) {
    return refuse("SAME_ACTOR", { stage: rule.stage });
  }
  if (input.verdict !== "PASS" && input.verdict !== "FAIL") return refuse("BAD_INPUT", { stage: rule.stage });
  if (input.verdict === "FAIL") {
    return revokeOrRollback(engine, {
      rule_id: rule.rule_id,
      actor: input.actor,
      reason: input.reason || "review-fail",
    }, "review_fail");
  }
  const evidence = recordEvidence(engine, "REVIEW", {
    rule_id: rule.rule_id,
    actor: input.actor,
    verdict: "PASS",
  });
  rule.review = { evidence_id: evidence.evidence_id, actor: input.actor, verdict: "PASS" };
  transition(engine, rule, "REVIEW", "review", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id });
}

function retire(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "REVOKE_OR_ROLLBACK");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  const evidence = recordEvidence(engine, "RETIREMENT", {
    rule_id: rule.rule_id,
    actor: input.actor,
  });
  rule.rollout = { step: "NONE", cohort: [], limited: [], broader: [] };
  engine.active.delete(rule.rule_id);
  transition(engine, rule, "RETIRE", "retire", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id });
}

function removalProbe(engine, rule) {
  const sample = rule.observations[0] || rule.signal;
  const decision = sample
    ? decide(engine, { rule_id: rule.rule_id, ...sample })
    : { decision_class: "REFUSED" };
  return {
    in_active: engine.active.has(rule.rule_id),
    rollout_step: rule.rollout.step,
    decision_class: decision.decision_class,
    enforcement_attached: false,
  };
}

function verifyRemoval(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireStage(rule, "RETIRE");
  if (stageError) return refuse(stageError, { stage: rule.stage });
  const probe = removalProbe(engine, rule);
  const armed = probe.in_active
    || probe.rollout_step !== "NONE"
    || probe.decision_class === "PROMOTED_MATCH"
    || probe.decision_class === "CANARY";
  if (armed) return refuse("STILL_ARMED", { stage: rule.stage, probe });
  const evidence = recordEvidence(engine, "REMOVAL", {
    rule_id: rule.rule_id,
    actor: input.actor,
    probe,
  });
  transition(engine, rule, "VERIFY_REMOVAL", "verify_removal", input.actor, evidence);
  return accept(engine, rule, { evidence_id: evidence.evidence_id, probe });
}

function freeze(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (engine.freeze) return refuse("ALREADY_FROZEN");
  if (typeof input.reason !== "string" || input.reason.length < 1 || input.reason.length > 200) {
    return refuse("BAD_INPUT");
  }
  const evidence = recordEvidence(engine, "FREEZE", { actor: input.actor, reason: input.reason });
  const stages = [...engine.rules.values()].map((rule) => ({ rule_id: rule.rule_id, stage: rule.stage }));
  engine.freeze = { actor: input.actor, reason: input.reason, at: evidence.at, evidence_id: evidence.evidence_id };
  return {
    ok: true,
    evidence_id: evidence.evidence_id,
    stages,
    auto_promoted: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
  };
}

function thaw(engine, input) {
  if (!clock(engine)) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  if (!engine.freeze) return refuse("NOT_FROZEN");
  const before = [...engine.rules.values()].map((rule) => ({ rule_id: rule.rule_id, stage: rule.stage }));
  const evidence = recordEvidence(engine, "THAW", { actor: input.actor });
  engine.freeze = null;
  const after = [...engine.rules.values()].map((rule) => ({ rule_id: rule.rule_id, stage: rule.stage }));
  return {
    ok: true,
    evidence_id: evidence.evidence_id,
    stages_before: before,
    stages_after: after,
    stages_changed: JSON.stringify(before) !== JSON.stringify(after),
    auto_promoted: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
  };
}

function grantException(engine, input) {
  const now = clock(engine);
  if (now === null) return refuse("BAD_CLOCK");
  const actorError = checkActor(input && input.actor);
  if (actorError) return refuse(actorError);
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code);
  const rule = found.rule;
  const stageError = requireOneOf(rule, ["ENFORCE", "REVIEW"]);
  if (stageError) return refuse("EXCEPTION_BEFORE_PROMOTION", { stage: rule.stage });
  if (!validId(input.subject_ref)) return refuse("BAD_INPUT", { stage: rule.stage });
  if (!Number.isSafeInteger(input.not_after) || input.not_after <= now) {
    return refuse("EXCEPTION_NOT_FUTURE", { stage: rule.stage });
  }
  const evidence = recordEvidence(engine, "EXCEPTION", {
    rule_id: rule.rule_id,
    actor: input.actor,
    subject_ref: input.subject_ref,
    not_after: input.not_after,
  });
  rule.exceptions.push({
    exception_id: evidence.evidence_id,
    subject_ref: input.subject_ref,
    not_after: input.not_after,
    status: "ACTIVE",
    actor: input.actor,
  });
  return accept(engine, rule, { evidence_id: evidence.evidence_id, exception_id: evidence.evidence_id });
}

function expireDueExceptions(engine, input = {}) {
  const now = Number.isSafeInteger(input.now) ? input.now : clock(engine);
  if (now === null) return refuse("BAD_CLOCK");
  const stagesBefore = [...engine.rules.values()].map((rule) => rule.stage);
  const expired = [];
  for (const rule of engine.rules.values()) {
    for (const item of rule.exceptions) {
      if (item.status === "ACTIVE" && item.not_after <= now) {
        item.status = "EXPIRED";
        expired.push(item.exception_id);
      }
    }
  }
  if (expired.length > 0) {
    recordEvidence(engine, "EXCEPTION_EXPIRY", { expired, now, promotions: 0 });
  }
  const stagesAfter = [...engine.rules.values()].map((rule) => rule.stage);
  return {
    ok: true,
    expired,
    promotions: 0,
    stages_changed: stagesBefore.join() !== stagesAfter.join(),
    auto_promoted: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    enforcement_attached: false,
  };
}

function inCanaryCohort(rule, subjectRef) {
  return rule.canary !== null && rule.canary.subject_refs.includes(subjectRef);
}

function decide(engine, input) {
  const now = clock(engine);
  if (now === null) return refuse("BAD_CLOCK", { decision_class: "REFUSED" });
  const found = requireRule(engine, input && input.rule_id);
  if (!found.ok) return refuse(found.code, { decision_class: "REFUSED" });
  const rule = found.rule;
  const event = structuralEvent({
    subject_ref: input.subject_ref,
    host: input.host,
    byte_count: input.byte_count,
    at: input.at,
  });
  if (!event.ok) return refuse(event.code, { decision_class: "REFUSED", stage: rule.stage });
  const matched = rule.predicate ? matches(rule.predicate, event.value) : false;
  let decisionClass = decisionClassForStage(rule.stage);
  if (rule.stage === "CANARY") {
    decisionClass = matched && inCanaryCohort(rule, event.value.subject_ref) ? "CANARY" : "SHADOW";
  } else if (rule.stage === "ENFORCE" || rule.stage === "REVIEW") {
    if (!promotionArmed(engine, rule)) decisionClass = "REFUSED";
    else if (engine.freeze) decisionClass = "FROZEN";
    else if (activeException(rule, event.value.subject_ref, now)) decisionClass = "EXCEPTION";
    else if (!rolloutMembers(rule).includes(event.value.subject_ref)) decisionClass = "SHADOW";
    else decisionClass = matched ? "PROMOTED_MATCH" : "SHADOW";
  }
  return {
    ok: true,
    rule_id: rule.rule_id,
    lifecycle_stage: rule.stage,
    decision_class: decisionClass,
    matched,
    in_active_set: engine.active.has(rule.rule_id),
    applied_to_host: false,
    enforcement_attached: false,
    host_attachment: "NOT_PERFORMED",
    live_enforcement: false,
    auto_promoted: false,
  };
}

function ingest(engine, input) {
  if (!input || typeof input !== "object") return refuse("BAD_INPUT");
  const actorError = checkActor(input.actor);
  if (actorError) return refuse(actorError);
  const controls = controlAttempt(input);
  if (!engine.rules.has(input.rule_id)) {
    const created = discover(engine, { rule_id: input.rule_id, actor: input.actor, signal: input.signal });
    if (!created.ok) return created;
  }
  const observations = Array.isArray(input.observations) ? input.observations : [];
  if (observations.length < 1) return refuse("MISSING_OBSERVATION", { control_attempt: controls });
  let last = null;
  for (const observation of observations) {
    last = observe(engine, { rule_id: input.rule_id, actor: input.actor, observation });
    if (!last.ok) return last;
  }
  let proposalCreated = false;
  if (input.propose === true) {
    const proposed = propose(engine, {
      rule_id: input.rule_id,
      actor: input.actor,
      effect: input.effect,
      predicate: input.predicate,
    });
    if (!proposed.ok) return proposed;
    last = proposed;
    proposalCreated = true;
  }
  const rule = engine.rules.get(input.rule_id);
  return accept(engine, rule, {
    proposal_created: proposalCreated,
    control_attempt: controls,
    evidence_id: last ? last.evidence_id : null,
  });
}

function activeEnforcement(engine) {
  return [...engine.active];
}

function listEvidence(engine, kind) {
  return engine.evidence.filter((item) => item.kind === kind).map((item) => ({
    evidence_id: item.evidence_id,
    kind: item.kind,
    at: item.at,
    dropped: item.dropped,
    body: item.body,
  }));
}

module.exports = {
  STAGES,
  activeEnforcement,
  advanceRollout,
  canary,
  createEngine,
  decide,
  discover,
  expireDueExceptions,
  freeze,
  grantException,
  ingest,
  listEvidence,
  observe,
  promote,
  propose,
  review,
  revokeOrRollback,
  simulate,
  thaw,
  retire,
  verifyRemoval,
};
