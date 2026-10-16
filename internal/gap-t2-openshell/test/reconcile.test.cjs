"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { loadNdjson, reconcile } = require("../src/index.cjs");

const ROOT = path.resolve(__dirname, "..");
const T0 = 1775014138811;

function run(overrides) {
  return {
    schema: "vantio.internal.openshell_reconciliation.run.v1",
    host_id: "lab-host-1",
    window_ms: 5000,
    bindings: [{ cgroup_id: "21", sandbox_id: "policy-demo" }],
    ...overrides,
  };
}

function kernel(overrides) {
  return {
    host_id: "lab-host-1",
    cgroup_id: "21",
    EventType: "TLS_EGRESS",
    ActionTaken: "OBSERVED",
    TraceId: "0xc0ffee00c0ffee00",
    observed_at_ms: T0,
    destination_host: "lab.invalid",
    destination_port: 443,
    ...overrides,
  };
}

function networkRow(overrides) {
  return {
    class_uid: 4001,
    time: T0,
    action: "Allowed",
    metadata: { uid: "event-1", version: "1.8.0" },
    container: { uid: "policy-demo" },
    dst_endpoint: { domain: "lab.invalid", port: 443 },
    ...overrides,
  };
}

function snapshot(overrides) {
  return {
    run: run(),
    kernel: [kernel()],
    openshell: [],
    gate: [],
    ...overrides,
  };
}

function one(result) {
  assert.equal(result.status, "ok");
  assert.equal(result.findings.length, 1);
  return result.findings[0];
}

test("bypass drill fixture flags the kernel write and keeps the parent process record from covering it", () => {
  const raw = JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures", "bypass-drill.json"), "utf8"));
  const result = reconcile(raw);
  const finding = one(result);
  assert.equal(finding.indicator, "BYPASS_INDICATOR");
  assert.equal(finding.reason, "no_matching_openshell_or_gate_record");
  assert.equal(finding.matched_openshell, false);
  assert.equal(finding.matched_gate, false);
  assert.equal(finding.decision_mismatch, false);
  assert.equal(finding.trace_id, "c0ffee00c0ffee00");
  assert.deepEqual(finding.subject, { kind: "network", host: "lab.invalid", port: 443 });
  assert.equal(result.label, "LAB_ONLY");
  assert.equal(result.live_stack, "ROADMAP");
  assert.equal(result.counts.bypass, 1);
  const encoded = JSON.stringify(result);
  assert.equal(encoded.includes("/usr/bin/python3.12"), false);
  assert.equal(encoded.includes("BytesObserved"), false);
  assert.equal(encoded.includes("4242"), false);
  assert.equal(encoded.includes("process start"), false);
});

test("an OpenShell network row reconciles a kernel write with a different pid", () => {
  const raw = JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures", "reconciled-openshell.json"), "utf8"));
  const finding = one(reconcile(raw));
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.reason, "matched_openshell");
  assert.equal(finding.subject.host, "lab.invalid");
  assert.equal(finding.decision_mismatch, false);
});

test("a Gate trace id reconciles when the OpenShell corpus is empty", () => {
  const raw = JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures", "reconciled-gate.json"), "utf8"));
  const finding = one(reconcile(raw));
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.reason, "matched_gate");
});

test("metadata.uid and pid do not join a different destination", () => {
  const finding = one(reconcile(snapshot({
    openshell: [networkRow({
      metadata: { uid: "c0ffee00c0ffee00" },
      dst_endpoint: { domain: "other.invalid", port: 443 },
      actor: { process: { name: "/usr/bin/curl", pid: 4242 } },
    })],
    kernel: [kernel({ Pid: 4242 })],
  })));
  assert.equal(finding.indicator, "BYPASS_INDICATOR");
});

test("the time window is inclusive and a later millisecond misses", () => {
  const onEdge = one(reconcile(snapshot({
    openshell: [networkRow({ time: T0 + 5000 })],
  })));
  assert.equal(onEdge.indicator, "RECONCILED_OK");
  const past = one(reconcile(snapshot({
    openshell: [networkRow({ time: T0 + 5001 })],
  })));
  assert.equal(past.indicator, "BYPASS_INDICATOR");
});

