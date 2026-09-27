"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const runtime = require("../../internal/pe-integrated-runtime/src/index.cjs");

const ROOT = path.join(__dirname, "../..");
const SRC = path.join(ROOT, "internal/pe-integrated-runtime/src");

function readSrc() {
  return fs.readdirSync(SRC).filter((name) => name.endsWith(".cjs")).map((name) => {
    return fs.readFileSync(path.join(SRC, name), "utf8");
  }).join("\n");
}

test("the composition source does not attach, load, or spawn", () => {
  const source = readSrc();
  const banned = [
    "child_process",
    "spawnSync",
    "spawn(",
    "execFile",
    "bpftool",
    "proveLiveChild",
    "collectHostFacts",
    "proveEvidence",
    "uninstallSession",
    "@vantio/cli",
    "vantio-agent-sdk-py",
  ];
  for (const token of banned) assert.equal(source.includes(token), false, token);
  assert.equal(Object.prototype.hasOwnProperty.call(runtime, "prove"), false);
});

test("frozen package versions and the workspace list stay closed", () => {
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3\.1\.0"/);
  assert.equal(workspace.includes("pe-integrated-runtime"), false);
  assert.equal(workspace.includes("pe-ingress-authority"), false);
});

test("program and internal registers are the same honesty documents", () => {
  const pairs = [
    ["RUNTIME-REGISTER.json", "RUNTIME-REGISTER.json"],
    ["INTEGRATION-REGISTER.json", "INTEGRATION-REGISTER.json"],
  ];
  for (const [name] of pairs) {
    const internal = fs.readFileSync(path.join(ROOT, "docs/internal/wave3/pe-integration", name), "utf8");
    const program = fs.readFileSync(path.join(ROOT, "docs/programs/production-readiness/wave3", name), "utf8");
    assert.equal(internal, program, name);
  }
  assert.equal(runtime.RUNTIME_REGISTER.producer_classification, "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL");
  assert.equal(runtime.INTEGRATION_REGISTER.active_protection, false);
});

test("two runtimes do not share in-process promotion state", () => {
  const left = runtime.createRuntime({ now: () => 5000 });
  const right = runtime.createRuntime({ now: () => 5000 });
  const signal = { subject_ref: "agent-a", host: "api.example.com", byte_count: 120, at: 10 };
  const created = runtime.integrate(left, {
    op: "progressive",
    step: "discover",
    input: { rule_id: "rule-host", actor: "ada", signal },
  });
  assert.equal(created.ok, true);
  const missing = runtime.integrate(right, {
    op: "progressive",
    step: "decide",
    input: { rule_id: "rule-host", subject_ref: "agent-a", host: "api.example.com", byte_count: 120, at: 10 },
  });
  assert.equal(missing.ok, false);
  assert.equal(missing.code, "UNKNOWN_RULE");
  assert.equal(missing.planes.HOST_ENFORCEMENT.applied, false);
  assert.deepEqual(runtime.snapshot(right).in_process_promoted_rule_ids, []);
  assert.equal(runtime.snapshot(left).host_attachment, false);
  assert.equal(runtime.snapshot(right).ebpf_loaded, false);
});
