"use strict";

const { MAX_CORPUS } = require("./boundary.cjs");
const { digest } = require("./canonical.cjs");
const { impactOf, matches, structuralEvent } = require("./predicate.cjs");

function replayHistory(ruleId, predicate, corpus, label) {
  if (!Array.isArray(corpus) || corpus.length < 1 || corpus.length > MAX_CORPUS) {
    return { ok: false, code: "BAD_CORPUS" };
  }
  const decisions = [];
  for (let index = 0; index < corpus.length; index += 1) {
    const parsed = structuralEvent(corpus[index], "reject");
    if (!parsed.ok) return { ok: false, code: "BAD_CORPUS" };
    const event = parsed.value;
    const matched = matches(predicate, event);
    decisions.push({
      seq: index,
      rule_id: ruleId,
      label,
      matched,
      subject_ref: event.subject_ref,
      host: event.host,
      byte_count: event.byte_count,
      at: event.at,
      applied_to_host: false,
      enforcement_attached: false,
      auto_promoted: false,
    });
  }
  const impact = impactOf(ruleId, label, decisions);
  const replayDigest = digest({
    rule_id: ruleId,
    label,
    decisions: decisions.map((decision) => ({
      seq: decision.seq,
      matched: decision.matched,
      subject_ref: decision.subject_ref,
      host: decision.host,
      byte_count: decision.byte_count,
      at: decision.at,
    })),
  });
  return {
    ok: true,
    decisions,
    impact,
    replay_digest: replayDigest,
    shadow_decision_count: decisions.length,
  };
}

module.exports = {
  replayHistory,
};
