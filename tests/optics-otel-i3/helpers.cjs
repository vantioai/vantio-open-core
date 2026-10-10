"use strict";

const { attestSourceRecord } = require("../../packages/optics-otel-i3/src/index.cjs");

function goodRecord(overrides) {
  return {
    source_shape: "canonical_observation",
    record_type: "observation_event",
    evidence_origin: "LOCAL_OBSERVATION",
    provider_id: "openai",
    provider_confidence: "CATALOG",
    destination_host: "api.openai.com",
    destination_port: 443,
    scheme: "https",
    method: "POST",
    path: "/v1/chat/completions",
    http_status: 200,
    application_status: "SUCCESS",
    optics_status: "UNAVAILABLE",
    request_bytes: 120,
    response_bytes: 80,
    duration_ms: 5000,
    ok: true,
    action: "OBSERVED",
    run_id: "run_1",
    trace_id: "0123456789abcdef0123456789abcdef",
    trace_id_basis: "APPLICATION_SUPPLIED",
    span_id: "0123456789abcdef",
    start_time_unix_nano: "1700000000000000000",
    end_time_unix_nano: "1700000000000000100",
    ...overrides,
  };
}

const CHAT_ATTRIBUTES = {
  "gen_ai.operation.name": "chat",
  "gen_ai.provider.name": "openai",
  "http.request.method": "POST",
  "http.response.status_code": 200,
  "server.address": "api.openai.com",
  "server.port": 443,
  "url.path": "/v1/chat/completions",
  "url.scheme": "https",
};

function assertNoLeak(assert, value, secrets) {
  const text = JSON.stringify(value);
  for (const secret of secrets) {
    assert.equal(text.includes(secret), false, secret);
  }
}

function sourceRecord(overrides) {
  const record = goodRecord(overrides);
  const attested = attestSourceRecord(record);
  if (!attested.ok) throw new Error(attested.reason || "attest failed");
  return record;
}

function traceEnable(overrides) {
  return {
    enabled: true,
    adapter: "otlp_traces",
    endpoint: "https://collector.example/v1/traces",
    transport() {
      return { status: 200 };
    },
    ...overrides,
  };
}

module.exports = {
  CHAT_ATTRIBUTES,
  assertNoLeak,
  goodRecord,
  sourceRecord,
  traceEnable,
};
