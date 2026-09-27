"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const runtime = require("../../internal/pe-integrated-runtime/src/index.cjs");
const { permitCase } = require("../pe-ingress/fixtures.cjs");
const { attempt, hostObservation, policy } = require("../pe-egress/fixture.cjs");
const { baseInput, OPTIONS } = require("../shared-health-runtime/helpers.cjs");
const seq = require("../pe-sequential-authority/fixture.cjs");

function must(result) {
  assert.equal(result.ok, true, `${result.code} ${JSON.stringify(result.problems)}`);
  return result;
}

test("attachment flags on the request are refused before a child runs", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const refused = runtime.integrate(rt, {
    op: "host_contract",
    load_ebpf: true,
    attempt: { surface: "files", op: "open", path: "/etc/crontab", uid: 1, pid: 3 },
  });
  assert.equal(refused.ok, false);
  assert.equal(refused.code, "ATTACHMENT_REFUSED");
  assert.equal(refused.active_protection, false);
  assert.equal(refused.ebpf_loaded, false);
  assert.equal(rt.ebpf_loaded, false);
  assert.equal(rt.host_attachment, false);
  const view = runtime.snapshot(rt);
  assert.equal(view.ebpf_loaded, false);
  assert.equal(view.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
});

test("the honesty gate rejects a smuggled kernel execution flag", () => {
  assert.deepEqual(runtime.sealChild({ kernel_executed: true, execution: "CONTRACT_ONLY" }), ["kernel_executed"]);
  assert.deepEqual(runtime.sealChild({ host_attachment: "ATTACHED" }), ["host_attachment"]);
  assert.deepEqual(runtime.sealChild({ packet_effect: "DROP" }), ["packet_effect"]);
  assert.deepEqual(runtime.sealChild({ enforcement: "HOST" }), ["enforcement"]);
  assert.deepEqual(runtime.sealChild({
    kernel_executed: false,
    host_attachment: false,
    execution: "CONTRACT_ONLY",
    enforcement: "EVALUATE_ONLY",
    packet_effect: "NOT_APPLIED",
  }), []);
});

test("process up and HTTP 200 do not become protection", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const record = must(runtime.integrate(rt, {
    op: "health",
    input: baseInput({ signals: { process_up: true, http_status: 200 } }),
    options: OPTIONS,
  }));
  assert.equal(record.quote.state, "ENFORCEMENT_UNKNOWN");
  assert.equal(record.planes.OBSERVATION.status, "ENFORCEMENT_UNKNOWN");
  assert.equal(record.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");
  assert.equal(record.quote.green, false);
  assert.equal(record.active_protection, false);
});

test("an enforcement gap and a host-execution claim stay gaps", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const gap = must(runtime.integrate(rt, {
    op: "egress",
    input: { policy: policy(), path: { id: "app_raw_syscall" }, attempt: attempt() },
  }));
  assert.equal(gap.quote.result, "ENFORCEMENT_GAP");
  assert.equal(gap.planes.APPLICATION_ENFORCEMENT.status, "GAP");
  assert.equal(gap.planes.APPLICATION_ENFORCEMENT.applied, false);
  assert.equal(gap.active_protection, false);

  const claimed = must(runtime.integrate(rt, {
    op: "egress",
    input: {
      policy: policy(),
      path: { id: "host_tc_enrolled" },
      attempt: attempt({
        host_observation: hostObservation({ this_force_executed: true, dropped: true }),
      }),
    },
  }));
  assert.equal(claimed.quote.result, "UNKNOWN");
  assert.equal(claimed.quote.reason, "host_execution_claim_rejected");
  assert.equal(claimed.quote.this_force_executed_host, false);
  assert.equal(claimed.planes.HOST_ENFORCEMENT.kernel_executed, false);
});

