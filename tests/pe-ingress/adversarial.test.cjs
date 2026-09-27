"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { evaluateIngress, openSession } = require("../../packages/pe-ingress-authority/src/index.cjs");
const { permitCase } = require("./fixtures.cjs");
const { assertClosed } = require("./invariants.cjs");

function expect(input, reason, authority) {
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.reason, reason);
  assert.equal(result.authority, authority);
  assert.notEqual(result.authority, "HELD");
  return result;
}

test("unexpected listener refuses authority and does not claim a bind refusal", () => {
  const input = permitCase();
  input.accept = null;
  input.post_accept = { behaviors: [] };
  input.listener.local_port = 9999;
  const result = expect(input, "unexpected_listener", "REFUSED");
  assert.equal(result.listener_state, "unexpected");
  assert.equal(result.live_bind_refused, false);
});

test("wrong process refuses authority even when the port is expected", () => {
  const input = permitCase();
  input.envelope.expected_listeners[0].comm = "nc";
  input.listener.owner_pid = 999;
  input.listener.owner_comm = "nc";
  input.listener.owner_starttime = 77;
  const result = expect(input, "wrong_process", "REFUSED");
  assert.equal(result.listener_state, "expected");
  assert.equal(result.identity_result, "wrong_process");
});

test("pid reuse with a different start time is impersonation", () => {
  const input = permitCase();
  input.listener.owner_starttime = 49;
  const result = expect(input, "impersonation", "REFUSED");
  assert.equal(result.identity_result, "impersonation");
});

test("a substituted trace id is impersonation", () => {
  const input = permitCase();
  input.identity.trace_id = "0xevil";
  input.accept.accepting_trace_id = "0xevil";
  const result = expect(input, "impersonation", "REFUSED");
  assert.equal(result.identity_result, "impersonation");
});

test("an attestation outside the caller window is stale identity and freshness stays UNKNOWN", () => {
  const input = permitCase();
  input.identity.attested_at_ms = 1;
  input.identity.freshness_window_ms = 1000;
  const result = expect(input, "stale_identity", "WITHHELD");
  assert.equal(result.identity_attestation, "OUTSIDE_CALLER_WINDOW");
  assert.equal(result.freshness, "UNKNOWN");
  assert.equal(result.identity_result, "stale");
});

test("protection_stale withholds authority without emitting a shared freshness token", () => {
  const input = permitCase();
  input.health.protection_state = "protection_stale";
  const result = expect(input, "stale_identity", "WITHHELD");
  assert.equal(result.protection_state_echo, "protection_stale");
  assert.equal(result.freshness, "UNKNOWN");
});

test("a modified executable refuses authority", () => {
  const input = permitCase();
  input.workload.executable_digest = "sha256:fff";
  const result = expect(input, "modified_executable", "REFUSED");
  assert.equal(result.integrity_result, "modified_executable");
});

test("an image digest mismatch refuses authority when both digests are present", () => {
  const input = permitCase();
  input.workload.image_digest = "sha256:img-live";
  input.workload.image_digest_expected = "sha256:img-expected";
  input.envelope.requires_image_binding = true;
  const result = expect(input, "image_binding_mismatch", "REFUSED");
  assert.equal(result.integrity_result, "image_unbound");
});

test("a version mismatch refuses authority", () => {
  const input = permitCase();
  input.workload.version = "9.9.9";
  expect(input, "version_binding_mismatch", "REFUSED");
});

test("unknown executable integrity does not expand authority", () => {
  const input = permitCase();
  input.workload.executable_digest = null;
  input.workload.executable_digest_expected = null;
  const result = expect(input, "integrity_unknown", "WITHHELD");
  assert.equal(result.integrity_result, "unknown");
});

test("a valid credential bound to another workload refuses authority while integrity stays bound", () => {
  const input = permitCase();
  input.identity.credential = {
    presented: true,
    valid: true,
    bound_workload_id: "wl-other",
  };
  const result = expect(input, "valid_credential_wrong_workload", "REFUSED");
  assert.equal(result.credential_result, "valid_wrong_workload");
  assert.equal(result.integrity_result, "bound");
  assert.equal(result.credential_is_integrity, false);
});

