"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { appendRecord, openLedger, proveEvidence, verifyLedger } = require("../../packages/pe-host-authority/src/evidence.cjs");

test("a valid chain verifies and an owner rewrite is detected", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "pe-host-authority-evidence-"));
  try {
    const proof = proveEvidence(dir);
    const byId = Object.fromEntries(proof.cases.map((row) => [row.id, row]));
    assert.equal(byId["evidence-append-verifies"].reason, "CHAIN_INTACT");
    assert.equal(byId["evidence-truncate-detected"].reason, "TRUNCATED_TAIL");
    assert.equal(byId["evidence-rewrite-detected"].reason, "HASH_MISMATCH");
    assert.equal(byId["evidence-truncate-detected"].prevention, "FAIL_CLOSED_GAP");
    const ledger = openLedger(dir);
    const next = appendRecord(ledger, { kind: "row" });
    assert.equal(verifyLedger(next.file).ok, true);
    fs.rmSync(next.file);
    assert.equal(fs.existsSync(next.file), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
