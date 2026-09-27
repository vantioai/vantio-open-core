"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const ZERO = "0".repeat(64);

function canonical(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => canonical(item)).join(",")}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
}

function hashRecord(prev, record) {
  return crypto.createHash("sha256").update(`${prev}\n${canonical(record)}`).digest("hex");
}

function openLedger(dir) {
  const file = path.join(dir, "ledger.ndjson");
  fs.writeFileSync(file, "");
  return { file, prev: ZERO, seq: 0 };
}

function appendRecord(ledger, record) {
  const hash = hashRecord(ledger.prev, record);
  const line = { seq: ledger.seq, prev: ledger.prev, hash, record };
  fs.appendFileSync(ledger.file, `${JSON.stringify(line)}\n`);
  return { file: ledger.file, prev: hash, seq: ledger.seq + 1 };
}

function verifyLedger(file) {
  const raw = fs.readFileSync(file, "utf8");
  if (raw.length === 0) {
    return { ok: false, reason: "EMPTY" };
  }
  if (!raw.endsWith("\n")) {
    return { ok: false, reason: "TRUNCATED_TAIL", prevention: "FAIL_CLOSED_GAP" };
  }
  const lines = raw.slice(0, -1).split("\n");
  let prev = ZERO;
  for (let i = 0; i < lines.length; i += 1) {
    let parsed;
    try {
      parsed = JSON.parse(lines[i]);
    } catch {
      return { ok: false, reason: "MALFORMED_LINE", prevention: "FAIL_CLOSED_GAP" };
    }
    if (parsed.seq !== i || parsed.prev !== prev) {
      return { ok: false, reason: "PREV_OR_SEQ_MISMATCH", prevention: "FAIL_CLOSED_GAP" };
    }
    const expect = hashRecord(prev, parsed.record);
    if (parsed.hash !== expect) {
      return { ok: false, reason: "HASH_MISMATCH", prevention: "FAIL_CLOSED_GAP" };
    }
    prev = parsed.hash;
  }
  return { ok: true, reason: "CHAIN_INTACT", records: lines.length, prevention: "FAIL_CLOSED_GAP" };
}

function proveEvidence(dir) {
  const ledger = openLedger(dir);
  const after = appendRecord(
    appendRecord(ledger, { kind: "observe", n: 1 }),
    { kind: "observe", n: 2 },
  );
  const intact = verifyLedger(after.file);
  const intactCopy = path.join(dir, "intact.ndjson");
  fs.copyFileSync(after.file, intactCopy);

  const truncated = path.join(dir, "truncated.ndjson");
  const original = fs.readFileSync(after.file);
  fs.writeFileSync(truncated, original.subarray(0, Math.max(0, original.length - 8)));
  const truncateResult = verifyLedger(truncated);

  const rewritten = path.join(dir, "rewritten.ndjson");
  const text = fs.readFileSync(intactCopy, "utf8");
  fs.writeFileSync(rewritten, text.replace("\"n\":1", "\"n\":9"));
  const rewriteResult = verifyLedger(rewritten);
  const stillIntact = verifyLedger(intactCopy);

  return {
    mechanism_id: "evidence_hash_chain",
    kernel_executed: false,
    cases: [
      {
        id: "evidence-append-verifies",
        surface: "evidence_tampering",
        disposition: intact.ok ? "CHAIN_INTACT" : "FAIL_CLOSED_GAP",
        reason: intact.reason,
        prevention: "FAIL_CLOSED_GAP",
        mechanism_id: "evidence_hash_chain",
        kernel_executed: false,
        execution: "TEMP_FILE",
      },
      {
        id: "evidence-truncate-detected",
        surface: "evidence_tampering",
        disposition: truncateResult.ok ? "FAIL_CLOSED_GAP" : "DETECTED",
        reason: truncateResult.reason,
        write_succeeded: true,
        prevention: "FAIL_CLOSED_GAP",
        mechanism_id: "evidence_hash_chain",
        kernel_executed: false,
        execution: "TEMP_FILE",
      },
      {
        id: "evidence-rewrite-detected",
        surface: "evidence_tampering",
        disposition: rewriteResult.ok ? "FAIL_CLOSED_GAP" : "DETECTED",
        reason: rewriteResult.reason,
        write_succeeded: true,
        prevention: "FAIL_CLOSED_GAP",
        mechanism_id: "evidence_hash_chain",
        kernel_executed: false,
        execution: "TEMP_FILE",
      },
      {
        id: "evidence-original-remains",
        surface: "evidence_tampering",
        disposition: stillIntact.ok ? "CHAIN_INTACT" : "FAIL_CLOSED_GAP",
        reason: stillIntact.reason,
        prevention: "FAIL_CLOSED_GAP",
        mechanism_id: "evidence_hash_chain",
        kernel_executed: false,
        execution: "TEMP_FILE",
      },
    ],
  };
}

module.exports = {
  ZERO,
  canonical,
  hashRecord,
  openLedger,
  appendRecord,
  verifyLedger,
  proveEvidence,
};
