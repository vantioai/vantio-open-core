"use strict";

const {
  AUDIENCE,
  EVIDENCE_DECISION,
  FRESHNESS,
  FRESHNESS_RULE,
  NOT_PRESENT,
  PACKET_PLANE,
  PROGRAM,
  PROGRAM_CLASSIFICATION,
  authorityFor,
  spokenAllowed,
  spokenFor,
} = require("./constants.cjs");

function containmentFor(reason) {
  const required = reason === "child_process_escape" || reason === "post_accept_denied";
  return {
    required,
    effect: required ? "DECISION_RECORDED_ONLY" : "NONE",
    executor: "NOT_WIRED_IN_LIVE_LOADER",
    connection_isolation: "NOT_PRESENT",
    cgroup_freeze_applied: false,
    identity_revoke: "NOT_EXECUTED",
  };
}

function finishResult(fields) {
  const spoken = spokenFor(fields.reason);
  if (!spokenAllowed(spoken)) {
    throw new Error(`spoken line failed the claim fence: ${fields.reason}`);
  }
  return {
    audience: AUDIENCE,
    program: PROGRAM,
    producer_classification: PROGRAM_CLASSIFICATION,
    decision_classification: "PE_INGRESS_AUTHORITY_DECISION",
    authority: authorityFor(fields.reason),
    reason: fields.reason,
    findings: fields.findings,
    spoken,
    spoken_ok: true,
    evidence_decision: EVIDENCE_DECISION,
    packet_plane: PACKET_PLANE,
    packet_effect: "NOT_APPLIED",
    ingress_hook: "observe",
    live_loader_mutated: false,
    live_bind_refused: false,
    reachability_is_authority: false,
    credential_is_integrity: false,
    ingress_protected_claim: false,
    protection_state_echo_is_ingress_proof: false,
    freshness: FRESHNESS,
    freshness_rule: FRESHNESS_RULE,
    idp_revoke: "NOT_EXECUTED",
    stranger_host_executed: false,
    customer_deployed: false,
    association_not_causation: fields.association_not_causation === true,
    not_present: NOT_PRESENT,
    containment: fields.containment || containmentFor(fields.reason),
    listener_state: fields.listener_state,
    identity_result: fields.identity_result,
    identity_attestation: fields.identity_attestation,
    integrity_result: fields.integrity_result,
    credential_result: fields.credential_result,
    post_accept: fields.post_accept,
    protection_state_echo: fields.protection_state_echo,
    unsupported: fields.unsupported,
    partials: fields.partials,
    notices: fields.notices,
    policy: fields.policy,
    grant_id: fields.grant_id,
    grants_carried: fields.grants_carried,
    boot_id: fields.boot_id,
  };
}

module.exports = {
  containmentFor,
  finishResult,
};
