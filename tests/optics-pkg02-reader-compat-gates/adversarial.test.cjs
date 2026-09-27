"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { displayCall } = require("../../packages/vantio-cli/bin/optics-cx.cjs");
const { explainCopy } = require("../../packages/optics-record-reader/src/explain.cjs");
const {
  CLASSIFICATION_BLOCKED,
  CLASSIFICATION_READY,
  evaluateEntryGates,
} = require("../../packages/optics-reader-compat-gates/src/index.cjs");
const { ABSENT_NAME, CANARY, futureRecord, writeCorpus } = require("./samples.cjs");

function withCorpus(run) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-adv-"));
  try {
    const corpus = writeCorpus(directory);
    const frozen = displayCall(futureRecord());
    assert.equal(frozen.opticsStatus, "SUCCESS");
    return run(directory, corpus, frozen);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
}

function reportText(report) {
  return JSON.stringify(report);
}

test("a forged compatible frozen display blocks the ready classification", () => {
  withCorpus((directory, corpus) => {
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: { opticsStatus: "OBSERVED" },
    });
    assert.equal(report.producer_classification, CLASSIFICATION_BLOCKED);
    assert.equal(report.producer_ready_for_council, false);
    assert.equal(reportText(report).includes(CLASSIFICATION_READY), false);
    const frozenGate = report.gates.find((gate) => gate.id === "frozen_cli_honestly_unsupported");
    assert.equal(frozenGate.passed, false);
    assert.equal(report.activates_unit_d, false);
    assert.equal(report.writer_activated, false);
  });
});

test("a missing role blocks every gate", () => {
  withCorpus((directory, corpus) => {
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries.slice(1),
      frozenDisplay: displayCall(futureRecord()),
    });
    assert.equal(report.blocked_reason, "ROLE_SET_REFUSED");
    assert.equal(report.producer_classification, CLASSIFICATION_BLOCKED);
    assert.equal(report.gates.every((gate) => gate.passed === false), true);
  });
});

test("a symlink and a path escape are refused before any outside read", () => {
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-out-"));
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-link-"));
  const secret = path.join(outside, "secret.json");
  const secretBytes = Buffer.from(JSON.stringify({ prompt: CANARY, optics_status: "SUCCESS" }));
  fs.writeFileSync(secret, secretBytes);
  try {
    const corpus = writeCorpus(directory);
    fs.unlinkSync(path.join(directory, "legacy-cli.json"));
    fs.symlinkSync(secret, path.join(directory, "legacy-cli.json"));
    const linked = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: displayCall(futureRecord()),
    });
    assert.equal(linked.blocked_reason, "SYMLINK_REFUSED");
    assert.equal(linked.producer_classification, CLASSIFICATION_BLOCKED);
    assert.equal(reportText(linked).includes(CANARY), false);
    assert.equal(fs.readFileSync(secret).equals(secretBytes), true);

    fs.unlinkSync(path.join(directory, "legacy-cli.json"));
    fs.writeFileSync(path.join(directory, "legacy-cli.json"), Buffer.from("{\"vantio_run_log\":\"1\"}\n"));
    const escaped = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries.map((entry) => {
        if (entry.role === "legacy_python") return { name: "../secret.json", role: entry.role };
        return entry;
      }),
      frozenDisplay: displayCall(futureRecord()),
    });
    assert.equal(escaped.blocked_reason, "NAME_REFUSED");
    assert.equal(fs.readFileSync(secret).equals(secretBytes), true);
    assert.equal(reportText(escaped).includes(CANARY), false);
  } finally {
    fs.rmSync(outside, { recursive: true, force: true });
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("promote and writer options leave every corpus byte in place", () => {
  withCorpus((directory, corpus, frozen) => {
    const before = new Map();
    for (const entry of corpus.entries) {
      before.set(entry.name, fs.readFileSync(path.join(directory, entry.name)));
    }
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: frozen,
    });
    assert.equal(report.producer_classification, CLASSIFICATION_READY);
    assert.equal(report.bytes_rewritten, false);
    for (const entry of corpus.entries) {
      assert.equal(fs.readFileSync(path.join(directory, entry.name)).equals(before.get(entry.name)), true);
    }
    assert.equal(fs.existsSync(path.join(directory, ABSENT_NAME)), false);
    const claimed = report.entries.find((entry) => entry.role === "claimed_local");
    assert.equal(claimed.sourceOrigin, "LOCAL_OBSERVATION");
    assert.equal(claimed.reader.originLabel, "LEGACY_UNMARKED");
    assert.equal(claimed.reader.mentionsLocalObservation, false);
    const newer = report.entries.find((entry) => entry.role === "newer_schema");
    assert.equal(newer.schemaVersion, 99);
    assert.equal(newer.schemaStatus, "stable-v9");
    assert.equal(newer.reader.schemaVersion, 0);
    assert.equal(newer.bytesIdentical, true);
  });
});