test("a credential claim is not integrity even when the credential matches this workload", () => {
  const input = permitCase();
  input.authority_claim = "credential";
  input.identity.credential = {
    presented: true,
    valid: true,
    bound_workload_id: "wl-agent",
  };
  const result = expect(input, "credential_is_not_integrity", "WITHHELD");
  assert.equal(result.credential_result, "not_integrity");
  assert.equal(result.integrity_result, "bound");
});

test("a valid credential with unknown integrity does not grant authority", () => {
  const input = permitCase();
  input.workload.executable_digest = null;
  input.identity.credential = {
    presented: true,
    valid: true,
    bound_workload_id: "wl-agent",
  };
  const result = expect(input, "integrity_unknown", "WITHHELD");
  assert.equal(result.findings.includes("credential_is_not_integrity"), true);
  assert.equal(result.credential_is_integrity, false);
});

test("a reachability claim withholds authority", () => {
  const input = permitCase();
  input.authority_claim = "reachability";
  input.reachable = true;
  const result = expect(input, "reachability_is_not_authority", "WITHHELD");
  assert.equal(result.reachability_is_authority, false);
});

test("unauthorized post-accept behavior is denied and containment stays a decision", () => {
  const input = permitCase();
  input.post_accept.behaviors = [
    {
      kind: "cred_path",
      path: "/root/.ssh/id_rsa",
      authorized: false,
      trace_id: "0xtrace",
      cgroup_id: "cg-1",
      pid: 100,
      starttime: 50,
    },
  ];
  const result = expect(input, "post_accept_denied", "REFUSED");
  assert.equal(result.post_accept, "denied");
  assert.equal(result.containment.required, true);
  assert.equal(result.containment.effect, "DECISION_RECORDED_ONLY");
  assert.equal(JSON.stringify(result).includes("id_rsa"), false);
});

test("a child that leaves the enrolled cgroup is an escape even when the row says authorized", () => {
  const input = permitCase();
  input.post_accept.behaviors.push({
    kind: "exec",
    path: "/usr/bin/curl",
    authorized: true,
    trace_id: "0xtrace",
    cgroup_id: "cg-other",
    pid: 200,
    starttime: 60,
  });
  const result = expect(input, "child_process_escape", "REFUSED");
  assert.equal(result.post_accept, "child_escape");
  assert.equal(result.containment.required, true);
  assert.equal(result.containment.cgroup_freeze_applied, false);
  assert.equal(JSON.stringify(result).includes("curl"), false);
});

test("a later behavior on another trace stays unjoined", () => {
  const input = permitCase();
  input.post_accept.behaviors = [
    {
      kind: "exec",
      path: "/usr/bin/curl",
      authorized: true,
      trace_id: "0xother",
      cgroup_id: "cg-1",
      pid: 200,
      starttime: 60,
    },
  ];
  const result = expect(input, "post_accept_unjoined", "WITHHELD");
  assert.equal(result.post_accept, "unjoined");
  assert.equal(result.association_not_causation, true);
});

test("an accept by a different process is not assigned to the enrolled workload", () => {
  const input = permitCase();
  input.accept.accepting_pid = 250;
  input.accept.accepting_starttime = 80;
  const result = expect(input, "unattributed_accept", "WITHHELD");
  assert.equal(result.identity_result, "unbound");
});

test("a candidate policy sha that differs from the applied sha is stale", () => {
  const input = permitCase();
  input.envelope.candidate_sha = "sha-candidate";
  expect(input, "stale_policy", "WITHHELD");
});

test("a missing policy version is stale and does not invent an unexpected-listener alarm", () => {
  const input = permitCase();
  input.envelope.policy_version = "missing";
  input.envelope.expected_listeners = [];
  const result = expect(input, "stale_policy", "WITHHELD");
  assert.equal(result.listener_state, "undeclared");
  assert.equal(result.findings.includes("unexpected_listener"), false);
});

test("loader, evidence, and netns gaps withhold authority", () => {
  for (const [field, coverage] of [
    ["loader_up", "seeing"],
    ["evidence_writable", "seeing"],
    ["netns_readable", "seeing"],
    ["trace_map_available", "seeing"],
  ]) {
    const input = permitCase();
    input.health[field] = false;
    expect(input, "health_or_evidence_unavailable", "WITHHELD");
  }
  const unseen = permitCase();
  unseen.health.coverage = "cannot_see";
  expect(unseen, "health_or_evidence_unavailable", "WITHHELD");
  const degraded = permitCase();
  degraded.health.coverage = "degraded";
  expect(degraded, "health_degraded", "WITHHELD");
});

