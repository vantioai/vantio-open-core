"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../internal/w3-otlp-enable-test-disable/src/index.cjs");
const { COMPLETION, LIVE_PROVIDER, LIVE_TRACE_ID, PROMPT } = require("../../internal/w3-otlp-enable-test-disable/src/records.cjs");

const CHAT_KEYS = [
  "gen_ai.operation.name",
  "gen_ai.provider.name",
  "http.request.method",
  "http.response.status_code",
  "server.address",
  "server.port",
  "url.path",
  "url.scheme",
];

function attempt(report, id) {
  const found = report.attempts.find((item) => item.id === id);
  assert.ok(found, id);
  return found;
}

function assertDisabledProbe(summary) {
  assert.equal(summary.enabled, false);
  assert.equal(summary.exported, false);
  assert.equal(summary.reason, "ADAPTER_DISABLED");
  assert.equal(summary.network, false);
  assert.equal(summary.bytes_sent, 0);
  assert.equal(summary.transport_calls, 0);
  assert.equal(summary.delivery_attempted, false);
  assert.equal(summary.public_shipped_support, false);
  assert.equal(summary.product_otlp_export_authorized, false);
}

test("one cycle enables, records attempts, and finishes disabled", async () => {
  const report = await api.runEnableTestDisable({
    enabled: true,
    endpoint: "https://collector.example/v1/traces",
  });
  assert.equal(report.ok, true);
  assert.deepEqual(report.failures, []);
  assert.equal(report.producer_classification, "W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL");
  assert.equal(report.phase, "DISABLED");
  assert.equal(report.left_disabled, true);
  assert.equal(report.default_enabled, false);
  assert.equal(report.enabled_at_rest, false);
  assert.equal(report.public_shipped_support, false);
  assert.equal(report.product_otlp_export_authorized, false);
  assert.equal(report.public_otlp_claim, false);
  assert.equal(report.founder_decision_12, "unresolved");
  assert.equal(report.i3_status, "NOT_AUTHORIZED");
  assert.equal(report.i3_product_authorization, "NOT_AUTHORIZED");
  assert.equal(report.dialed, false);
  assert.equal(report.schema_status, "unstable-pre-1.0");
  assert.equal(report.schema_url, null);
  assert.equal(report.stable_schema, false);
  assert.equal(report.ws7_honesty_held, true);
  assert.equal(report.rest_before.default_enabled, false);
  assert.equal(report.rest_after.default_enabled, false);
  assert.equal(report.rest_after.i3_status, "NOT_AUTHORIZED");
  assert.equal(report.rest_after.active, false);
  assert.equal(report.rest_after.adapters.every((item) => item.enabled === false), true);
  assertDisabledProbe(report.disabled_before);
  assertDisabledProbe(report.disabled_after);
  assertDisabledProbe(report.string_enable);
  assertDisabledProbe(report.inherited_enable);

  const accepted = attempt(report, "accepted");
  assert.equal(accepted.exported, true);
  assert.equal(accepted.reason, "ACCEPTED");
  assert.equal(accepted.enabled, true);
  assert.equal(accepted.transport_calls, 1);
  assert.ok(accepted.encoded_bytes > 0);
  assert.equal(accepted.bytes_sent, accepted.encoded_bytes);
  assert.equal(accepted.bytes_dropped, 0);
  assert.equal(accepted.public_shipped_support, false);
  assert.deepEqual(accepted.attribute_keys, CHAT_KEYS);
  assert.equal(accepted.status_code, 1);
  assert.deepEqual(accepted.body_status_codes, [1]);

  const unavailable = attempt(report, "exporter_unavailable");
  assert.equal(unavailable.exported, false);
  assert.equal(unavailable.reason, "EXPORTER_UNAVAILABLE");
  assert.equal(unavailable.bytes_sent, 0);
  assert.ok(unavailable.encoded_bytes > 0);
  assert.equal(unavailable.bytes_dropped, unavailable.encoded_bytes);
  assert.equal(unavailable.transport_calls, 1);
  assert.equal(unavailable.network, true);

  const empty = attempt(report, "nothing_to_export");
  assert.equal(empty.reason, "NOTHING_TO_EXPORT");
  assert.equal(empty.bytes_sent, 0);
  assert.equal(empty.encoded_bytes, 0);
  assert.equal(empty.transport_calls, 0);
  assert.equal(empty.network, false);
  assert.equal(empty.enabled, true);

  const text = JSON.stringify(report);
  assert.equal(text.includes(PROMPT), false);
  assert.equal(text.includes(COMPLETION), false);
  assert.equal(text.includes(LIVE_PROVIDER), false);
  assert.equal(text.includes(LIVE_TRACE_ID), false);
  assert.equal(text.includes("collector.example"), false);
});

test("a second cycle still starts and ends disabled", async () => {
  const first = await api.runEnableTestDisable();
  const second = await api.runEnableTestDisable();
  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.equal(second.disabled_before.transport_calls, 0);
  assert.equal(second.disabled_after.reason, "ADAPTER_DISABLED");
  assert.equal(api.restState().default_enabled, false);
  assert.equal(api.restState().active, false);
  assert.equal(api.REST_REGISTER.enabled_at_rest, false);
  assert.equal(api.REST_REGISTER.default_enabled, false);
  assert.equal(api.REST_REGISTER.public_shipped_support, false);
  assert.equal(api.REST_REGISTER.public_otlp_claim, false);
  assert.equal(api.REST_REGISTER.i3_product_authorization, "NOT_AUTHORIZED");
  assert.equal(api.REST_REGISTER.signals_at_rest.otlp_traces, "DISABLED");
});
