"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { reconcile } = require("../src/index.cjs");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "src");

const FORBIDDEN = [
  "child_process",
  "fs",
  "net",
  "http",
  "https",
  "http2",
  "tls",
  "dgram",
  "dns",
  "worker_threads",
];

test("the join modules do not open sockets, spawn, or touch the filesystem", () => {
  const files = fs.readdirSync(SRC).filter((name) => name.endsWith(".cjs"));
  assert.ok(files.length >= 5);
  for (const name of files) {
    const source = fs.readFileSync(path.join(SRC, name), "utf8");
    for (const token of FORBIDDEN) {
      for (const style of [`"${token}"`, `'${token}'`, `"node:${token}"`, `'node:${token}'`]) {
        assert.equal(source.includes(`require(${style})`), false, `${name} require ${style}`);
      }
    }
    assert.equal(source.includes("import("), false, name);
    assert.equal(source.includes("process.binding"), false, name);
    assert.equal(source.includes("process.env"), false, name);
  }
});

test("lab documents contain no price figures", () => {
  const files = [
    "COUNCIL.md",
    "POSITIONING.md",
    "RISK-REGISTER.md",
    "README.md",
    "LIVE-JOIN.md",
    "fixtures/bypass-drill.json",
    "fixtures/reconciled-openshell.json",
    "fixtures/reconciled-gate.json",
  ];
  for (const relative of files) {
    const source = fs.readFileSync(path.join(ROOT, relative), "utf8");
    assert.equal(/\$\d/.test(source), false, relative);
    assert.equal(source.toLowerCase().includes("unbreakable"), false, relative);
    assert.equal(/\baudited\b/i.test(source), false, relative);
  }
});

test("committed evidence matches the fixtures and the current join", () => {
  const evidence = JSON.parse(fs.readFileSync(path.join(ROOT, "evidence", "bypass-drill.json"), "utf8"));
  assert.equal(evidence.label, "LAB_ONLY");
  assert.equal(evidence.live_stack, "ROADMAP");
  assert.equal(evidence.indicator, "BYPASS_INDICATOR");
  assert.equal(evidence.openshell_runtime, "not-executed");
  assert.equal(evidence.phantom_engine_runtime, "not-executed");
  assert.equal(evidence.controls.openshell, "matched_openshell");
  assert.equal(evidence.controls.gate, "matched_gate");
  assert.equal(evidence.generated_at.endsWith("Z"), true);
  for (const [name, expected] of Object.entries(evidence.fixture_sha256)) {
    const bytes = fs.readFileSync(path.join(ROOT, "fixtures", name));
    const actual = crypto.createHash("sha256").update(bytes).digest("hex");
    assert.equal(actual, expected, name);
  }
  const bypass = JSON.parse(fs.readFileSync(path.join(ROOT, "fixtures", "bypass-drill.json"), "utf8"));
  const result = reconcile(bypass);
  assert.equal(result.findings[0].indicator, evidence.indicator);
  assert.equal(result.findings[0].reason, evidence.reason);
});
