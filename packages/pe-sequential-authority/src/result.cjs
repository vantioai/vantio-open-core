"use strict";

const { ENFORCEMENT } = require("./boundary.cjs");

function toResult(spec) {
  return {
    disposition: spec.disposition,
    invariant: spec.invariant ?? null,
    rule: spec.rule ?? null,
    axis: spec.axis ?? null,
    reason: spec.reason,
    envelope_id: spec.envelope_id ?? null,
    principal_id: spec.principal_id ?? null,
    process_id: spec.process_id ?? null,
    consensus_ignored: spec.consensus_ignored === true,
    host_attachment: false,
    enforcement: ENFORCEMENT,
    doctrine_present: false,
    ledger: spec.ledger ?? null,
    receipt: spec.receipt ?? null,
    revoke_transition: spec.revoke_transition ?? null,
    envelope: spec.envelope ?? null,
    catalog: spec.catalog ?? null,
    revoked_ids: spec.revoked_ids ?? null,
  };
}

function inputResult(reason, extras) {
  return toResult({
    disposition: "DENY",
    rule: "INPUT_REJECTED",
    reason,
    ...extras,
  });
}

module.exports = {
  inputResult,
  toResult,
};
