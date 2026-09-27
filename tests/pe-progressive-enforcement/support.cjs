"use strict";

const fs = require("node:fs");
const path = require("node:path");

const api = require("../../packages/pe-progressive-enforcement/src/index.cjs");

const HOST = "api.example.com";
const EFFECT = "DECLARED_HOST_MATCH";
const PREDICATE = { host_equals: HOST };

function loadHistory() {
  const file = path.join(
    __dirname,
    "../../packages/pe-progressive-enforcement/fixtures/history.json",
  );
  return JSON.parse(fs.readFileSync(file, "utf8")).events;
}

function event(subjectRef, host, byteCount, at) {
  return { subject_ref: subjectRef, host, byte_count: byteCount, at };
}

function create(now = 1000) {
  return api.createEngine({ now: () => now });
}

function mutable(start = 1000) {
  let current = start;
  return {
    engine: api.createEngine({ now: () => current }),
    set(next) {
      current = next;
    },
  };
}

function assertHeld(result) {
  if (!result || result.auto_promoted !== false) {
    throw new Error("auto_promoted");
  }
  if (result.host_attachment !== "NOT_PERFORMED") throw new Error("host_attachment");
  if (result.live_enforcement !== false) throw new Error("live_enforcement");
  if (result.enforcement_attached !== false) throw new Error("enforcement_attached");
}

function throughCanary(engine, ruleId = "rule-host") {
  const history = loadHistory();
  const signal = event("agent-a", HOST, 120, 10);
  let result = api.discover(engine, { rule_id: ruleId, actor: "ada", signal });
  if (!result.ok) throw new Error(result.code);
  result = api.observe(engine, { rule_id: ruleId, actor: "ada", observation: signal });
  if (!result.ok) throw new Error(result.code);
  result = api.propose(engine, {
    rule_id: ruleId,
    actor: "ada",
    effect: EFFECT,
    predicate: PREDICATE,
  });
  if (!result.ok) throw new Error(result.code);
  result = api.simulate(engine, { rule_id: ruleId, actor: "ada", corpus: history });
  if (!result.ok) throw new Error(result.code);
  const simulation = result;
  result = api.canary(engine, {
    rule_id: ruleId,
    actor: "ada",
    cohort: { cohort_id: "cohort-a", subject_refs: ["agent-a"] },
    samples: history.filter((row) => row.subject_ref === "agent-a"),
  });
  if (!result.ok) throw new Error(result.code);
  return { simulation, canary: result, history };
}

module.exports = {
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
};
