"use strict";

const AUDIENCE = "INTERNAL_RESTRICTED";
const PROGRAM = "PE_INGRESS_AUTHORITY";
const PROGRAM_CLASSIFICATION = "PE_INGRESS_PROGRAM_READY_FOR_COUNCIL";
const PACKET_PLANE = "OBSERVE_ONLY";
const EVIDENCE_DECISION = "observed";
const FRESHNESS = "UNKNOWN";
const FRESHNESS_RULE = "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN";

const PROTECTION_STATES = Object.freeze([
  "protected",
  "observing",
  "not_enrolled",
  "protection_stale",
  "policy_stale",
  "degraded",
  "quarantined",
  "recovery_required",
  "coverage_unknown",
]);

const PROTECTION_STATE_SET = new Set(PROTECTION_STATES);

const BANNED_SPOKEN = Object.freeze([
  "absolute control",
  "unbreakable",
  "stops hackers",
  "protects from ingress attackers",
  "generic firewall",
  "worm storage",
  "spanner worm",
]);

const NOT_PRESENT = Object.freeze([
  "inbound_packet_drop",
  "cgroup_skb_ingress",
  "tc_ingress_classifier",
  "connection_isolation",
  "live_cgroup_freeze",
  "live_quarantine_executor",
  "idp_revoke",
  "full_inbound_tree_walk",
  "stranger_host_proof",
  "off_host_durable_ledger",
]);

const REASONS = Object.freeze({
  evidence_malformed: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The evidence bundle is not a usable object.",
  },
  live_loader_mutation_refused: {
    authority: "REFUSED",
    spoken: "The request to change the live loader is refused. This session records a decision only.",
  },
  unsupported_path: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The ingress path is unsupported on the cited engine surface.",
  },
  health_or_evidence_unavailable: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. Health or evidence is unavailable.",
  },
  health_degraded: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. Ingress health is degraded.",
  },
  health_evidence_contradiction: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The health coverage contradicts the ingress evidence.",
  },
  not_enrolled: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The workload is not enrolled.",
  },
  unattributable_cgroup: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The cgroup is unattributable.",
  },
  already_quarantined: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The supplied protection state is quarantined.",
  },
  recovery_required: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. No last-known listener policy is available to restore.",
  },
  stale_policy: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The listener policy is stale against the applied policy.",
  },
  impersonation: {
    authority: "REFUSED",
    spoken: "Authority is refused. The presented process identity does not bind to the enrolled workload.",
  },
  wrong_process: {
    authority: "REFUSED",
    spoken: "Authority is refused. The listener owner is a different process from the enrolled workload.",
  },
  unattributed_accept: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The accepting process is not the enrolled workload identity.",
  },
  stale_identity: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The identity attestation is outside the caller-supplied window.",
  },
  identity_unknown: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. Workload identity is unknown.",
  },
  modified_executable: {
    authority: "REFUSED",
    spoken: "Authority is refused. The executable digest differs from the expected digest.",
  },
  image_binding_mismatch: {
    authority: "REFUSED",
    spoken: "Authority is refused. The image digest differs from the expected image digest.",
  },
  version_binding_mismatch: {
    authority: "REFUSED",
    spoken: "Authority is refused. The workload version differs from the expected version.",
  },
  integrity_unknown: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. Workload integrity is unknown.",
  },
  valid_credential_wrong_workload: {
    authority: "REFUSED",
    spoken: "Authority is refused. The valid credential is bound to a different workload.",
  },
  credential_invalid: {
    authority: "REFUSED",
    spoken: "Authority is refused. The presented credential does not validate.",
  },
  credential_is_not_integrity: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. A presented credential is not workload integrity.",
  },
  unexpected_listener: {
    authority: "REFUSED",
    spoken: "Authority is refused. The listener is unexpected for this workload policy, or the accept does not join the expected listener. The live bind path is unchanged.",
  },
  child_process_escape: {
    authority: "REFUSED",
    spoken: "Authority is refused. A descendant left the enrolled cgroup. Containment is recorded as a decision. No live executor ran.",
  },
  post_accept_denied: {
    authority: "REFUSED",
    spoken: "Authority is refused. Post-accept behavior is outside the authorized set. Containment is recorded as a decision.",
  },
  post_accept_unjoined: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. The later behavior does not join the accepted connection.",
  },
  revoked: {
    authority: "REFUSED",
    spoken: "The active authority grant is revoked in this session.",
  },
  grant_not_carried: {
    authority: "REFUSED",
    spoken: "The prior grant is not active in this session.",
  },
  reachability_is_not_authority: {
    authority: "WITHHELD",
    spoken: "Authority stays withheld. Reachability is not workload authority.",
  },
  expected_listener_is_not_authority: {
    authority: "OBSERVED_ONLY",
    spoken: "The listener matches the declared envelope. A match is not post-accept authority.",
  },
  undeclared_listener_is_not_authority: {
    authority: "OBSERVED_ONLY",
    spoken: "The listener has no declared row for this workload. That fact is not an authority grant.",
  },
  missing_listener_is_not_authority: {
    authority: "OBSERVED_ONLY",
    spoken: "A declared listener is absent from the supplied evidence. Absence is not an authority grant.",
  },
  permitted_after_accept: {
    authority: "HELD",
    spoken: "Post-accept authority is held on the enrolled identity, executable binding, current listener policy, and in-window attestation.",
  },
  policy_reloaded_not_granted: {
    authority: "OBSERVED_ONLY",
    spoken: "The session restarted onto the last-known listener policy. Prior grants were not carried.",
  },
  rolled_back_not_granted: {
    authority: "OBSERVED_ONLY",
    spoken: "The listener policy rolled back to the last-known digest under a new version id. Prior grants were not carried.",
  },
});

