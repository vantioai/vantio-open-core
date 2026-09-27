"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const {
  PRECEDENCE,
  PROGRAM_CLASSIFICATION,
  REASONS,
  classifyListeners,
  evaluateIngress,
} = require("../../packages/pe-ingress-authority/src/index.cjs");
const { listenCase, permitCase } = require("./fixtures.cjs");
const { assertClosed } = require("./invariants.cjs");

test("registry covers every precedence reason and the shared freshness token stays UNKNOWN", () => {
  assert.equal(PROGRAM_CLASSIFICATION, "PE_INGRESS_PROGRAM_READY_FOR_COUNCIL");
  for (const reason of PRECEDENCE) {
    assert.equal(typeof REASONS[reason].spoken, "string");
    assert.equal(["HELD", "REFUSED", "WITHHELD", "OBSERVED_ONLY"].includes(REASONS[reason].authority), true);
  }
  assert.equal(REASONS.permitted_after_accept.authority, "HELD");
  assert.equal(REASONS.expected_listener_is_not_authority.authority, "OBSERVED_ONLY");
});

test("P0b envelope classes stay distinct on the pure classifier", () => {
  const classified = classifyListeners(
    [
      { local_port: 5000, local_addr: "0.0.0.0", proto: "tcp", workload: "openclaw", comm: "node" },
      { local_port: 9999, local_addr: "0.0.0.0", proto: "tcp", workload: "openclaw", comm: "nc" },
    ],
    {
      expected_listeners: [
        { port: 5000, bind: "*", protocol: "tcp", workload: "openclaw" },
        { port: 4444, bind: "*", protocol: "tcp", workload: "openclaw" },
      ],
    },
  );
  assert.deepEqual(
    classified.listeners.map((row) => row.listener_state),
    ["expected", "unexpected"],
  );
  assert.equal(classified.missing.length, 1);
  assert.equal(classified.missing[0].port, 4444);

  const empty = classifyListeners(
    [{ local_port: 5000, local_addr: "0.0.0.0", proto: "tcp", workload: "openclaw", comm: "node" }],
    { expected_listeners: [] },
  );
  assert.equal(empty.listeners[0].listener_state, "undeclared");

  const other = classifyListeners(
    [{ local_port: 9, local_addr: "127.0.0.1", proto: "tcp", workload: "hands", comm: "python3" }],
    { expected_listeners: [{ port: 5000, bind: "*", protocol: "tcp", workload: "openclaw" }] },
  );
  assert.equal(other.listeners[0].listener_state, "undeclared");
  assert.equal(other.missing.length, 0);
});

test("an expected listener is observed and is not post-accept authority", () => {
  const input = listenCase();
  const before = JSON.stringify(input);
  const result = evaluateIngress(input);
  assert.equal(JSON.stringify(input), before);
  assertClosed(result);
  assert.equal(result.authority, "OBSERVED_ONLY");
  assert.equal(result.reason, "expected_listener_is_not_authority");
  assert.equal(result.listener_state, "expected");
  assert.equal(result.grant_id, null);
  assert.equal(result.protection_state_echo, "observing");
  assert.equal(result.association_not_causation, false);
});

test("an empty envelope stays undeclared", () => {
  const input = listenCase();
  input.envelope.expected_listeners = [];
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.listener_state, "undeclared");
  assert.equal(result.reason, "undeclared_listener_is_not_authority");
  assert.equal(result.authority, "OBSERVED_ONLY");
});

test("another workload envelope does not classify this listener or grant authority", () => {
  const input = listenCase();
  input.envelope.expected_listeners = [
    { port: 5000, bind: "*", protocol: "tcp", workload: "hands", comm: "python3" },
  ];
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.listener_state, "undeclared");
  assert.equal(result.authority, "OBSERVED_ONLY");
  assert.equal(result.findings.includes("unexpected_listener"), false);
});

test("a declared listener absent from the workload bundle is missing", () => {
  const input = listenCase();
  input.listener = null;
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.listener_state, "missing");
  assert.equal(result.reason, "missing_listener_is_not_authority");
  assert.equal(result.authority, "OBSERVED_ONLY");
});

test("post-accept authority is held only when identity, integrity, policy, and health bind", () => {
  const input = permitCase();
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.authority, "HELD");
  assert.equal(result.reason, "permitted_after_accept");
  assert.equal(result.listener_state, "expected");
  assert.equal(result.identity_result, "bound");
  assert.equal(result.identity_attestation, "INSIDE_CALLER_WINDOW");
  assert.equal(result.integrity_result, "bound");
  assert.equal(result.credential_result, "absent");
  assert.equal(result.post_accept, "permitted");
  assert.equal(result.association_not_causation, true);
  assert.equal(typeof result.grant_id, "string");
  assert.equal(result.partials.includes("image_digest_binding_not_in_evidence"), true);
  assert.equal(result.partials.includes("iface_unnamed"), true);
  assert.equal(result.containment.required, false);
});

test("reachability beside a bound accept does not become the authority basis", () => {
  const input = permitCase();
  input.reachable = true;
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.authority, "HELD");
  assert.equal(result.reason, "permitted_after_accept");
  assert.equal(result.reachability_is_authority, false);
});

test("a matching image digest clears the missing-image partial", () => {
  const input = permitCase();
  input.workload.image_digest = "sha256:img";
  input.workload.image_digest_expected = "sha256:img";
  input.envelope.requires_image_binding = true;
  input.listener.iface = "lo";
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.authority, "HELD");
  assert.equal(result.partials.includes("image_digest_binding_not_in_evidence"), false);
  assert.equal(result.partials.includes("iface_unnamed"), false);
});

test("fail-closed on the packet plane is not applied and does not become a drop", () => {
  const input = permitCase();
  input.envelope.fail_mode = "fail_closed";
  const result = evaluateIngress(input);
  assertClosed(result);
  assert.equal(result.authority, "HELD");
  assert.equal(result.packet_effect, "NOT_APPLIED");
  assert.equal(result.notices.includes("fail_closed_packet_plane_not_authorized"), true);
});

test("malformed evidence withholds authority", () => {
  const result = evaluateIngress(null);
  assertClosed(result);
  assert.equal(result.reason, "evidence_malformed");
  assert.equal(result.authority, "WITHHELD");
});
