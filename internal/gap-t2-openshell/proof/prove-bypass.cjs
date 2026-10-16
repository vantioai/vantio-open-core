"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const { EVIDENCE_SCHEMA, reconcile } = require("../src/index.cjs");

const ROOT = path.resolve(__dirname, "..");
const EVIDENCE_PATH = path.resolve(ROOT, "evidence", "bypass-drill.json");

function assertInside(target) {
  const rootWithSep = ROOT.endsWith(path.sep) ? ROOT : `${ROOT}${path.sep}`;
  if (target !== ROOT && !target.startsWith(rootWithSep)) {
    throw new Error("refusing a path outside the lab package");
  }
}

function readFixture(name) {
  const target = path.resolve(ROOT, "fixtures", name);
  assertInside(target);
  return fs.readFileSync(target);
}

function loadSnapshot(name) {
  const bytes = readFixture(name);
  const snapshot = JSON.parse(bytes.toString("utf8"));
  return { bytes, snapshot };
}

function expectIndicator(snapshot, indicator, reason) {
  const result = reconcile(snapshot);
  if (result.status !== "ok") {
    throw new Error(`snapshot rejected: ${result.reason_code}`);
  }
  if (result.label !== "LAB_ONLY" || result.live_stack !== "ROADMAP") {
    throw new Error("label drifted");
  }
  if (result.findings.length !== 1 || result.findings[0].indicator !== indicator) {
    throw new Error(`expected one ${indicator}`);
  }
  if (reason && result.findings[0].reason !== reason) {
    throw new Error(`expected reason ${reason}`);
  }
  return result;
}

function main() {
  const bypass = loadSnapshot("bypass-drill.json");
  const openshell = loadSnapshot("reconciled-openshell.json");
  const gate = loadSnapshot("reconciled-gate.json");
  const bypassResult = expectIndicator(
    bypass.snapshot,
    "BYPASS_INDICATOR",
    "no_matching_openshell_or_gate_record",
  );
  const openshellResult = expectIndicator(openshell.snapshot, "RECONCILED_OK", "matched_openshell");
  const gateResult = expectIndicator(gate.snapshot, "RECONCILED_OK", "matched_gate");
  const bypassFinding = bypassResult.findings[0];
  if (bypassFinding.matched_openshell || bypassFinding.matched_gate || bypassFinding.decision_mismatch) {
    throw new Error("bypass finding matched a record");
  }
  if (bypassFinding.subject.kind !== "network" || bypassFinding.subject.host !== "lab.invalid") {
    throw new Error("bypass subject drifted");
  }
  const evidence = {
    schema: EVIDENCE_SCHEMA,
    generated_at: new Date().toISOString(),
    label: "LAB_ONLY",
    live_stack: "ROADMAP",
    drill: "kernel TLS_EGRESS with an OpenShell process record and no Gate record",
    indicator: bypassFinding.indicator,
    reason: bypassFinding.reason,
    controls: {
      openshell: openshellResult.findings[0].reason,
      gate: gateResult.findings[0].reason,
    },
    fixture_sha256: {
      "bypass-drill.json": crypto.createHash("sha256").update(bypass.bytes).digest("hex"),
      "reconciled-openshell.json": crypto.createHash("sha256").update(openshell.bytes).digest("hex"),
      "reconciled-gate.json": crypto.createHash("sha256").update(gate.bytes).digest("hex"),
    },
    node: process.version,
    openshell_runtime: "not-executed",
    phantom_engine_runtime: "not-executed",
  };
  const encoded = `${JSON.stringify(evidence, null, 2)}\n`;
  if (encoded.includes("sk-") || encoded.includes("BEGIN ")) {
    throw new Error("evidence refused");
  }
  assertInside(EVIDENCE_PATH);
  fs.mkdirSync(path.dirname(EVIDENCE_PATH), { recursive: true });
  fs.writeFileSync(EVIDENCE_PATH, encoded);
  process.stdout.write(`LAB_ONLY BYPASS_INDICATOR evidence=${EVIDENCE_PATH}\n`);
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : "proof failed";
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
