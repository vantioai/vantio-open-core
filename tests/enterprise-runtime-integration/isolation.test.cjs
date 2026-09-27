"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const composition = require("../../internal/enterprise-runtime-integration/src/index.cjs");
const enterprise = require("../../internal/enterprise-governance/src/index.cjs");
const runtime = require("../../internal/pe-integrated-runtime/src/index.cjs");

const ROOT = path.join(__dirname, "../..");
const SRC = path.join(ROOT, "internal/enterprise-runtime-integration/src");

function readSrc() {
  return fs.readdirSync(SRC).filter((name) => name.endsWith(".cjs")).map((name) => {
    return fs.readFileSync(path.join(SRC, name), "utf8");
  }).join("\n");
}

test("the composition source does not attach, load, publish, or spawn", () => {
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
    "pnpm publish",
  ];
  for (const token of banned) assert.equal(source.includes(token), false, token);
  assert.equal(Object.prototype.hasOwnProperty.call(composition, "prove"), false);
  assert.equal(source.includes("enterprise-governance/src/index.cjs"), true);
  assert.equal(source.includes("pe-integrated-runtime/src/index.cjs"), true);
});

test("frozen package versions and the workspace list stay closed", () => {
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3\.1\.0"/);
  assert.equal(workspace.includes("enterprise-runtime-integration"), false);
  assert.equal(workspace.includes("enterprise-governance"), false);
  assert.equal(workspace.includes("pe-integrated-runtime"), false);
});

test("program and internal registers are the same honesty documents", () => {
  const pairs = [
    ["RUNTIME-REGISTER.json", "ENTERPRISE-RUNTIME-REGISTER.json"],
    ["INTEGRATION-REGISTER.json", "ENTERPRISE-INTEGRATION-REGISTER.json"],
    ["STATUS.json", "ENTERPRISE-RUNTIME-STATUS.json"],
  ];
  for (const [internalName, programName] of pairs) {
    const internal = fs.readFileSync(path.join(ROOT, "docs/internal/wave3/enterprise-runtime", internalName), "utf8");
    const program = fs.readFileSync(path.join(ROOT, "docs/programs/production-readiness/wave3", programName), "utf8");
    assert.equal(internal, program, internalName);
  }
  assert.equal(composition.RUNTIME_REGISTER.producer_classification, "W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL");
  assert.equal(composition.RUNTIME_REGISTER.live_customer_authority, false);
  assert.equal(composition.INTEGRATION_REGISTER.record_layer_only, true);
  assert.equal(composition.STATUS.frozen_version_reopened, false);
});

test("this force leaves the enterprise and PE producer classifications in place", () => {
  assert.equal(enterprise.PRODUCER_CLASSIFICATION, "ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL");
  assert.equal(runtime.PRODUCER_CLASSIFICATION, "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL");
  assert.equal(runtime.POSTURE.host_attachment, false);
  assert.equal(enterprise.POSTURE.includes("NO_HOST_CONTACT"), true);
  const comp = composition.createComposition({ now: () => 0 });
  assert.equal(comp.kind, "W3_ENTERPRISE_RUNTIME_COMPOSITION");
  assert.equal(comp.pe.kind, "PE_INTEGRATED_RUNTIME");
  assert.equal(comp.store.marker, "customer-held-enterprise-record");
  assert.notEqual(comp.store, composition.createComposition().store);
  const view = composition.snapshot(comp);
  assert.equal(view.pe.producer_classification, "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL");
  assert.equal(view.producer_classification, "W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL");
  assert.equal(view.live_customer_authority, false);
  assert.equal(view.host_attachment, false);
});
