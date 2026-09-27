"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { displayCall } = require("../../packages/vantio-cli/bin/optics-cx.cjs");
const { adaptNodeCopy } = require("../../packages/optics-node-adapter/src/adapt.cjs");

const ROOT = path.resolve(__dirname, "../..");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

test("a frozen CLI display still says SUCCESS and the adapter does not", () => {
  const call = { hostname: "api.example.com", status: 200 };
  const shown = displayCall(call);
  assert.equal(shown.opticsStatus, "SUCCESS");
  const adapted = adaptNodeCopy({ vantio_run_log: "1", schema_version: 2, calls: [call] });
  assert.equal(adapted.events[0].record.optics_status, "UNAVAILABLE");
  assert.equal(adapted.writer_activated, false);
});

test("explicit optics SUCCESS is refused on the detached copy", () => {
  const result = adaptNodeCopy({
    http_status: 200,
    optics_status: "SUCCESS",
    record_type: "observation_event",
  });
  assert.equal(result.record.optics_status, "UNAVAILABLE");
  assert.equal(result.optimistic_default_forbidden, true);
  assert.equal(result.record.application_status, "SUCCESS");
});

test("prohibited values are absent from the detached result", () => {
  const canary = "sk-CANARYUNITB0001";
  const result = adaptNodeCopy({
    calls: [{ hostname: "api.example.com", prompt: canary, status: 200 }],
    data_note: "Developer egress data log " + canary,
    est_spend_usd: 3,
    plane: "optics",
    residual: { note: canary },
    vantio_run_log: "1",
  });
  const text = JSON.stringify(result);
  assert.equal(text.includes(canary), false);
  assert.equal(text.includes("Developer egress"), false);
  assert.equal(result.events.length, 0);
  assert.notEqual(result.optics_health, "SUCCESS");
  assert.equal(result.record == null || result.record.prompt === undefined, true);
});

test("an enforcement action is not stored and is not optics success", () => {
  const result = adaptNodeCopy({
    calls: [{ action: "BLOCKED_EGRESS", hostname: "api.example.com", status: 200 }],
    vantio_run_log: "1",
  });
  assert.equal(JSON.stringify(result).includes("BLOCKED_EGRESS"), false);
  assert.notEqual(result.optics_health, "SUCCESS");
  assert.equal(result.events.length, 0);
});

test("sixty-five calls are a bound, not the first sixty-four", () => {
  const calls = [];
  for (let i = 0; i < 65; i += 1) calls.push({ status: 204 });
  const result = adaptNodeCopy({ calls, vantio_run_log: "1" });
  assert.equal(result.reason_code, "INPUT_BOUND");
  assert.equal(result.record, null);
  assert.equal(result.events.length, 0);
  assert.notEqual(result.optics_health, "SUCCESS");
});

test("a mutating getter is not called", () => {
  let reads = 0;
  const input = {};
  Object.defineProperty(input, "calls", {
    enumerable: true,
    get() {
      reads += 1;
      return [{ status: 200 }];
    },
  });
  const result = adaptNodeCopy(input);
  assert.equal(reads, 0);
  assert.equal(result.record, null);
  assert.equal(result.events.length, 0);
});

test("an inherited accessor is not called", () => {
  let reads = 0;
  const proto = {};
  Object.defineProperty(proto, "calls", {
    enumerable: true,
    get() {
      reads += 1;
      return [{ prompt: "CANARYINHERITED", status: 200 }];
    },
  });
  const input = Object.create(proto);
  input.vantio_run_log = "1";
  const result = adaptNodeCopy(input);
  assert.equal(reads, 0);
  assert.equal(JSON.stringify(result).includes("CANARYINHERITED"), false);
  assert.equal(result.record, null);
  assert.equal(result.events.length, 0);
  assert.equal(result.reason_code, "ACCESSOR_PROPERTY_FORBIDDEN");
});

test("an inherited accessor on a call is not called", () => {
  let reads = 0;
  const callProto = {};
  Object.defineProperty(callProto, "duration_ms", {
    enumerable: true,
    get() {
      reads += 1;
      return 0;
    },
  });
  Object.defineProperty(callProto, "status", {
    enumerable: true,
    get() {
      reads += 1;
      return null;
    },
  });
  const call = Object.create(callProto);
  call.hostname = "api.example.com";
  const result = adaptNodeCopy({ calls: [call], vantio_run_log: "1" });
  assert.equal(reads, 0);
  assert.equal(result.record, null);
  assert.equal(result.events.length, 0);
  assert.equal(result.reason_code, "ACCESSOR_PROPERTY_FORBIDDEN");
});

