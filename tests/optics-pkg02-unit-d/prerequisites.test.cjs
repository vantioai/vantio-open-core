"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/vantio-cli-pkg02/src/index.cjs");
const { adaptNodeCopy } = require("../../packages/optics-node-adapter/src/adapt.cjs");
const support = require("./support.cjs");

test("inert Unit B adapter is present and an ordinary 0.3.24 file stays byte-identical while unused", () => {
  const home = support.homeDir("unit-d-byte-");
  try {
    const child = support.runFrozen(home, ["run", "node", "-e", "process.exit(0)"]);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const file = support.runFiles(home)[0];
    const before = fs.readFileSync(file);
    assert.equal(api.proveAdapterByteIdentity(file), true);
    const after = fs.readFileSync(file);
    assert.equal(before.equals(after), true);
    const parsed = JSON.parse(before.toString("utf8"));
    assert.equal(parsed.cli_version, "0.3.24");
    assert.equal(parsed.schema_version, 2);
    assert.equal(parsed.vantio_run_log, "1");
    assert.equal(Object.prototype.hasOwnProperty.call(parsed, "record_type"), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("loading the inert adapter inside a 0.3.24 run does not change the frozen record shape", () => {
  const plainHome = support.homeDir("unit-d-plain-");
  const adapterHome = support.homeDir("unit-d-adapter-");
  try {
    const plain = support.runFrozen(plainHome, ["run", "node", "-e", "process.exit(0)"], {
      VANTIO_TRACE_ID: "0xunitdplainshape",
    });
    const withAdapter = support.runFrozen(adapterHome, ["run", "node", "-e", "process.exit(0)"], {
      NODE_OPTIONS: `--require ${support.ADAPTER}`,
      VANTIO_TRACE_ID: "0xunitdadaptershape",
    });
    assert.equal(plain.status, 0, plain.stderr || plain.stdout);
    assert.equal(withAdapter.status, 0, withAdapter.stderr || withAdapter.stdout);
    const left = support.readJson(support.runFiles(plainHome)[0]);
    const right = support.readJson(support.runFiles(adapterHome)[0]);
    for (const record of [left, right]) {
      delete record.pid;
      delete record.ppid;
      delete record.started_at;
      delete record.generated_at;
      delete record.duration_ms;
      delete record.node_version;
      delete record.trace_id;
    }
    assert.deepEqual(left, right);
    assert.equal(right.cli_version, "0.3.24");
    assert.equal(right.schema_version, 2);
  } finally {
    fs.rmSync(plainHome, { recursive: true, force: true });
    fs.rmSync(adapterHome, { recursive: true, force: true });
  }
});

test("unknown optics_status does not become SUCCESS before the writer is asked to activate", () => {
  const proof = api.proveUnknownOpticsNotSuccess();
  assert.equal(proof.unknown_becomes_success, false);
  assert.equal(proof.optimistic_default_forbidden, true);
  assert.equal(proof.tokens.includes("UNAVAILABLE"), true);
  assert.equal(proof.tokens.includes("SUCCESS"), false);
  const adapted = adaptNodeCopy({
    calls: [{ hostname: "api.openai.com", opticsStatus: "SUPER_SUCCESS", status: 200 }],
    schema_version: 2,
    vantio_run_log: "1",
  });
  assert.equal(adapted.optimistic_default_forbidden, true);
  const tokens = support.opticsTokens(adapted, []);
  assert.equal(tokens.includes("SUCCESS"), false);
  assert.equal(tokens.includes("UNAVAILABLE"), true);
});
