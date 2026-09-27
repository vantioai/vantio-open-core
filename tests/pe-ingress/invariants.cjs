"use strict";

const assert = require("node:assert/strict");

const { BANNED_SPOKEN, PROTECTION_STATES } = require("../../packages/pe-ingress-authority/src/constants.cjs");

function assertClosed(result) {
  assert.equal(result.audience, "INTERNAL_RESTRICTED");
  assert.equal(result.program, "PE_INGRESS_AUTHORITY");
  assert.equal(result.producer_classification, "PE_INGRESS_PROGRAM_READY_FOR_COUNCIL");
  assert.equal(result.decision_classification, "PE_INGRESS_AUTHORITY_DECISION");
  assert.equal(result.live_loader_mutated, false);
  assert.equal(result.live_bind_refused, false);
  assert.equal(result.reachability_is_authority, false);
  assert.equal(result.credential_is_integrity, false);
  assert.equal(result.ingress_protected_claim, false);
  assert.equal(result.protection_state_echo_is_ingress_proof, false);
  assert.equal(result.packet_plane, "OBSERVE_ONLY");
  assert.equal(result.packet_effect, "NOT_APPLIED");
  assert.equal(result.evidence_decision, "observed");
  assert.equal(result.freshness, "UNKNOWN");
  assert.equal(result.freshness_rule, "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN");
  assert.equal(result.ingress_hook, "observe");
  assert.equal(result.idp_revoke, "NOT_EXECUTED");
  assert.equal(result.stranger_host_executed, false);
  assert.equal(result.customer_deployed, false);
  assert.equal(result.spoken_ok, true);
  assert.equal(result.containment.executor, "NOT_WIRED_IN_LIVE_LOADER");
  assert.equal(result.containment.cgroup_freeze_applied, false);
  assert.equal(result.containment.connection_isolation, "NOT_PRESENT");
  assert.equal(result.containment.identity_revoke, "NOT_EXECUTED");
  assert.equal(Object.hasOwn(result, "ActionTaken"), false);
  assert.equal(result.not_present.includes("inbound_packet_drop"), true);
  assert.equal(result.not_present.includes("live_quarantine_executor"), true);
  assert.equal(result.not_present.includes("stranger_host_proof"), true);
  const blob = JSON.stringify(result);
  assert.equal(blob.includes("ALLOWED"), false);
  assert.equal(blob.includes("BLOCKED"), false);
  assert.equal(blob.includes("CURRENT"), false);
  assert.equal(blob.includes("HISTORICAL"), false);
  assert.equal(blob.includes('"STALE"'), false);
  assert.equal(blob.includes("SUCCESS"), false);
  for (const token of BANNED_SPOKEN) {
    assert.equal(result.spoken.toLowerCase().includes(token), false);
  }
  if (result.protection_state_echo != null) {
    assert.equal(PROTECTION_STATES.includes(result.protection_state_echo), true);
  }
}

module.exports = {
  assertClosed,
};
