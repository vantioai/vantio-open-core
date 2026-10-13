"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { CHAT_ATTRIBUTES, assertNoLeak, goodRecord, sourceRecord, traceEnable } = require("./helpers.cjs");

test("chat observation maps allowlisted fields at mapping version 0", async () => {
  const record = sourceRecord({ parent_span_id: "fedcba9876543210" });
  const snapshot = structuredClone(record);
  const bodies = [];
  const result = await api.exportOpticsRecords([record], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { status: 200 };
    },
  }));
  assert.deepEqual(record, snapshot);
  assert.equal(result.exported, true);
  assert.equal(result.reason, "ACCEPTED");
  assert.equal(result.mapping_id, "WS7-I2");
  assert.equal(result.mapping_version, 0);
  assert.equal(result.schema_status, "unstable-pre-1.0");
  assert.equal(result.schema_url, null);
  assert.deepEqual(result.authority[0].candidates, CHAT_ATTRIBUTES);
  assert.equal(result.eligibility[0].export_eligible, true);
  assert.equal(result.eligibility[0].span_name, "chat");
  assert.equal(result.eligibility[0].kind, 3);
  assert.equal(result.eligibility[0].status_code, 1);
  assert.equal(result.eligibility[0].parent_span_id, "fedcba9876543210");
  assert.equal(bodies.length, 1);
  const parsed = JSON.parse(bodies[0]);
  const span = parsed.resourceSpans[0].scopeSpans[0].spans[0];
  assert.equal(parsed.resourceSpans[0].resource.attributes.length, 0);
  assert.equal(parsed.resourceSpans[0].scopeSpans[0].scope.name, "vantio.optics.i3");
  assert.equal(span.traceId, record.trace_id);
  assert.equal(span.spanId, record.span_id);
  assert.equal(span.parentSpanId, "fedcba9876543210");
  assert.equal(span.name, "chat");
  assert.equal(span.kind, 3);
  assert.equal(span.status.code, 1);
  assert.equal(span.startTimeUnixNano, record.start_time_unix_nano);
  assert.equal(span.endTimeUnixNano, record.end_time_unix_nano);
  assert.equal(Object.hasOwn(parsed, "schemaUrl"), false);
  const keys = span.attributes.map((item) => item.key);
  assert.deepEqual(keys, Object.keys(CHAT_ATTRIBUTES).sort());
  const values = Object.fromEntries(span.attributes.map((item) => {
    const raw = item.value.stringValue != null ? item.value.stringValue : Number(item.value.intValue);
    return [item.key, raw];
  }));
  assert.deepEqual(values, CHAT_ATTRIBUTES);
  assert.equal(bodies[0].includes("gen_ai.usage"), false);
  assert.equal(bodies[0].includes("gen_ai.input"), false);
  assert.equal(bodies[0].includes("gen_ai.request.model"), false);
  assert.equal(bodies[0].includes("5000"), false);
  assert.equal(bodies[0].includes("run_1"), false);
  assertNoLeak(assert, result, ["run_1", "5000"]);
  assert.equal(result.bytes_sent, Buffer.byteLength(bodies[0]));
});

test("a record mapping_version does not replace the approved version", async () => {
  const result = await api.exportOpticsRecords([
    sourceRecord({ mapping_version: 99, schema_status: "caller-supplied-schema-label" }),
  ], traceEnable());
  assert.equal(result.mapping_version, 0);
  assert.equal(result.schema_status, "unstable-pre-1.0");
  assert.deepEqual(result.authority[0].unknown_fields, ["mapping_version", "schema_status"]);
  assert.equal(result.exported, true);
  assert.equal(JSON.stringify(result).includes("99"), false);
  assertNoLeak(assert, result, ["caller-supplied-schema-label"]);
});

test("unknown field names are listed and unknown values are not copied", async () => {
  const note = "sentence-not-for-export";
  const bodies = [];
  const result = await api.exportOpticsRecords([
    sourceRecord({ customer_note: note, internal_flag: 1 }),
  ], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { status: 200 };
    },
  }));
  assert.equal(result.eligibility[0].export_eligible, true);
  assert.deepEqual(result.authority[0].unknown_fields, ["customer_note", "internal_flag"]);
  assert.equal(bodies.length, 1);
  assert.equal(bodies[0].includes(note), false);
  assertNoLeak(assert, result, [note]);
});

test("application error maps error.type and does not read the ok boolean", async () => {
  const record = sourceRecord({
    provider_id: "anthropic",
    destination_host: "api.anthropic.com",
    path: "/v1/messages",
    http_status: 500,
    application_status: "APPLICATION_ERROR",
    ok: true,
  });
  const bodies = [];
  const result = await api.exportOpticsRecords([record], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { ok: true };
    },
  }));
  assert.equal(result.eligibility[0].status_code, 2);
  assert.equal(result.eligibility[0].kind, 3);
  assert.equal(result.eligibility[0].span_name, "gen_ai.client");
  assert.equal(result.authority[0].candidates["error.type"], "application_error");
  assert.equal(result.authority[0].candidates["http.response.status_code"], 500);
  assert.equal(result.authority[0].candidates["gen_ai.provider.name"], "anthropic");
  assert.equal(Object.hasOwn(result.authority[0].candidates, "gen_ai.operation.name"), false);
  const parsed = JSON.parse(bodies[0]);
  assert.equal(parsed.resourceSpans[0].scopeSpans[0].spans[0].status.code, 2);
  assert.equal(bodies[0].includes("\"ok\""), false);
});

