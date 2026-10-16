"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "..");
const SRC = path.join(ROOT, "src");

const FORBIDDEN = [
  "child_process",
  "node:child_process",
  "node:net",
  "node:http",
  "node:https",
  "node:tls",
  "node:dgram",
  "node:dns",
  "node:fs",
];

test("the join modules do not open sockets, spawn, or touch the filesystem", () => {
  const files = fs.readdirSync(SRC).filter((name) => name.endsWith(".cjs"));
  assert.ok(files.length >= 5);
  for (const name of files) {
    const source = fs.readFileSync(path.join(SRC, name), "utf8");
    for (const token of FORBIDDEN) {
      assert.equal(source.includes(`require("${token}")`), false, `${name} requires ${token}`);
      assert.equal(source.includes(`require('${token}')`), false, `${name} requires ${token}`);
    }
    assert.equal(source.includes("process.env"), false, name);
  }
});

test("lab documents contain no price figures", () => {
  const files = [
    "COUNCIL.md",
    "POSITIONING.md",
    "RISK-REGISTER.md",
    "README.md",
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

test("the proof script writes the bypass evidence and exits 0", () => {
  const script = path.join(ROOT, "proof", "prove-bypass.cjs");
  const stdout = execFileSync(process.execPath, [script], { encoding: "utf8" });
  assert.match(stdout, /BYPASS_INDICATOR/);
  const evidence = JSON.parse(fs.readFileSync(path.join(ROOT, "evidence", "bypass-drill.json"), "utf8"));
  assert.equal(evidence.label, "LAB_ONLY");
  assert.equal(evidence.live_stack, "ROADMAP");
  assert.equal(evidence.indicator, "BYPASS_INDICATOR");
  assert.equal(evidence.openshell_runtime, "not-executed");
  assert.equal(evidence.phantom_engine_runtime, "not-executed");
  assert.equal(evidence.controls.openshell, "matched_openshell");
  assert.equal(evidence.controls.gate, "matched_gate");
  assert.equal(typeof evidence.generated_at, "string");
  assert.equal(evidence.generated_at.endsWith("Z"), true);
});