function projection(result) {
  return {
    events: result.events.map((event) => event.record),
    forbidden: result.optimistic_default_forbidden,
    health: result.optics_health,
    record: result.record,
  };
}

test("text and byte copies follow the same Unit A snapshot rules as objects", () => {
  const samples = [
    {
      calls: [{ sampling: "SAMPLED", status: 200 }],
      vantio_run_log: "1",
    },
    {
      calls: [{ method: "FLY", status: 204 }],
      vantio_run_log: "1",
    },
    {
      calls: [{ duration_ms: 0, status: null }],
      vantio_run_log: "1",
    },
    {
      record_type: "run_envelope",
      span_id: null,
    },
    {
      evidence_origin: "IMPORTED",
      original_evidence_origin: "LEGACY_UNMARKED",
      record_type: "run_envelope",
    },
    {
      http_status: 204,
      optics_status: "SUPER_SUCCESS",
      record_type: "observation_event",
    },
    {
      calls: [],
      generated_at: "2026-07-01T00:00:00.000Z",
      schema_version: 2,
      trace_id: "0xcliempty",
      vantio_run_log: "1",
    },
  ];
  for (const sample of samples) {
    const text = JSON.stringify(sample);
    const objectResult = adaptNodeCopy(sample);
    const textResult = adaptNodeCopy(text);
    const bytesResult = adaptNodeCopy(Buffer.from(text));
    assert.deepEqual(projection(textResult), projection(objectResult));
    assert.deepEqual(projection(bytesResult), projection(objectResult));
  }

  const sampled = adaptNodeCopy(JSON.stringify(samples[0]));
  assert.equal(hasOwn(sampled.events[0].record, "sampling"), false);
  assert.notEqual(sampled.events[0].record.sampling, "UNSAMPLED");

  const fly = adaptNodeCopy(Buffer.from(JSON.stringify(samples[1])));
  assert.equal(hasOwn(fly.events[0].record, "method"), false);
  assert.notEqual(fly.events[0].record.method, "unknown");

  const pre = adaptNodeCopy(JSON.stringify(samples[2]));
  assert.equal(pre.events[0].record.lifecycle, "INTERRUPTED");
  assert.equal(hasOwn(pre.events[0].record, "duration_ms"), false);

  const span = adaptNodeCopy(Buffer.from(JSON.stringify(samples[3])));
  assert.equal(span.record.span_id, null);

  const imported = adaptNodeCopy(JSON.stringify(samples[4]));
  assert.equal(imported.record.evidence_origin, "IMPORTED");
  assert.equal(imported.record.original_evidence_origin, "LEGACY_UNMARKED");
  assert.notEqual(imported.record.evidence_origin, "LEGACY_UNMARKED");

  const unknown = adaptNodeCopy(Buffer.from(JSON.stringify(samples[5])));
  assert.equal(unknown.record.optics_status, "UNAVAILABLE");
  assert.equal(unknown.optimistic_default_forbidden, true);

  const empty = adaptNodeCopy(JSON.stringify(samples[6]));
  assert.equal(empty.optics_health, "NOT_OBSERVED");
  assert.equal(empty.record.trace_id_basis, "ASSERTED_CONTEXT");
  assert.equal(empty.record.optics_status, "NOT_OBSERVED");
});

test("a filesystem path is not opened", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "unit-b-path-"));
  const file = path.join(directory, "run.json");
  const body = '{"prompt":"PATHCANARYVALUE"}\n';
  fs.writeFileSync(file, body);
  try {
    const result = adaptNodeCopy(file);
    assert.equal(fs.readFileSync(file, "utf8"), body);
    assert.equal(JSON.stringify(result).includes("PATHCANARYVALUE"), false);
    assert.equal(result.adapter_disposition, "PATH_REFUSED");
    assert.equal(result.writer_activated, false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("writer options do not create a file", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "unit-b-write-"));
  const file = path.join(directory, "out.json");
  try {
    const result = adaptNodeCopy({ calls: [], vantio_run_log: "1" }, { path: file, write: true });
    assert.equal(result.adapter_disposition, "WRITER_INACTIVE");
    assert.equal(result.writer_activated, false);
    assert.equal(fs.existsSync(file), false);
  } finally {
    fs.rmSync(directory, { recursive: true, force: true });
  }
});

