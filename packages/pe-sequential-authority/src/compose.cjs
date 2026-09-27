"use strict";

const { COMPOSITIONS } = require("./boundary.cjs");
const { compositionKey } = require("./ledger.cjs");

function pairBound(envelope, step) {
  return envelope.bound_uses.some(
    (pair) => pair.credential_id === step.credential_id && pair.destination === step.destination,
  );
}

function compositionDenial(envelope, ledger, step) {
  if (step.raises_ceiling === true) {
    return {
      invariant: "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY",
      reason: "raise_composes_widen",
      axis: "sequence",
    };
  }
  if (step.composed_effect !== null && step.composed_effect !== step.action) {
    return {
      invariant: "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY",
      reason: "one_step_does_not_compose_a_second_effect",
      axis: "sequence",
    };
  }
  if (step.credential_id !== null && step.destination !== null && !pairBound(envelope, step)) {
    return {
      invariant: "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY",
      reason: "unbound_credential_destination",
      axis: "sequence",
    };
  }
  const history = ledger.sequences[compositionKey(envelope)] || [];
  for (const rule of COMPOSITIONS) {
    if (step.action !== rule.stepAction) continue;
    const prior = history.some((effect) => effect.action === rule.priorAction);
    if (!prior) continue;
    if (!envelope.actions.includes(rule.derived)) {
      return {
        invariant: "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY",
        reason: rule.id,
        axis: "sequence",
      };
    }
  }
  return null;
}

module.exports = {
  compositionDenial,
};