test("containment for a child escape is a decision and does not freeze a cgroup", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
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
  const escaped = must(runtime.integrate(rt, { op: "ingress", input }));
  assert.equal(escaped.quote.reason, "child_process_escape");
  assert.equal(escaped.planes.CONTAINMENT.status, "DECISION_RECORDED_ONLY");
  assert.equal(escaped.planes.CONTAINMENT.execution, "NOT_PERFORMED");
  assert.equal(escaped.quote.cgroup_freeze_applied, false);
  assert.equal(escaped.planes.HOST_ENFORCEMENT.applied, false);
  assert.equal(JSON.stringify(escaped.quote).includes("curl"), false);
});

test("evidence tampering is not proved from this runtime", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const refused = runtime.integrate(rt, {
    op: "host_contract",
    attempt: { surface: "evidence_tampering", op: "truncate" },
  });
  assert.equal(refused.ok, false);
  assert.equal(refused.code, "NOT_WIRED");
  assert.equal(refused.child, null);
  assert.equal(refused.active_protection, false);
});

test("a loader mutation request stays a refused decision", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const input = permitCase();
  input.mutate_live_loader = true;
  const result = must(runtime.integrate(rt, { op: "ingress", input }));
  assert.equal(result.quote.reason, "live_loader_mutation_refused");
  assert.equal(result.quote.live_loader_mutated, false);
  assert.equal(result.planes.DECISION.status, "REFUSED");
  assert.equal(result.planes.HOST_ENFORCEMENT.applied, false);
});

test("consensus and a performed uninstall flag do not create authority", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const consensus = must(runtime.integrate(rt, {
    op: "sequential",
    input: {
      envelope: seq.root(),
      catalog: seq.catalogOf(seq.root()),
      ledger: seq.api.emptyLedger(),
      step: seq.step({ authority_source: "consensus" }),
      now: 10,
    },
  }));
  assert.equal(consensus.quote.invariant, "CONSENSUS_IS_NOT_AUTHORIZATION");
  assert.equal(consensus.planes.HOST_ENFORCEMENT.status, "NOT_APPLIED");

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "w3-pe-"));
  const file = path.join(dir, "keep.txt");
  fs.writeFileSync(file, "stay");
  const refused = runtime.integrate(rt, {
    op: "uninstall",
    input: { performed: true, delete: true, path: file },
  });
  assert.equal(refused.ok, false);
  assert.equal(refused.code, "NOT_PERFORMED");
  assert.equal(fs.readFileSync(file, "utf8"), "stay");
  assert.equal(runtime.snapshot(rt).uninstall.performed, false);
  fs.rmSync(dir, { recursive: true });
});

test("a policy version cannot be marked applied", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const refused = runtime.integrate(rt, {
    op: "policy_version",
    input: { version_id: "pol-2", applied_to_host: true },
  });
  assert.equal(refused.ok, false);
  assert.equal(refused.code, "ATTACHMENT_REFUSED");
  assert.equal(runtime.snapshot(rt).policy_versions.length, 0);
});

test("composition stops when a later step asks to attach", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const composed = runtime.integrateAll(rt, [
    { op: "policy_version", input: { version_id: "pol-3" } },
    { op: "host_contract", attach_host: true, attempt: { surface: "files", op: "open", path: "/etc/crontab", uid: 1, pid: 3 } },
    { op: "uninstall", input: { performed: true } },
  ]);
  assert.equal(composed.ok, false);
  assert.equal(composed.contributions.length, 2);
  assert.equal(composed.contributions[1].code, "ATTACHMENT_REFUSED");
  assert.equal(composed.active_protection, false);
  assert.equal(runtime.snapshot(rt).uninstall.status, "NOT_REQUESTED");
});

test("an unknown operation is refused", () => {
  const rt = runtime.createRuntime({ now: () => 5000 });
  const refused = runtime.integrate(rt, { op: "load_ebpf" });
  assert.equal(refused.ok, false);
  assert.equal(refused.code, "UNKNOWN_OP");
  assert.equal(refused.ebpf_loaded, false);
});
