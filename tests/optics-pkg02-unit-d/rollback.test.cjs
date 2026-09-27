"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const test = require("node:test");

const { displayCall } = require("../../packages/vantio-cli/bin/optics-cx.cjs");
const api = require("../../packages/vantio-cli-pkg02/src/index.cjs");
const { composeCanonical } = require("../../packages/vantio-cli-pkg02/src/record.cjs");
const support = require("./support.cjs");

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

test("the same workload differs from CLI 0.3.24 in the written record", () => {
  const script = `
    const http = require("node:http");
    const server = http.createServer((req, res) => {
      const body = Buffer.from("{}");
      res.writeHead(200, { "Content-Type": "application/json", "Content-Length": String(body.length) });
      res.end(body);
    });
    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      const response = await fetch("http://127.0.0.1:" + port + "/v1/chat/completions", { method: "POST", body: "{}" });
      await response.arrayBuffer();
      server.close();
    });
  `;
  const frozenHome = support.homeDir("unit-d-delta-frozen-");
  const futureHome = support.homeDir("unit-d-delta-future-");
  try {
    const file = require("node:path").join(frozenHome, "workload.cjs");
    fs.writeFileSync(file, script);
    const frozen = support.runFrozen(frozenHome, ["run", "node", file]);
    const future = support.runFuture(futureHome, script);
    assert.equal(frozen.status, 0, frozen.stderr || frozen.stdout);
    assert.equal(future.status, 0, future.stderr || future.stdout);
    const oldFile = support.readJson(support.runFiles(frozenHome)[0]);
    const nextFile = support.readJson(support.runFiles(futureHome)[0]);
    assert.equal(oldFile.vantio_run_log, "1");
    assert.equal(oldFile.schema_version, 2);
    assert.equal(oldFile.cli_version, "0.3.24");
    assert.equal(typeof oldFile.trace_id, "string");
    assert.equal(Object.prototype.hasOwnProperty.call(oldFile, "record_type"), false);
    assert.equal(Object.prototype.hasOwnProperty.call(oldFile.calls[0], "optics_status"), false);
    assert.equal(nextFile.record_type, "run_envelope");
    assert.equal(nextFile.schema_version, 0);
    assert.equal(nextFile.compatibility.legacy_schema_version, 2);
    assert.equal(nextFile.run_id.startsWith("0x"), true);
    assert.equal(nextFile.events[0].record_type, "observation_event");
    assert.equal(nextFile.events[0].optics_status, "OBSERVED");
    assert.equal(nextFile.events[0].response_bytes, 2);
    assert.equal(nextFile.events[0].evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(nextFile.events[0].issue_location, "NONE");
    assert.equal(nextFile.diagnostics.unicode_profile_id, "PKG01-UCD-16.0.0");
    support.assertNoOpticsSuccess(assert, nextFile);
    assert.equal(JSON.stringify(nextFile).includes("\"plane\""), false);
    assert.equal(JSON.stringify(oldFile).includes("\"plane\""), true);
  } finally {
    fs.rmSync(frozenHome, { recursive: true, force: true });
    fs.rmSync(futureHome, { recursive: true, force: true });
  }
});

test("disabling the writer restores the previous shape and leaves the canonical file in place", () => {
  const home = support.homeDir("unit-d-rollback-");
  try {
    const first = support.runFuture(home, "process.exit(0);\n");
    assert.equal(first.status, 0, first.stderr || first.stdout);
    const canonicalPath = support.runFiles(home)[0];
    const before = fs.readFileSync(canonicalPath);
    const beforeHash = sha256(before);
    const canonical = JSON.parse(before.toString("utf8"));
    assert.equal(canonical.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(canonical.optics_status, "NOT_OBSERVED");
    const second = support.runFuture(home, "process.exit(0);\n", { VANTIO_PKG02_WRITER: "0" });
    assert.equal(second.status, 0, second.stderr || second.stdout);
    const after = fs.readFileSync(canonicalPath);
    assert.equal(sha256(after), beforeHash);
    assert.equal(after.equals(before), true);
    const files = support.runFiles(home);
    assert.equal(files.length, 2);
    const legacyPath = files.find((file) => file !== canonicalPath);
    const legacy = support.readJson(legacyPath);
    assert.equal(legacy.vantio_run_log, "1");
    assert.equal(legacy.schema_version, 2);
    assert.equal(legacy.cli_version, "0.3.24");
    assert.equal(Object.prototype.hasOwnProperty.call(legacy, "record_type"), false);
    const rolled = api.readRolledBack(canonicalPath);
    assert.equal(rolled.classification, "UNSUPPORTED");
    assert.equal(rolled.optics_status, "UNSUPPORTED");
    assert.equal(rolled.schema_status, "unstable-pre-1.0");
    assert.equal(rolled.schema_version, 0);
    assert.equal(rolled.schema_marker_visible, true);
    assert.equal(rolled.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(rolled.bytes_identical, true);
    assert.equal(rolled.rewritten, false);
    assert.equal(rolled.unknown_status_becomes_success, false);
    assert.equal(rolled.activates_unit_e, false);
    const frozenDisplay = displayCall(canonical.events[0] || { destination_host: "127.0.0.1", http_status: 200 });
    assert.equal(frozenDisplay.opticsStatus, "SUCCESS");
    assert.notEqual(rolled.optics_status, frozenDisplay.opticsStatus);
    const still = support.readJson(canonicalPath);
    assert.equal(still.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(sha256(fs.readFileSync(canonicalPath)), beforeHash);
    const legacyRead = api.readRolledBack(legacyPath);
    assert.equal(legacyRead.classification, "LEGACY_SHAPE");
    assert.equal(legacyRead.optics_status, "UNAVAILABLE");
    assert.notEqual(legacyRead.optics_status, "SUCCESS");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a validator failure keeps the workload exit code and does not write optics SUCCESS", () => {
  const kept = { code: 4, marker: "workload-kept" };
  const fault = composeCanonical(
    { calls: [], schema_version: 2, trace_id: "0xfault", vantio_run_log: "1" },
    [],
    { applicationResult: kept, injectFault: true },
  );
  assert.deepEqual(fault.application_result, kept);
  assert.equal(fault.optics_status, "OPTICS_ERROR");
  assert.equal(fault.document.optics_status, "OPTICS_ERROR");
  support.assertNoOpticsSuccess(assert, fault.document);
  assert.equal(JSON.stringify(fault.document).includes("workload-kept"), false);

  const home = support.homeDir("unit-d-fault-");
  try {
    const child = support.runFuture(home, "process.exit(4);\n", { VANTIO_PKG02_INJECT_FAULT: "1" });
    assert.equal(child.status, 4, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assert.equal(document.optics_status, "OPTICS_ERROR");
    assert.equal(document.issue_location, "OPTICS");
    assert.equal(document.schema_status, "unstable-pre-1.0");
    assert.equal(document.schema_version, 0);
    assert.equal(document.diagnostics.unicode_profile_id, "PKG01-UCD-16.0.0");
    support.assertNoOpticsSuccess(assert, document);
    assert.notEqual(document.evidence_origin, "LOCAL_OBSERVATION");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