test("the caller object is not retained", () => {
  const input = {
    calls: [{ bytes: 4, hostname: "api.example.com", status: 200 }],
    vantio_run_log: "1",
  };
  const result = adaptNodeCopy(input);
  input.calls[0].status = 500;
  input.calls[0].prompt = "MUTATIONCANARY";
  assert.equal(result.events[0].record.http_status, 200);
  assert.equal(JSON.stringify(result).includes("MUTATIONCANARY"), false);
});

test("a validator rejection leaves the application result unchanged", () => {
  const application = { ticket: "APP-7" };
  const result = adaptNodeCopy("{not-json", { applicationResult: application });
  assert.equal(result.optics_health, "OPTICS_ERROR");
  assert.equal(result.record, null);
  assert.equal(result.application_result.ticket, "APP-7");
  application.ticket = "CHANGED";
  assert.equal(result.application_result.ticket, "APP-7");
});

test("an oversized session is omitted rather than truncated", () => {
  const marker = "MARKERSESSION";
  const result = adaptNodeCopy({
    http_status: 204,
    record_type: "observation_event",
    session_id: marker + "A".repeat(80),
    session_id_basis: "CALLER",
  });
  assert.equal(JSON.stringify(result).includes(marker), false);
  assert.equal(result.record && hasOwn(result.record, "session_id"), false);
});

test("a non-zero timestamp offset is not converted", () => {
  const result = adaptNodeCopy({
    http_status: 204,
    record_type: "observation_event",
    started_at: "2026-07-01T00:00:00.000+05:00",
  });
  assert.notEqual(result.record && result.record.started_at, "2026-06-30T19:00:00.000Z");
  assert.equal(result.record && hasOwn(result.record, "started_at"), false);
});

test("null span and omitted span stay different", () => {
  const omittedObject = { record_type: "run_envelope" };
  const nulledObject = { record_type: "run_envelope", span_id: null };
  const copies = [
    omittedObject,
    JSON.stringify(omittedObject),
    Buffer.from(JSON.stringify(omittedObject)),
  ];
  const nulledCopies = [
    nulledObject,
    JSON.stringify(nulledObject),
    Buffer.from(JSON.stringify(nulledObject)),
  ];
  for (const copy of copies) {
    assert.equal(hasOwn(adaptNodeCopy(copy).record, "span_id"), false);
  }
  for (const copy of nulledCopies) {
    assert.equal(adaptNodeCopy(copy).record.span_id, null);
  }
});

test("a real CLI 0.3.24 run file is byte-identical with the adapter present", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "unit-b-home-"));
  const runs = path.join(home, ".vantio", "runs");
  try {
    const child = spawnSync(process.execPath, [
      path.join(ROOT, "packages/vantio-cli/bin/vantio.js"),
      "run",
      "node",
      "-e",
      "process.exit(0)",
    ], {
      cwd: home,
      encoding: "utf8",
      env: Object.assign({}, process.env, { HOME: home, VANTIO_HOME: path.join(home, ".vantio") }),
    });
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const files = fs.readdirSync(runs).filter((name) => name.endsWith(".json"));
    assert.equal(files.length, 1);
    const file = path.join(runs, files[0]);
    const before = fs.readFileSync(file);
    const beforeHash = crypto.createHash("sha256").update(before).digest("hex");
    const parsed = JSON.parse(before.toString("utf8"));
    const adapted = adaptNodeCopy(parsed);
    const asText = adaptNodeCopy(before.toString("utf8"));
    const asBytes = adaptNodeCopy(Buffer.from(before));
    const after = fs.readFileSync(file);
    const afterHash = crypto.createHash("sha256").update(after).digest("hex");
    assert.equal(afterHash, beforeHash);
    assert.equal(before.equals(after), true);
    assert.equal(adapted.live_writer_modified, false);
    assert.equal(adapted.writes_live_run_directory, false);
    const text = JSON.stringify(adapted);
    assert.equal(text.includes("Developer egress data log"), false);
    assert.equal(text.includes("est_spend_usd"), false);
    assert.equal(parsed.schema_version, 2);
    assert.equal(adapted.compatibility.legacy_schema_version, 2);
    assert.equal(adapted.schema_version, 0);
    assert.equal(adapted.optics_health, "NOT_OBSERVED");
    assert.equal(adapted.record.trace_id_basis, "ASSERTED_CONTEXT");
    assert.equal(adapted.record.optics_status, "NOT_OBSERVED");
    assert.deepEqual(projection(asText), projection(adapted));
    assert.deepEqual(projection(asBytes), projection(adapted));
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