const PRECEDENCE = Object.freeze([
  "evidence_malformed",
  "live_loader_mutation_refused",
  "unsupported_path",
  "health_or_evidence_unavailable",
  "health_degraded",
  "health_evidence_contradiction",
  "not_enrolled",
  "unattributable_cgroup",
  "already_quarantined",
  "recovery_required",
  "stale_policy",
  "impersonation",
  "wrong_process",
  "unattributed_accept",
  "stale_identity",
  "identity_unknown",
  "modified_executable",
  "image_binding_mismatch",
  "version_binding_mismatch",
  "integrity_unknown",
  "valid_credential_wrong_workload",
  "credential_invalid",
  "credential_is_not_integrity",
  "unexpected_listener",
  "child_process_escape",
  "post_accept_denied",
  "post_accept_unjoined",
  "revoked",
  "grant_not_carried",
  "reachability_is_not_authority",
  "expected_listener_is_not_authority",
  "undeclared_listener_is_not_authority",
  "missing_listener_is_not_authority",
  "permitted_after_accept",
]);

for (const reason of PRECEDENCE) {
  if (!Object.prototype.hasOwnProperty.call(REASONS, reason)) {
    throw new Error(`precedence reason missing from registry: ${reason}`);
  }
}

function authorityFor(reason) {
  const row = REASONS[reason];
  if (!row) {
    throw new Error(`unknown ingress reason: ${reason}`);
  }
  return row.authority;
}

function spokenFor(reason) {
  const row = REASONS[reason];
  if (!row) {
    throw new Error(`unknown ingress reason: ${reason}`);
  }
  return row.spoken;
}

function spokenAllowed(text) {
  const blob = String(text).toLowerCase();
  return !BANNED_SPOKEN.some((token) => blob.includes(token));
}

module.exports = {
  AUDIENCE,
  BANNED_SPOKEN,
  EVIDENCE_DECISION,
  FRESHNESS,
  FRESHNESS_RULE,
  NOT_PRESENT,
  PACKET_PLANE,
  PRECEDENCE,
  PROGRAM,
  PROGRAM_CLASSIFICATION,
  PROTECTION_STATES,
  PROTECTION_STATE_SET,
  REASONS,
  authorityFor,
  spokenAllowed,
  spokenFor,
};