test("honest idle contradicts an accepted connection", () => {
  const input = permitCase();
  input.health.coverage = "honest_idle";
  expect(input, "health_evidence_contradiction", "WITHHELD");
});

test("cgroup id 0 and a missing enrollment withhold authority", () => {
  const zero = permitCase();
  zero.workload.cgroup_id = 0;
  expect(zero, "unattributable_cgroup", "WITHHELD");
  const none = permitCase();
  delete none.workload.enroll_id;
  expect(none, "not_enrolled", "WITHHELD");
});

test("unix, udp peer, io_uring, and docker dns stay unsupported", () => {
  const unix = permitCase();
  unix.listener.proto = "unix";
  const unixResult = expect(unix, "unsupported_path", "WITHHELD");
  assert.equal(unixResult.unsupported.includes("unix_domain"), true);

  const udp = permitCase();
  udp.listener.proto = "udp";
  udp.accept.proto = "udp";
  const udpResult = expect(udp, "unsupported_path", "WITHHELD");
  assert.equal(udpResult.unsupported.includes("udp_peer_attribution"), true);

  const uring = permitCase();
  uring.accept.mechanism = "io_uring";
  const uringResult = expect(uring, "unsupported_path", "WITHHELD");
  assert.equal(uringResult.unsupported.includes("io_uring_accept"), true);

  const dns = permitCase();
  dns.listener.local_addr = "127.0.0.11";
  const dnsResult = expect(dns, "unsupported_path", "WITHHELD");
  assert.equal(dnsResult.unsupported.includes("docker_embedded_dns"), true);
});

test("a request to mutate the live loader is refused and the loader flag stays false", () => {
  const input = permitCase();
  input.mutate_live_loader = true;
  const result = expect(input, "live_loader_mutation_refused", "REFUSED");
  assert.equal(result.live_loader_mutated, false);
});

test("an omitted caller window does not become a fresh identity", () => {
  const input = permitCase();
  delete input.identity.freshness_window_ms;
  const result = expect(input, "identity_unknown", "WITHHELD");
  assert.equal(result.identity_attestation, "WINDOW_ABSENT");
  assert.equal(result.freshness, "UNKNOWN");
});

test("an accept does not hold on an empty envelope, another workload, or a missing listener", () => {
  const empty = permitCase();
  empty.envelope.expected_listeners = [];
  const emptyResult = expect(empty, "undeclared_listener_is_not_authority", "OBSERVED_ONLY");
  assert.equal(emptyResult.listener_state, "undeclared");
  assert.equal(emptyResult.grant_id, null);

  const other = permitCase();
  other.envelope.expected_listeners = [
    { port: 5000, bind: "*", protocol: "tcp", workload: "hands", comm: "python3" },
  ];
  const otherResult = expect(other, "undeclared_listener_is_not_authority", "OBSERVED_ONLY");
  assert.equal(otherResult.listener_state, "undeclared");
  assert.equal(otherResult.findings.includes("unexpected_listener"), false);
  assert.equal(otherResult.grant_id, null);

  const missing = permitCase();
  missing.listener = null;
  const missingResult = expect(missing, "missing_listener_is_not_authority", "OBSERVED_ONLY");
  assert.equal(missingResult.listener_state, "missing");
  assert.equal(missingResult.grant_id, null);
});

test("coverage partial, bogus, or SEEING does not hold, and coverage_unknown echo does not hold", () => {
  for (const coverage of ["partial", "bogus", "SEEING"]) {
    const input = permitCase();
    input.health.coverage = coverage;
    const result = expect(input, "health_or_evidence_unavailable", "WITHHELD");
    assert.equal(result.listener_state, "expected");
    assert.equal(result.grant_id, null);
  }
  const unknown = permitCase();
  unknown.health.coverage = "seeing";
  unknown.health.protection_state = "coverage_unknown";
  const echoed = expect(unknown, "health_or_evidence_unavailable", "WITHHELD");
  assert.equal(echoed.protection_state_echo, "coverage_unknown");
  assert.equal(echoed.grant_id, null);
});

