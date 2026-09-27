"use strict";

const { STALENESS_TRIGGERS } = require("./constants.cjs");

function assessStaleness(control, context = {}) {
  const reasons = [];
  if (control.evidence_freshness === "STALE") reasons.push("EVIDENCE_STALE");
  if (control.evidence_freshness === "UNSET") reasons.push("EVIDENCE_UNSET");
  if (control.evidence_freshness === "UNKNOWN") reasons.push("FRESHNESS_UNKNOWN");
  const triggers = Array.isArray(context.triggers) ? context.triggers : [];
  for (const trigger of triggers) {
    if (!STALENESS_TRIGGERS.includes(trigger)) {
      throw new Error(`unknown staleness trigger ${trigger}`);
    }
    reasons.push(trigger);
  }
  if (context.frameworkSuperseded === true) reasons.push("AUTHORITY_POLICY_CHANGED");
  return {
    stale: reasons.length > 0,
    reasons,
    clears_prior_pass: reasons.length > 0,
  };
}

module.exports = {
  assessStaleness,
};
