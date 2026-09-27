"use strict";

const { containmentFor, finishResult } = require("./result.cjs");

function openSession(options = {}) {
  const lastKnown = options.last_known_sha == null ? null : String(options.last_known_sha);
  return {
    boot_id: options.boot_id || "boot-0",
    last_known_sha: lastKnown,
    applied_sha: options.applied_sha == null ? lastKnown : options.applied_sha,
    policy_version: options.policy_version == null ? null : String(options.policy_version),
    epoch: 0,
    grants: new Map(),
    dead: new Set(),
    revoked_keys: new Set(),
    policy_unrecoverable: false,
    rollback_seq: 0,
    events: [],
  };
}

function lookupGrant(session, grantId) {
  if (!session || !session.grants.has(grantId)) return null;
  const grant = session.grants.get(grantId);
  return {
    id: grant.id,
    key: grant.key,
    boot_id: grant.boot_id,
    policy_sha: grant.policy_sha,
    policy_version: grant.policy_version,
  };
}

function dropGrants(session) {
  for (const id of session.grants.keys()) session.dead.add(id);
  session.grants.clear();
  session.revoked_keys.clear();
}

function lifecycleResult(session, reason, policy) {
  return finishResult({
    reason,
    findings: [reason],
    listener_state: "none",
    identity_result: "unknown",
    identity_attestation: "WINDOW_ABSENT",
    integrity_result: "unknown",
    credential_result: "absent",
    post_accept: "not_applicable",
    protection_state_echo: null,
    unsupported: [],
    partials: [],
    notices: [],
    policy,
    grant_id: null,
    grants_carried: 0,
    boot_id: session.boot_id,
    association_not_causation: false,
    containment: containmentFor(reason),
  });
}

function revokeActive(session, grantId) {
  if (!session || !session.grants.has(grantId)) {
    return lifecycleResult(session || openSession(), "grant_not_carried", {
      present: false,
      version: null,
      sha: null,
      stale: true,
      fail_mode_effect: "NOT_APPLIED",
    });
  }
  const grant = session.grants.get(grantId);
  session.grants.delete(grantId);
  session.dead.add(grantId);
  session.revoked_keys.add(grant.key);
  session.events.push({ op: "revoke", grant_id: grantId, key: grant.key });
  const result = lifecycleResult(session, "revoked", {
    present: true,
    version: session.policy_version,
    sha: session.applied_sha,
    stale: false,
    fail_mode_effect: "NOT_APPLIED",
  });
  result.grant_id = grantId;
  return result;
}

function restartSession(session, options = {}) {
  dropGrants(session);
  session.epoch += 1;
  session.boot_id = options.boot_id || `boot-restart-${session.epoch}`;
  if (session.last_known_sha) {
    session.applied_sha = session.last_known_sha;
    session.policy_unrecoverable = false;
  } else {
    session.applied_sha = null;
    session.policy_version = null;
    session.policy_unrecoverable = true;
  }
  const reason = session.policy_unrecoverable ? "recovery_required" : "policy_reloaded_not_granted";
  session.events.push({ op: "restart", boot_id: session.boot_id, reason });
  return lifecycleResult(session, reason, {
    present: !session.policy_unrecoverable,
    version: session.policy_version,
    sha: session.applied_sha,
    stale: session.policy_unrecoverable,
    fail_mode_effect: "NOT_APPLIED",
  });
}

function rollbackSession(session) {
  dropGrants(session);
  session.epoch += 1;
  if (!session.last_known_sha) {
    session.applied_sha = null;
    session.policy_version = null;
    session.policy_unrecoverable = true;
    session.events.push({ op: "rollback", reason: "recovery_required" });
    return lifecycleResult(session, "recovery_required", {
      present: false,
      version: null,
      sha: null,
      stale: true,
      fail_mode_effect: "NOT_APPLIED",
    });
  }
  session.rollback_seq += 1;
  session.applied_sha = session.last_known_sha;
  session.policy_version = `rollback:${session.last_known_sha}:${session.rollback_seq}`;
  session.policy_unrecoverable = false;
  session.events.push({
    op: "rollback",
    policy_version: session.policy_version,
    policy_sha: session.applied_sha,
  });
  return lifecycleResult(session, "rolled_back_not_granted", {
    present: true,
    version: session.policy_version,
    sha: session.applied_sha,
    stale: false,
    fail_mode_effect: "NOT_APPLIED",
  });
}

module.exports = {
  lookupGrant,
  openSession,
  restartSession,
  revokeActive,
  rollbackSession,
};
