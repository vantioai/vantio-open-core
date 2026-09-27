"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  evaluateIngress,
  lookupGrant,
  openSession,
  restartSession,
  revokeActive,
  rollbackSession,
} = require("../../packages/pe-ingress-authority/src/index.cjs");
const { permitCase } = require("./fixtures.cjs");
const { assertClosed } = require("./invariants.cjs");

function hold(session) {
  const result = evaluateIngress(permitCase(), session);
  assertClosed(result);
  assert.equal(result.authority, "HELD");
  assert.equal(typeof result.grant_id, "string");
  return result;
}

test("revoke while active drops the grant and does not freeze or isolate", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied", policy_version: "v3" });
  const first = hold(session);
  assert.ok(lookupGrant(session, first.grant_id));
  const revoked = revokeActive(session, first.grant_id);
  assertClosed(revoked);
  assert.equal(revoked.authority, "REFUSED");
  assert.equal(revoked.reason, "revoked");
  assert.equal(revoked.containment.required, false);
  assert.equal(revoked.containment.cgroup_freeze_applied, false);
  assert.equal(revoked.live_loader_mutated, false);
  assert.equal(lookupGrant(session, first.grant_id), null);

  const again = evaluateIngress(permitCase(), session);
  assertClosed(again);
  assert.equal(again.authority, "REFUSED");
  assert.equal(again.reason, "revoked");
  assert.equal(again.grant_id, null);
});

test("revoke of an unknown grant does not invent one", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied" });
  const result = revokeActive(session, "missing-grant");
  assertClosed(result);
  assert.equal(result.reason, "grant_not_carried");
  assert.equal(result.authority, "REFUSED");
  assert.equal(session.grants.size, 0);
});

test("restart drops grants, reloads last-known policy, and a replay does not carry the old grant", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied", policy_version: "v3" });
  const first = hold(session);
  const restarted = restartSession(session, { boot_id: "boot-1" });
  assertClosed(restarted);
  assert.equal(restarted.authority, "OBSERVED_ONLY");
  assert.equal(restarted.reason, "policy_reloaded_not_granted");
  assert.equal(restarted.grants_carried, 0);
  assert.equal(restarted.policy.sha, "sha-applied");
  assert.equal(restarted.ingress_protected_claim, false);
  assert.equal(lookupGrant(session, first.grant_id), null);

  const replay = evaluateIngress({ ...permitCase(), replay_grant_id: first.grant_id }, session);
  assertClosed(replay);
  assert.equal(replay.reason, "grant_not_carried");
  assert.equal(replay.authority, "REFUSED");

  const fresh = hold(session);
  assert.notEqual(fresh.grant_id, first.grant_id);
  assert.equal(fresh.boot_id, "boot-1");
});

test("restart without a last-known policy names recovery and does not silently grant", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: null, policy_version: "v3" });
  hold(session);
  const restarted = restartSession(session, { boot_id: "boot-2" });
  assertClosed(restarted);
  assert.equal(restarted.reason, "recovery_required");
  assert.equal(restarted.authority, "WITHHELD");
  const again = evaluateIngress(permitCase(), session);
  assertClosed(again);
  assert.equal(again.reason, "recovery_required");
  assert.equal(again.authority, "WITHHELD");
  assert.equal(again.ingress_protected_claim, false);
});

test("rollback mints a new version id and the previous grant does not survive", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied", policy_version: "v3" });
  const first = hold(session);
  const rolled = rollbackSession(session);
  assertClosed(rolled);
  assert.equal(rolled.reason, "rolled_back_not_granted");
  assert.equal(rolled.authority, "OBSERVED_ONLY");
  assert.equal(rolled.policy.sha, "sha-applied");
  assert.equal(rolled.policy.version, "rollback:sha-applied:1");
  assert.notEqual(rolled.policy.version, "v3");
  assert.equal(lookupGrant(session, first.grant_id), null);

  const stale = evaluateIngress(permitCase(), session);
  assertClosed(stale);
  assert.equal(stale.reason, "stale_policy");
  assert.equal(stale.authority, "WITHHELD");

  const restored = permitCase();
  restored.envelope.policy_version = rolled.policy.version;
  restored.envelope.policy_sha = rolled.policy.sha;
  restored.envelope.applied_sha = rolled.policy.sha;
  restored.envelope.candidate_sha = rolled.policy.sha;
  const again = evaluateIngress(restored, session);
  assertClosed(again);
  assert.equal(again.authority, "HELD");
  assert.notEqual(again.grant_id, first.grant_id);
  assert.equal(again.ingress_protected_claim, false);
});

test("rollback without a last-known policy withholds recovery", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: null });
  const rolled = rollbackSession(session);
  assertClosed(rolled);
  assert.equal(rolled.reason, "recovery_required");
  assert.equal(rolled.authority, "WITHHELD");
});

test("child escape revokes the key until an explicit restart", () => {
  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied", policy_version: "v3" });
  const first = hold(session);
  const escaped = permitCase();
  escaped.post_accept.behaviors.push({
    kind: "exec",
    path: "/bin/true",
    authorized: true,
    trace_id: "0xtrace",
    cgroup_id: "cg-other",
    pid: 200,
    starttime: 60,
  });
  const stopped = evaluateIngress(escaped, session);
  assertClosed(stopped);
  assert.equal(stopped.reason, "child_process_escape");
  assert.equal(lookupGrant(session, first.grant_id), null);
  assert.equal(session.events.some((event) => event.op === "authority_stopped"), true);

  const clean = evaluateIngress(permitCase(), session);
  assertClosed(clean);
  assert.equal(clean.reason, "revoked");
  assert.equal(clean.authority, "REFUSED");

  const restarted = restartSession(session, { boot_id: "boot-3" });
  assert.equal(restarted.reason, "policy_reloaded_not_granted");
  const restored = hold(session);
  assert.notEqual(restored.grant_id, first.grant_id);
});
