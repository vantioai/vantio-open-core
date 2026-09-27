"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { displayCall } = require("../../packages/vantio-cli/bin/optics-cx.cjs");
const { explainCopy, readRunFile } = require("../../packages/optics-record-reader/src/explain.cjs");

const CANARY = "sk-UNITFREADER00001";

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function opticsTokens(result) {
  const tokens = [result.optics_health];
  for (const line of result.display) {
    if (line.dimension === "optics_status" || line.dimension === "optics_health") tokens.push(line.token);
  }
  return tokens;
}

test("unknown, missing, null, and legacy SUCCESS do not display as optics success", () => {
  const unknown = explainCopy({
    http_status: 200,
    optics_status: "SUPER_SUCCESS",
    record_type: "observation_event",
  });
  const missing = explainCopy({
    http_status: 200,
    record_type: "observation_event",
  });
  const nulled = explainCopy({
    http_status: 200,
    optics_status: null,
    record_type: "observation_event",
  });
  const legacy = explainCopy({
    opticsStatus: "SUCCESS",
    record_type: "observation_event",
    status: 200,
  });
  assert.equal(unknown.optics_health, "UNAVAILABLE");
  assert.equal(unknown.optimistic_default_forbidden, true);
  assert.equal(unknown.optics_input_classes.includes("unknown"), true);
  assert.equal(JSON.stringify(unknown).includes("SUPER_SUCCESS"), false);
  assert.equal(missing.optics_input_classes.includes("absent"), true);
  assert.equal(nulled.optics_input_classes.includes("null"), true);
  assert.equal(legacy.optics_input_classes.includes("refused_success"), true);
  assert.equal(legacy.record.optics_status, "UNAVAILABLE");
  assert.equal(legacy.record.application_status, "SUCCESS");
  for (const result of [unknown, missing, nulled, legacy]) {
    assert.equal(result.optics_displayed_as_success, false);
    assert.equal(opticsTokens(result).includes("SUCCESS"), false);
    assert.equal(result.explanation_text.includes("optics_status=SUCCESS"), false);
    assert.equal(result.write_back, false);
  }
  assert.equal(legacy.explanation_text.includes("application_status=SUCCESS"), true);
  assert.notEqual(missing.optics_input_classes, nulled.optics_input_classes);
  assert.notEqual(nulled.optics_input_classes, unknown.optics_input_classes);
});

test("a corrupt file is OPTICS_ERROR and stays byte-identical", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-corrupt-"));
  const file = path.join(dir, "corrupt.json");
  fs.writeFileSync(file, "{");
  try {
    const before = fs.readFileSync(file);
    const result = readRunFile(file);
    const after = fs.readFileSync(file);
    assert.equal(before.equals(after), true);
    assert.equal(result.input_bytes_identical, true);
    assert.equal(result.optics_health, "OPTICS_ERROR");
    assert.equal(result.record, null);
    assert.equal(result.optics_health === "NOT_OBSERVED", false);
    assert.equal(result.optics_displayed_as_success, false);
    assert.equal(result.write_back, false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a missing path is UNAVAILABLE and is not created", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-missing-"));
  const file = path.join(dir, "absent.json");
  try {
    const result = readRunFile(file);
    assert.equal(fs.existsSync(file), false);
    assert.equal(result.optics_health, "UNAVAILABLE");
    assert.equal(result.reason_code, "ABSENT_FILE");
    assert.equal(result.record_emitted, false);
    assert.notEqual(result.optics_health, "NOT_OBSERVED");
    assert.equal(result.optics_displayed_as_success, false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("a writer option does not create or rewrite a file", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-writer-"));
  const file = path.join(dir, "run.json");
  const body = Buffer.from("{\"sealed\":true}\n");
  fs.writeFileSync(file, body);
  try {
    const result = readRunFile(file, { activate: true, write: true });
    assert.equal(fs.readFileSync(file).equals(body), true);
    assert.equal(result.writer_activated, false);
    assert.equal(result.write_back, false);
    assert.equal(result.reason_code, "WRITER_INACTIVE");
    assert.equal(result.optics_health, "OPTICS_ERROR");
    assert.equal(result.units_d_e, "NOT_AUTHORIZED");
    const missing = path.join(dir, "new.json");
    const refused = readRunFile(missing, { migrate: true, sqlite: true });
    assert.equal(fs.existsSync(missing), false);
    assert.equal(refused.writer_activated, false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("prohibited names and a secret canary are not echoed", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), CANARY + "-"));
  const file = path.join(dir, "run.json");
  const payload = {
    calls: [
      {
        action: "OBSERVED",
        hostname: "api.example.com",
        prompt: CANARY,
        status: 200,
      },
    ],
    data_note: "Developer egress data log",
    est_spend_usd: 1.5,
    plane: "data",
    residual: CANARY,
    vantio_run_log: "1",
  };
  fs.writeFileSync(file, JSON.stringify(payload));
  try {
    const before = fs.readFileSync(file);
    const result = readRunFile(file);
    const text = JSON.stringify(result);
    assert.equal(before.equals(fs.readFileSync(file)), true);
    assert.equal(text.includes(CANARY), false);
    assert.equal(text.includes("Developer egress data log"), false);
    assert.equal(text.includes("est_spend_usd"), false);
    assert.equal(text.includes("\"prompt\""), false);
    assert.equal(text.includes("\"plane\""), false);
    assert.equal(text.includes("\"residual\""), false);
    assert.equal(text.includes(dir), false);
    assert.equal(result.optics_displayed_as_success, false);
    assert.equal(result.source_name, "run.json");
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("an own getter is not invoked", () => {
  let calls = 0;
  const input = {};
  Object.defineProperty(input, "prompt", {
    enumerable: true,
    get() {
      calls += 1;
      return CANARY;
    },
  });
  const result = explainCopy(input);
  assert.equal(calls, 0);
  assert.equal(JSON.stringify(result).includes(CANARY), false);
});

test("null span and omitted span stay different", () => {
  const omitted = explainCopy({ record_type: "run_envelope" });
  const nulled = explainCopy({ record_type: "run_envelope", span_id: null });
  assert.equal(hasOwn(omitted.record, "span_id"), false);
  assert.equal(nulled.record.span_id, null);
});

test("frozen displayCall still returns SUCCESS and this reader does not", () => {
  const call = {
    hostname: "optics-demo.invalid",
    status: 200,
  };
  const frozen = displayCall(call);
  const explained = explainCopy({
    action: "OBSERVED",
    hostname: "optics-demo.invalid",
    status: 200,
  });
  assert.equal(frozen.opticsStatus, "SUCCESS");
  assert.equal(explained.record.optics_status, "UNAVAILABLE");
  assert.equal(explained.record.evidence_origin, "SIMULATED_DEMO");
  assert.equal(explained.record.application_status, "SUCCESS");
  assert.equal(explained.optics_displayed_as_success, false);
});

test("explainCopy does not open a path string", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-path-"));
  const file = path.join(dir, "run.json");
  fs.writeFileSync(file, "{\"record_type\":\"observation_event\",\"optics_status\":\"OBSERVED\"}");
  try {
    const before = fs.readFileSync(file);
    const result = explainCopy(file);
    assert.equal(fs.readFileSync(file).equals(before), true);
    assert.equal(result.record_emitted, false);
    assert.equal(result.reason_code, "PATH_REFUSED");
    const opened = readRunFile(file);
    assert.equal(opened.record.optics_status, "OBSERVED");
    assert.equal(fs.readFileSync(file).equals(before), true);
    assert.equal(opened.input_bytes_identical, true);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