test("a missing or empty accept trace does not hold, and a different accept trace is impersonation", () => {
  const absent = permitCase();
  delete absent.accept.accepting_trace_id;
  const absentResult = expect(absent, "identity_unknown", "WITHHELD");
  assert.equal(absentResult.grant_id, null);

  const empty = permitCase();
  empty.accept.accepting_trace_id = "";
  expect(empty, "identity_unknown", "WITHHELD");

  const mismatched = permitCase();
  mismatched.accept.accepting_trace_id = "0xother";
  const mismatchedResult = expect(mismatched, "impersonation", "REFUSED");
  assert.equal(mismatchedResult.identity_result, "impersonation");
});

test("authorized later behavior without an enrolled cgroup does not hold", () => {
  const absent = permitCase();
  delete absent.post_accept.behaviors[0].cgroup_id;
  assert.equal(absent.post_accept.behaviors[0].authorized, true);
  const absentResult = expect(absent, "post_accept_unjoined", "WITHHELD");
  assert.equal(absentResult.post_accept, "unjoined");
  assert.equal(absentResult.grant_id, null);

  const nulled = permitCase();
  nulled.post_accept.behaviors[0].cgroup_id = null;
  const nulledResult = expect(nulled, "post_accept_unjoined", "WITHHELD");
  assert.equal(nulledResult.post_accept, "unjoined");
});

test("an accept on another port does not join the expected listener", () => {
  const input = permitCase();
  input.accept.local_port = 9999;
  const result = expect(input, "unexpected_listener", "REFUSED");
  assert.equal(result.listener_state, "expected");
  assert.equal(result.live_bind_refused, false);
  assert.equal(result.findings.includes("permitted_after_accept"), false);
  assert.equal(result.grant_id, null);
});

test("child_process_escape still records decision-only containment when it is not primary", () => {
  const unexpected = permitCase();
  unexpected.listener.local_port = 9999;
  unexpected.post_accept.behaviors.push({
    kind: "cgroup_escape",
    authorized: true,
    trace_id: "0xtrace",
    cgroup_id: "cg-1",
    pid: 200,
    starttime: 60,
  });
  const shadowed = expect(unexpected, "unexpected_listener", "REFUSED");
  assert.equal(shadowed.listener_state, "unexpected");
  assert.equal(shadowed.findings.includes("child_process_escape"), true);
  assert.equal(shadowed.post_accept, "child_escape");
  assert.equal(shadowed.containment.required, true);
  assert.equal(shadowed.containment.effect, "DECISION_RECORDED_ONLY");
  assert.equal(shadowed.containment.executor, "NOT_WIRED_IN_LIVE_LOADER");
  assert.equal(shadowed.containment.cgroup_freeze_applied, false);
  assert.equal(shadowed.containment.connection_isolation, "NOT_PRESENT");
  assert.equal(shadowed.live_bind_refused, false);

  const session = openSession({ boot_id: "boot-0", last_known_sha: "sha-applied", policy_version: "v3" });
  const held = evaluateIngress(permitCase(), session);
  assert.equal(held.authority, "HELD");
  const modified = permitCase();
  modified.workload.executable_digest = "sha256:fff";
  modified.post_accept.behaviors.push({
    kind: "exec",
    authorized: true,
    trace_id: "0xtrace",
    cgroup_id: "cg-other",
    pid: 200,
    starttime: 60,
  });
  const refused = evaluateIngress(modified, session);
  assertClosed(refused);
  assert.equal(refused.reason, "modified_executable");
  assert.equal(refused.findings.includes("child_process_escape"), true);
  assert.equal(refused.containment.required, true);
  assert.equal(refused.containment.effect, "DECISION_RECORDED_ONLY");
  assert.equal(refused.containment.cgroup_freeze_applied, false);
  const again = evaluateIngress(permitCase(), session);
  assertClosed(again);
  assert.equal(again.reason, "revoked");
  assert.equal(again.authority, "REFUSED");

  const denied = permitCase();
  denied.workload.executable_digest = "sha256:fff";
  denied.post_accept.behaviors[0].authorized = false;
  const denyShadow = expect(denied, "modified_executable", "REFUSED");
  assert.equal(denyShadow.findings.includes("post_accept_denied"), true);
  assert.equal(denyShadow.containment.required, true);
  assert.equal(denyShadow.containment.effect, "DECISION_RECORDED_ONLY");
  assert.equal(denyShadow.containment.executor, "NOT_WIRED_IN_LIVE_LOADER");
  assert.equal(denyShadow.containment.cgroup_freeze_applied, false);
});
