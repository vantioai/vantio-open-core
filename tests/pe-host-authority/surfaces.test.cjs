"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { CASES } = require("../../packages/pe-host-authority/src/cases.cjs");
const { SURFACES, DISPOSITIONS, MECHANISMS, CLAIMS, PRODUCER_CLASSIFICATION } = require("../../packages/pe-host-authority/src/catalog.cjs");
const { evaluate } = require("../../packages/pe-host-authority/src/evaluate.cjs");
const { hostFor, prove, runPureCases } = require("../../packages/pe-host-authority/src/prove.cjs");
const { matchesExact, pathBuffer } = require("../../packages/pe-host-authority/src/path-match.cjs");

const REQUIRED = [
  "files",
  "processes",
  "descendants",
  "privileges",
  "credentials",
  "namespaces",
  "containers",
  "devices",
  "persistence",
  "resource_use",
  "monitor_disablement",
  "policy_tampering",
  "evidence_tampering",
];

function subset(actual, expect) {
  for (const [key, value] of Object.entries(expect)) {
    assert.deepEqual(actual[key], value, key);
  }
}

test("every required surface is named once", () => {
  assert.deepEqual(SURFACES.map((surface) => surface.id), REQUIRED);
});

test("pure cases match the cited rule and do not widen authority", () => {
  const ids = new Set();
  for (const entry of CASES) {
    assert.equal(ids.has(entry.id), false);
    ids.add(entry.id);
    assert.equal(REQUIRED.includes(entry.surface), true);
    const host = hostFor(entry);
    const decision = evaluate(host, entry.attempt);
    subset(decision, entry.expect);
    assert.equal(decision.kernel_executed, false);
    assert.equal(decision.execution, "CONTRACT_ONLY");
    assert.equal(decision.universal_linux, false);
    assert.equal(decision.authority_widened, false);
    assert.equal(DISPOSITIONS.includes(decision.disposition), true);
  }
});

test("a 64-byte exact key does not match a longer path", () => {
  const exact = `/${"a".repeat(63)}`;
  assert.equal(Buffer.from(exact, "utf8").length, 64);
  const host = { enforce_exact: [exact] };
  assert.equal(matchesExact(host.enforce_exact, pathBuffer(exact)), true);
  assert.equal(matchesExact(host.enforce_exact, pathBuffer(`${exact}b`)), false);
});

test("unknown surface fails closed", () => {
  const host = hostFor({});
  assert.throws(() => evaluate(host, { surface: "firmware" }), /unknown surface/);
});

test("ioctl is outside the deny set", () => {
  const decision = evaluate(hostFor({}), { surface: "files", op: "ioctl", path: "/etc/crontab", uid: 1, pid: 1 });
  assert.equal(decision.disposition, "NOT_COVERED");
  assert.equal(decision.reason, "syscall_not_in_deny_set");
});

test("descendant allowlist is not a wider copy", () => {
  const host = hostFor({});
  const decision = evaluate(host, { surface: "descendants", op: "fork_inherit", trace_id: "0x0c1a" });
  assert.deepEqual(decision.child_allow_cidr_v4, host.allow_cidr_v4);
  decision.child_allow_cidr_v4.push("9.9.9.0/24");
  assert.deepEqual(host.allow_cidr_v4, ["1.1.1.0/24"]);
});

test("credential token is absent from the decision", () => {
  const token = "synthetic-not-a-secret";
  const decision = evaluate(hostFor({}), { surface: "credentials", op: "present_token", token });
  assert.equal(JSON.stringify(decision).includes(token), false);
});

test("runPureCases agrees with the case table", () => {
  const rows = runPureCases();
  assert.equal(rows.length, CASES.length);
  rows.forEach((row, index) => {
    assert.equal(row.id, CASES[index].id);
    subset(row, CASES[index].expect);
  });
});

test("proof names every mechanism and refuses a universal claim", () => {
  const report = prove();
  assert.equal(report.producer_classification, PRODUCER_CLASSIFICATION);
  assert.equal(report.council_verdict, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(report.universal_linux_control, false);
  assert.equal(report.kernel_loaded_this_force, false);
  assert.equal(report.loader_mutated_this_force, false);
  assert.equal(report.stranger_host, "NOT_RUN");
  assert.equal(report.clean_host_infrastructure, false);
  assert.deepEqual(report.claims, CLAIMS);
  assert.equal(report.host_facts.kernel_loaded_this_force, false);
  assert.equal(report.host_facts.privileged_helper_invoked, false);
  assert.equal(report.host_facts.pins_created_by_this_force, false);
  assert.notEqual(report.host_facts.euid, 0);
  assert.equal(report.host_facts.cap_eff_zero, true);
  assert.equal(report.host_facts.bpf_writable_by_this_euid, false);
  assert.equal(report.local_privilege.disposition, "NOT_COVERED");
  assert.equal(report.live_child.disposition, "INHERIT_NO_WIDEN");
  assert.equal(report.live_child.child_ppid, report.live_child.parent_pid);
  assert.equal(report.live_child.child_trace_env, null);
  assert.equal(report.live_child.child_allow_env, null);
  assert.equal(report.live_child.kernel_executed, false);
  const evidence = Object.fromEntries(report.evidence.map((row) => [row.id, row]));
  assert.equal(evidence["evidence-append-verifies"].disposition, "CHAIN_INTACT");
  assert.equal(evidence["evidence-truncate-detected"].disposition, "DETECTED");
  assert.equal(evidence["evidence-truncate-detected"].prevention, "FAIL_CLOSED_GAP");
  assert.equal(evidence["evidence-truncate-detected"].write_succeeded, true);
  assert.equal(evidence["evidence-rewrite-detected"].disposition, "DETECTED");
  assert.equal(evidence["evidence-original-remains"].disposition, "CHAIN_INTACT");
  for (const surface of report.surfaces) {
    assert.equal(surface.case_ids.length > 0, true);
    for (const mechanismId of surface.mechanisms) {
      assert.equal(typeof MECHANISMS[mechanismId].kind, "string");
    }
  }
  const blob = JSON.stringify(report);
  assert.equal(blob.includes("universal Linux control was achieved"), false);
  assert.equal(report.not_reimplemented.some((row) => row.id === "loader_attach_gating"), true);
  assert.equal(report.citations.loader_source.this_force_read, "NOT_READ");
});