test("a monotonic kernel timestamp stays unattributed", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({
      observed_at_ms: undefined,
      EventTimestamp: 74594084443157,
    })],
  })));
  assert.equal(finding.indicator, "UNATTRIBUTED");
  assert.equal(finding.reason, "kernel_time_not_unix");
});

test("a Gate trace still reconciles a monotonic kernel timestamp", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({
      TraceId: "c1a5",
      observed_at_ms: undefined,
      EventTimestamp: 74594084443157,
    })],
    gate: [{ trace_id: "c1a5", action: "OBSERVED" }],
  })));
  assert.equal(finding.trace_id, "000000000000c1a5");
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.reason, "matched_gate");
});

test("a kernel row outside the binding table is out of scope", () => {
  const otherHost = one(reconcile(snapshot({
    kernel: [kernel({ host_id: "lab-host-2" })],
  })));
  assert.equal(otherHost.indicator, "OUT_OF_SCOPE");
  assert.equal(otherHost.reason, "out_of_scope_host");
  const otherCgroup = one(reconcile(snapshot({
    kernel: [kernel({ cgroup_id: "99" })],
  })));
  assert.equal(otherCgroup.indicator, "OUT_OF_SCOPE");
  assert.equal(otherCgroup.reason, "out_of_scope_cgroup");
});

test("missing subject and unknown event type stay unattributed", () => {
  const noDest = one(reconcile(snapshot({
    kernel: [kernel({ destination_host: undefined, destination_port: undefined })],
  })));
  assert.equal(noDest.indicator, "UNATTRIBUTED");
  assert.equal(noDest.reason, "missing_subject");
  const unknown = one(reconcile(snapshot({
    kernel: [kernel({ EventType: "SOMETHING_ELSE", destination_host: undefined, destination_port: undefined })],
  })));
  assert.equal(unknown.indicator, "UNATTRIBUTED");
  assert.equal(unknown.reason, "missing_action_class");
});

test("a process OpenShell row reconciles an exec and does not need the kernel pid", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({
      EventType: "SYSCALL_EXECVE",
      destination_host: undefined,
      destination_port: undefined,
      exe: "/usr/bin/python3.12",
      Pid: 7,
    })],
    openshell: [{
      class_uid: 1007,
      time: T0,
      action: "Allowed",
      container: { uid: "policy-demo" },
      process: { name: "/usr/bin/python3.12" },
      actor: { process: { name: "/usr/bin/bash", pid: 1 } },
    }],
  })));
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.reason, "matched_openshell");
  assert.deepEqual(finding.subject, { kind: "process", path: "/usr/bin/python3.12" });
});

test("an allowed OpenShell row against a kernel drop is a mismatch on a reconciled finding", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({ EventType: "NETWORK_BLOCK", ActionTaken: "NETWORK_BLOCK" })],
    openshell: [networkRow()],
  })));
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.decision_mismatch, true);
  const observed = one(reconcile(snapshot({
    openshell: [networkRow({ action: "Denied", disposition: "Blocked" })],
  })));
  assert.equal(observed.indicator, "RECONCILED_OK");
  assert.equal(observed.decision_mismatch, false);
});

test("both sides matching names matched_both", () => {
  const finding = one(reconcile(snapshot({
    openshell: [networkRow()],
    gate: [{ trace_id: "0xc0ffee00c0ffee00" }],
  })));
  assert.equal(finding.reason, "matched_both");
});

test("a Gate row for another host or another destination does not clear the kernel row", () => {
  const otherHost = one(reconcile(snapshot({
    gate: [{ trace_id: "c0ffee00c0ffee00", host_id: "lab-host-2" }],
  })));
  assert.equal(otherHost.indicator, "BYPASS_INDICATOR");
  const otherDest = one(reconcile(snapshot({
    gate: [{
      trace_id: "c0ffee00c0ffee00",
      destination_host: "other.invalid",
      destination_port: 443,
    }],
  })));
  assert.equal(otherDest.indicator, "BYPASS_INDICATOR");
});