test("optics error is an internal span and optics SUCCESS is not status OK", async () => {
  const opticsError = sourceRecord({
    optics_status: "OPTICS_ERROR",
    application_status: undefined,
    http_status: undefined,
    method: undefined,
    path: undefined,
    destination_port: undefined,
    scheme: undefined,
    provider_id: undefined,
    provider_confidence: undefined,
  });
  const opticsSuccess = goodRecord({ optics_status: "SUCCESS" });
  delete opticsSuccess.application_status;
  assert.equal(api.attestSourceRecord(opticsSuccess).ok, true);
  const bodies = [];
  const errored = await api.exportOpticsRecords([opticsError], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { status: 202 };
    },
  }));
  assert.equal(errored.exported, true);
  assert.equal(errored.delivery.status, 202);
  assert.equal(errored.eligibility[0].kind, 1);
  assert.equal(errored.eligibility[0].status_code, 2);
  assert.equal(errored.authority[0].candidates["error.type"], "optics_error");
  assert.equal(JSON.parse(bodies[0]).resourceSpans[0].scopeSpans[0].spans[0].kind, 1);

  const success = await api.exportOpticsRecords([opticsSuccess], traceEnable());
  assert.equal(success.eligibility[0].status_code, 0);
  assert.equal(success.authority[0].span.client, null);
  assert.equal(success.authority[0].span.instrumentation, null);
  assert.equal(Object.hasOwn(success.authority[0].candidates, "error.type"), false);
});

test("unmapped providers, string HTTP status, and query paths stay out of the body", async () => {
  const bodies = [];
  const result = await api.exportOpticsRecords([
    sourceRecord({
      provider_id: "ollama",
      http_status: "200",
      application_status: "SUCCESS",
      path: "/v1/chat/completions?api_key=path-secret",
      destination_port: undefined,
    }),
  ], traceEnable({
    transport(request) {
      bodies.push(request.body);
      return { status: 200 };
    },
  }));
  assert.equal(result.exported, true);
  assert.equal(Object.hasOwn(result.authority[0].candidates, "gen_ai.provider.name"), false);
  assert.equal(Object.hasOwn(result.authority[0].candidates, "http.response.status_code"), false);
  assert.equal(Object.hasOwn(result.authority[0].candidates, "url.path"), false);
  assert.equal(Object.hasOwn(result.authority[0].candidates, "gen_ai.operation.name"), false);
  assert.equal(Object.hasOwn(result.authority[0].candidates, "server.port"), false);
  assert.equal(result.eligibility[0].status_code, 0);
  assert.equal(bodies[0].includes("ollama"), false);
  assert.equal(bodies[0].includes("path-secret"), false);
  assertNoLeak(assert, result, ["ollama", "path-secret"]);
});

test("live display, product health, and missing trace context are not exported", async () => {
  let calls = 0;
  const live = goodRecord({
    source_shape: "live_display",
    provider: "openai",
    hostname: "api.openai.com",
    httpStatus: 200,
    applicationStatus: "SUCCESS",
    opticsStatus: "SUCCESS",
  });
  const health = goodRecord({ evidence_origin: "PRODUCT_HEALTH" });
  const demo = goodRecord({ evidence_origin: "SIMULATED_DEMO" });
  const noTrace = goodRecord();
  delete noTrace.trace_id;
  delete noTrace.span_id;
  delete noTrace.trace_id_basis;
  const result = await api.exportOpticsRecords([live, health, demo, noTrace], traceEnable({
    transport() {
      calls += 1;
      return { status: 200 };
    },
  }));
  assert.equal(calls, 0);
  assert.equal(result.reason, "NOTHING_TO_EXPORT");
  assert.equal(result.authority[0].operational, false);
  assert.equal(result.authority[0].operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");
  assert.deepEqual(result.authority[0].candidates, {});
  assert.equal(result.authority[1].operational_block, "ORIGIN_NOT_OPERATIONAL");
  assert.deepEqual(result.authority[1].candidates, {});
  assert.equal(result.authority[2].operational_block, "SIMULATED_DEMO_EXCLUDED");
  assert.equal(result.eligibility[3].reason, "TRACE_CONTEXT_NOT_ELIGIBLE");
  assert.equal(result.authority[3].operational, true);
  assert.deepEqual(result.drops.map((drop) => drop.reason), [
    "LIVE_DISPLAY_IS_NOT_PROVENANCE",
    "ORIGIN_NOT_OPERATIONAL",
    "SIMULATED_DEMO_EXCLUDED",
    "TRACE_CONTEXT_NOT_ELIGIBLE",
  ]);
});

test("simultaneous span dimensions are not collapsed", async () => {
  const result = await api.exportOpticsRecords([
    goodRecord({
      application_status: "SUCCESS",
      optics_status: "OPTICS_ERROR",
    }),
  ], traceEnable());
  assert.equal(result.exported, false);
  assert.equal(result.reason, "NOTHING_TO_EXPORT");
  assert.equal(result.authority[0].operational, true);
  assert.equal(result.authority[0].span.client, "OK");
  assert.equal(result.authority[0].span.instrumentation, "ERROR");
  assert.equal(result.eligibility[0].reason, "STATUS_DIMENSIONS_NOT_COLLAPSED");
});

test("both error classes stay a conflict and are not exported", async () => {
  const result = await api.evaluateRecords([
    goodRecord({
      http_status: 500,
      application_status: "APPLICATION_ERROR",
      optics_status: "OPTICS_ERROR",
    }),
  ]);
  assert.equal(result.records[0].authority.operational, false);
  assert.equal(result.records[0].authority.operational_block, "STATUS_DIMENSION_CONFLICT");
  assert.deepEqual(result.records[0].authority.candidates, {});
  assert.equal(result.records[0].eligibility.export_eligible, false);
});