test("unknown tokens are not displayed as optics SUCCESS", () => {
  const unknown = explainCopy({
    http_status: 200,
    optics_status: "SUPER_SUCCESS",
    record_type: "observation_event",
  });
  const lower = explainCopy({
    http_status: 200,
    optics_status: "success",
    record_type: "observation_event",
  });
  const legacy = explainCopy({
    opticsStatus: "SUCCESS",
    record_type: "observation_event",
    status: 200,
  });
  for (const result of [unknown, lower, legacy]) {
    assert.equal(result.optics_health, "UNAVAILABLE");
    assert.equal(result.optics_displayed_as_success, false);
    assert.equal(result.explanation_text.includes("optics_status=SUCCESS"), false);
    assert.equal(result.write_back, false);
  }
  assert.equal(unknown.optics_input_classes.includes("unknown"), true);
  assert.equal(JSON.stringify(unknown).includes("SUPER_SUCCESS"), false);
  assert.equal(lower.optics_input_classes.includes("unknown"), true);
  assert.equal(legacy.optics_input_classes.includes("refused_success"), true);
  assert.equal(legacy.record.application_status, "SUCCESS");
  assert.equal(legacy.record.optics_status, "UNAVAILABLE");
});

test("the gate report does not echo a canary, an unknown token, or a created file", () => {
  withCorpus((directory, corpus, frozen) => {
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: frozen,
    });
    const text = reportText(report);
    assert.equal(text.includes(CANARY), false);
    assert.equal(text.includes("SUPER_SUCCESS"), false);
    assert.equal(text.includes("freshness"), false);
    assert.equal(text.includes("widget_hint"), false);
    assert.equal(text.includes("est_spend_usd"), false);
    assert.equal(text.includes("\"prompt\""), false);
    assert.equal(text.includes(directory), false);
    assert.equal(fs.existsSync(path.join(directory, ABSENT_NAME)), false);
    const corrupt = report.entries.find((entry) => entry.role === "corrupt");
    assert.equal(corrupt.reader.opticsHealth, "OPTICS_ERROR");
    assert.equal(corrupt.reader.recordEmitted, false);
    assert.equal(corrupt.bytesIdentical, true);
    const field = report.entries.find((entry) => entry.role === "future_field");
    assert.equal(field.reader.prohibitedEcho, false);
    assert.equal(field.reader.mentionsLocalObservation, false);
  });
});

test("an empty request and a non-directory are blocked", () => {
  assert.equal(evaluateEntryGates(null).blocked_reason, "REQUEST_REFUSED");
  assert.equal(evaluateEntryGates(null).producer_classification, CLASSIFICATION_BLOCKED);
  assert.equal(reportText(evaluateEntryGates(null)).includes(CLASSIFICATION_READY), false);
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-file-"));
  try {
    const corpus = writeCorpus(directory);
    const file = path.join(directory, "legacy-cli.json");
    const before = fs.readFileSync(file);
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory: file,
      entries: corpus.entries,
      frozenDisplay: displayCall(futureRecord()),
    });
    assert.equal(report.blocked_reason, "DIRECTORY_REFUSED");
    assert.equal(report.producer_classification, CLASSIFICATION_BLOCKED);
    assert.equal(fs.readFileSync(file).equals(before), true);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