test("IPv6 brackets and an HTTP class row still reconcile", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({ destination_host: "[2001:db8::1]", destination_port: "443" })],
    openshell: [networkRow({
      class_uid: 4002,
      dst_endpoint: { ip: "2001:db8::1", port: 443 },
    })],
  })));
  assert.equal(finding.indicator, "RECONCILED_OK");
  assert.equal(finding.subject.host, "2001:db8::1");
});

test("repeated cgroup bindings reject the snapshot and emit no findings", () => {
  const same = reconcile(snapshot({
    run: run({
      bindings: [
        { cgroup_id: "21", sandbox_id: "policy-demo" },
        { cgroup_id: "21", sandbox_id: "policy-demo" },
      ],
    }),
  }));
  assert.equal(same.status, "rejected");
  assert.equal(same.reason_code, "AMBIGUOUS_BINDING");
  assert.deepEqual(same.findings, []);
  const clash = reconcile(snapshot({
    run: run({
      bindings: [
        { cgroup_id: "21", sandbox_id: "policy-demo" },
        { cgroup_id: "21", sandbox_id: "other-demo" },
      ],
    }),
  }));
  assert.equal(clash.reason_code, "AMBIGUOUS_BINDING");
});

test("secret fields, conversation fields, and corrupt lines reject without a bypass", () => {
  const secret = reconcile(snapshot({
    kernel: [kernel({ token: "not-printed" })],
  }));
  assert.equal(secret.status, "rejected");
  assert.equal(secret.reason_code, "SECRET_FIELD");
  assert.equal(JSON.stringify(secret).includes("not-printed"), false);
  const conversation = reconcile(snapshot({
    openshell: [networkRow({ prompt: "do not keep" })],
  }));
  assert.equal(conversation.reason_code, "CONVERSATION_FIELD");
  assert.equal(JSON.stringify(conversation).includes("do not keep"), false);
  const bearer = reconcile(snapshot({
    gate: [{ trace_id: "aa", note: "Bearer super-secret-value" }],
  }));
  assert.equal(bearer.reason_code, "SECRET_FIELD");
  assert.equal(JSON.stringify(bearer).includes("super-secret-value"), false);
  const corrupt = loadNdjson('{"ok":true}\n{not-json}\n');
  assert.equal(corrupt.ok, false);
  assert.equal(corrupt.reason_code, "CORRUPT_LINE");
  assert.equal(corrupt.detail, "line 2");
});

test("ndjson rejects a forbidden key and skips blank lines", () => {
  const forbidden = loadNdjson('{"__proto__":{"admin":true}}\n');
  assert.equal(forbidden.ok, false);
  assert.equal(forbidden.reason_code, "SCHEMA");
  const blank = loadNdjson('\n{"host_id":"lab-host-1"}\n\n');
  assert.equal(blank.ok, true);
  assert.equal(blank.records.length, 1);
});

test("oversize input and a missing Gate trace reject", () => {
  const tooMany = reconcile(snapshot({ kernel: Array.from({ length: 4097 }, () => kernel()) }));
  assert.equal(tooMany.status, "rejected");
  assert.equal(tooMany.reason_code, "LIMIT_EXCEEDED");
  assert.equal(tooMany.findings.length, 0);
  const noTrace = reconcile(snapshot({ gate: [{ action: "OBSERVED" }] }));
  assert.equal(noTrace.reason_code, "GATE_RECORD");
  const noSandbox = reconcile(snapshot({
    openshell: [{ class_uid: 4001, time: T0, dst_endpoint: { domain: "lab.invalid", port: 443 } }],
  }));
  assert.equal(noSandbox.reason_code, "OPENSHELL_RECORD");
});

test("an empty kernel snapshot is not a bypass", () => {
  const result = reconcile(snapshot({ kernel: [] }));
  assert.equal(result.status, "ok");
  assert.equal(result.counts.bypass, 0);
  assert.equal(result.findings.length, 0);
});

