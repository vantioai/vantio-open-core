"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { assertNoLeak, goodRecord, sourceRecord, traceEnable } = require("./helpers.cjs");

function spanRecord(n, extra) {
  return sourceRecord({
    span_id: n.toString(16).padStart(16, "0"),
    ...extra,
  });
}

test("authority does not depend on exporter availability", async () => {
  const prompt = "authority-must-ignore-this-prompt";
  const records = [
    sourceRecord(),
    goodRecord({ span_id: "0000000000000002", prompt }),
    goodRecord({ span_id: "0000000000000003", evidence_origin: "DERIVED_DIAGNOSTIC" }),
  ];
  const evaluated = api.evaluateRecords(records);
  const accepted = await api.exportOpticsRecords(records, traceEnable({
    transport() {
      return { status: 200, body: prompt };
    },
  }));
  const unavailable = await api.exportOpticsRecords(records, traceEnable({
    max_retries: 0,
    transport() {
      const error = new Error(prompt);
      throw error;
    },
  }));
  const disabled = await api.exportOpticsRecords(records, {
    enabled: false,
    endpoint: "https://collector.example/v1/traces",
    transport() {
      throw new Error("disabled transport was called");
    },
  });
  assert.deepEqual(accepted.authority, unavailable.authority);
  assert.deepEqual(accepted.eligibility, unavailable.eligibility);
  assert.deepEqual(accepted.admission, unavailable.admission);
  assert.deepEqual(accepted.drops, unavailable.drops);
  assert.deepEqual(accepted.authority, evaluated.records.map((row) => row.authority));
  assert.deepEqual(accepted.eligibility, evaluated.records.map((row) => row.eligibility));
  assert.deepEqual(disabled.authority, accepted.authority);
  assert.deepEqual(disabled.eligibility, accepted.eligibility);
  assert.equal(accepted.exported, true);
  assert.equal(accepted.delivery.outcome, "ACCEPTED");
  assert.equal(unavailable.exported, false);
  assert.equal(unavailable.reason, "EXPORTER_UNAVAILABLE");
  assert.equal(unavailable.bytes_sent, 0);
  assert.equal(unavailable.delivery.attempts, 1);
  assert.equal(unavailable.delivery.drops[0].reason, "EXPORTER_UNAVAILABLE");
  assert.equal(disabled.reason, "ADAPTER_DISABLED");
  assert.equal(disabled.bytes_sent, 0);
  assert.equal(disabled.network, false);
  assertNoLeak(assert, accepted, [prompt]);
  assertNoLeak(assert, unavailable, [prompt]);
  assertNoLeak(assert, disabled, [prompt]);
});

test("retry bounds clamp and a later success resends the same body", async () => {
  const failures = [];
  const exhausted = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: 100,
    transport() {
      failures.push("503");
      return { status: 503 };
    },
  }));
  assert.equal(failures.length, api.LIMITS.hardMaxAttempts);
  assert.equal(exhausted.delivery.attempts, 5);
  assert.equal(exhausted.delivery.max_attempts, 5);
  assert.equal(exhausted.reason, "EXPORTER_UNAVAILABLE");
  assert.equal(exhausted.bytes_sent, 0);
  assert.ok(exhausted.delivery.bytes_dropped > 0);

  const once = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: 0,
    transport() {
      return { status: 503 };
    },
  }));
  assert.equal(once.delivery.attempts, 1);

  const defaults = [];
  const defaulted = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: -1,
    transport() {
      defaults.push(1);
      return { status: 500 };
    },
  }));
  assert.equal(defaults.length, 1 + api.LIMITS.defaultMaxRetries);
  assert.equal(defaulted.reason, "EXPORTER_UNAVAILABLE");

  const bodies = [];
  let attempt = 0;
  const recovered = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: 2,
    transport(request) {
      attempt += 1;
      bodies.push(request.body);
      if (attempt < 2) return { status: 503 };
      return { status: 200 };
    },
  }));
  assert.equal(recovered.exported, true);
  assert.equal(recovered.delivery.attempts, 2);
  assert.equal(bodies[0], bodies[1]);
  assert.equal(recovered.bytes_sent, Buffer.byteLength(bodies[0]));
  assert.equal(recovered.delivery.bytes_dropped, 0);
});

test("HTTP 429 drops after the attempt cap and HTTP 400 does not retry", async () => {
  let pressure = 0;
  const limited = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: 1,
    transport() {
      pressure += 1;
      return { status: 429 };
    },
  }));
  assert.equal(pressure, 2);
  assert.equal(limited.reason, "BACKPRESSURE_EXPORTER");
  assert.equal(limited.delivery.drops[0].phase, "delivery");
  assert.equal(limited.bytes_sent, 0);

  let rejected = 0;
  const client = await api.exportOpticsRecords([sourceRecord()], traceEnable({
    max_retries: 4,
    transport() {
      rejected += 1;
      return { status: 400 };
    },
  }));
  assert.equal(rejected, 1);
  assert.equal(client.reason, "EXPORTER_REJECTED");
  assert.equal(client.delivery.attempts, 1);
});

test("queue backpressure drops later records and keeps their values out of the body", async () => {
  const note = "queued-record-must-not-leak";
  const records = [1, 2, 3, 4].map((n) => spanRecord(n, n > 2 ? { customer_note: note } : {}));
  const bodies = [];
  const result = await api.exportOpticsRecords(records, traceEnable({
    max_queue: 2,
    transport(request) {
      bodies.push(request.body);
      return { status: 200 };
    },
  }));
  assert.equal(result.exported, true);
  assert.deepEqual(result.admission.queued_indexes, [0, 1]);
  assert.equal(result.admission.limit, 2);
  const parsed = JSON.parse(bodies[0]);
  const spans = parsed.resourceSpans[0].scopeSpans[0].spans;
  assert.deepEqual(spans.map((span) => span.spanId), ["0000000000000001", "0000000000000002"]);
  assert.equal(bodies[0].includes(note), false);
  assertNoLeak(assert, result, [note]);
  const admission = result.drops.filter((drop) => drop.phase === "admission");
  assert.deepEqual(admission.map((drop) => drop.index), [2, 3]);
  assert.equal(admission[0].reason, "BACKPRESSURE_QUEUE_LIMIT");

  let calls = 0;
  const blocked = await api.exportOpticsRecords(records, traceEnable({
    max_queue: 0,
    transport() {
      calls += 1;
      return { status: 200 };
    },
  }));
  assert.equal(calls, 0);
  assert.equal(blocked.reason, "NOTHING_TO_EXPORT");
  assert.equal(blocked.admission.queued_indexes.length, 0);
  assert.equal(blocked.drops.every((drop) => drop.reason === "BACKPRESSURE_QUEUE_LIMIT"), true);

  const clamped = await api.exportOpticsRecords([sourceRecord()], traceEnable({ max_queue: 1000 }));
  assert.equal(clamped.admission.limit, api.LIMITS.hardMaxQueue);
  assert.equal(clamped.admission.clamped, true);
  assert.equal(clamped.exported, true);
});

test("the same records keep the same admission when the endpoint is rejected", async () => {
  const records = [goodRecord(), goodRecord({ span_id: "0000000000000002", evidence_origin: "IMPORTED" })];
  const sent = await api.exportOpticsRecords(records, traceEnable());
  const rejected = await api.exportOpticsRecords(records, traceEnable({
    endpoint: "https://collector.example/v1/metrics",
  }));
  assert.deepEqual(sent.authority, rejected.authority);
  assert.deepEqual(sent.eligibility, rejected.eligibility);
  assert.deepEqual(sent.admission, rejected.admission);
  assert.deepEqual(sent.drops, rejected.drops);
  assert.equal(rejected.reason, "ENDPOINT_PATH_REJECTED");
  assert.equal(rejected.network, false);
  assert.equal(rejected.delivery.endpoint_origin, null);
});