test("a parent actor record does not clear the parent exec or a network write", () => {
  const parentExec = one(reconcile(snapshot({
    kernel: [kernel({
      EventType: "SYSCALL_EXECVE",
      destination_host: undefined,
      destination_port: undefined,
      exe: "/usr/bin/bash",
    })],
    openshell: [{
      class_uid: 1007,
      time: T0,
      container: { uid: "policy-demo" },
      process: { name: "/usr/bin/python3.12" },
      actor: { process: { name: "/usr/bin/bash" } },
    }],
  })));
  assert.equal(parentExec.indicator, "BYPASS_INDICATOR");
  const childExec = one(reconcile(snapshot({
    kernel: [kernel({
      EventType: "SYSCALL_EXECVE",
      destination_host: undefined,
      destination_port: undefined,
      exe: "/usr/bin/python3.12",
    })],
    openshell: [{
      class_uid: 1007,
      time: T0,
      container: { uid: "policy-demo" },
      process: { name: "/usr/bin/python3.12" },
      actor: { process: { name: "/usr/bin/bash" } },
    }],
  })));
  assert.equal(childExec.indicator, "RECONCILED_OK");
  const actorOnly = one(reconcile(snapshot({
    kernel: [kernel({
      EventType: "SYSCALL_EXECVE",
      destination_host: undefined,
      destination_port: undefined,
      exe: "/usr/bin/python3.12",
    })],
    openshell: [{
      class_uid: 1007,
      time: T0,
      container: { uid: "policy-demo" },
      actor: { process: { name: "/usr/bin/python3.12" } },
    }],
  })));
  assert.equal(actorOnly.indicator, "BYPASS_INDICATOR");
});

test("an in-window monotonic timestamp is not a Unix clock", () => {
  const finding = one(reconcile(snapshot({
    kernel: [kernel({
      observed_at_ms: undefined,
      EventTimestamp: 1792000000000,
    })],
    openshell: [networkRow({ time: 1792000000000 })],
  })));
  assert.equal(finding.indicator, "UNATTRIBUTED");
  assert.equal(finding.reason, "kernel_time_not_unix");
  const gated = one(reconcile(snapshot({
    kernel: [kernel({
      observed_at_ms: undefined,
      EventTimestamp: 1792000000000,
    })],
    gate: [{ trace_id: "0xc0ffee00c0ffee00", observed_at_ms: T0 }],
  })));
  assert.equal(gated.indicator, "RECONCILED_OK");
  assert.equal(gated.reason, "matched_gate");
});

test("leading-zero cgroup ids are one id, and disagreeing aliases reject", () => {
  const clash = reconcile(snapshot({
    run: run({
      bindings: [
        { cgroup_id: "21", sandbox_id: "policy-demo" },
        { cgroup_id: "021", sandbox_id: "other-demo" },
      ],
    }),
  }));
  assert.equal(clash.status, "rejected");
  assert.equal(clash.reason_code, "AMBIGUOUS_BINDING");
  const padded = one(reconcile(snapshot({
    run: run({ bindings: [{ cgroup_id: "021", sandbox_id: "policy-demo" }] }),
    kernel: [kernel({ cgroup_id: 21 })],
  })));
  assert.equal(padded.indicator, "BYPASS_INDICATOR");
  const alias = reconcile(snapshot({
    kernel: [kernel({ host: "evil.example" })],
    openshell: [networkRow()],
  }));
  assert.equal(alias.status, "rejected");
  assert.equal(alias.reason_code, "KERNEL_RECORD");
  assert.equal(JSON.stringify(alias).includes("evil.example"), false);
});

test("a throwing getter or a hidden field rejects without leaking", () => {
  const hidden = kernel();
  Object.defineProperty(hidden, "note", {
    value: "sk-livesecretvalue",
    enumerable: false,
  });
  const hiddenResult = reconcile(snapshot({ kernel: [hidden] }));
  assert.equal(hiddenResult.status, "rejected");
  assert.equal(JSON.stringify(hiddenResult).includes("sk-livesecretvalue"), false);
  const throwing = kernel();
  Object.defineProperty(throwing, "host", {
    enumerable: true,
    get() {
      throw new Error("boom");
    },
  });
  const thrown = reconcile(snapshot({ kernel: [throwing] }));
  assert.equal(thrown.status, "rejected");
  assert.equal(thrown.reason_code, "SCHEMA");
});

test("a basename process record does not reject the snapshot or cover a network write", () => {
  const finding = one(reconcile(snapshot({
    openshell: [{
      class_uid: 1007,
      time: T0,
      container: { uid: "policy-demo" },
      actor: { process: { name: "python", pid: 1 } },
    }],
  })));
  assert.equal(finding.indicator, "BYPASS_INDICATOR");
});

test("a zero window matches only the same millisecond", () => {
  const same = one(reconcile(snapshot({
    run: run({ window_ms: 0 }),
    openshell: [networkRow({ time: T0 })],
  })));
  assert.equal(same.indicator, "RECONCILED_OK");
  const next = one(reconcile(snapshot({
    run: run({ window_ms: 0 }),
    openshell: [networkRow({ time: T0 + 1 })],
  })));
  assert.equal(next.indicator, "BYPASS_INDICATOR");
});

test("cgroup 0 cannot be enrolled, and a zero kernel cgroup stays out of scope", () => {
  const bound = reconcile(snapshot({
    run: run({ bindings: [{ cgroup_id: "0", sandbox_id: "policy-demo" }] }),
  }));
  assert.equal(bound.status, "rejected");
  assert.equal(bound.reason_code, "SCHEMA");
  const padded = reconcile(snapshot({
    run: run({ bindings: [{ cgroup_id: "000", sandbox_id: "policy-demo" }] }),
  }));
  assert.equal(padded.reason_code, "SCHEMA");
  const row = one(reconcile(snapshot({
    kernel: [kernel({ cgroup_id: 0 })],
  })));
  assert.equal(row.indicator, "OUT_OF_SCOPE");
  assert.equal(row.reason, "out_of_scope_cgroup");
});

test("disagreeing Gate aliases reject, and a denial record still reconciles", () => {
  const exe = reconcile(snapshot({
    gate: [{ trace_id: "c0ffee00c0ffee00", exe: "/bin/a", executable: "/bin/b" }],
  }));
  assert.equal(exe.status, "rejected");
  assert.equal(exe.reason_code, "GATE_RECORD");
  assert.equal(exe.findings.length, 0);
  assert.equal(JSON.stringify(exe).includes("/bin/"), false);
  const both = reconcile(snapshot({
    gate: [{
      trace_id: "c0ffee00c0ffee00",
      destination_host: "lab.invalid",
      destination_port: 443,
      exe: "/bin/other",
    }],
  }));
  assert.equal(both.reason_code, "GATE_RECORD");
  const denied = one(reconcile(snapshot({
    openshell: [networkRow({ action: "Denied", disposition: "Blocked" })],
  })));
  assert.equal(denied.indicator, "RECONCILED_OK");
});

test("hostile arrays and revoked proxies reject instead of throwing", () => {
  const rows = [];
  Object.defineProperty(rows, "0", {
    enumerable: true,
    get() {
      throw new Error("sk-from-a-getter");
    },
  });
  const arrayResult = reconcile(snapshot({ kernel: rows }));
  assert.equal(arrayResult.status, "rejected");
  assert.equal(JSON.stringify(arrayResult).includes("sk-from-a-getter"), false);
  const pair = Proxy.revocable({ kernel: [] }, {});
  pair.revoke();
  const revoked = reconcile(pair.proxy);
  assert.equal(revoked.status, "rejected");
  assert.equal(revoked.reason_code, "SCHEMA");
});

test("several kernel writes can match one OpenShell open inside the window", () => {
  const result = reconcile(snapshot({
    kernel: [kernel(), kernel({ observed_at_ms: T0 + 10 })],
    openshell: [networkRow()],
  }));
  assert.equal(result.status, "ok");
  assert.equal(result.counts.reconciled, 2);
  assert.equal(result.counts.bypass, 0);
});
