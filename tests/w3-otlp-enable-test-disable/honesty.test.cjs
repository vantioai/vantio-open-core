"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const api = require("../../internal/w3-otlp-enable-test-disable/src/index.cjs");

const GEN_AI_HTTP = [
  "gen_ai.provider.name",
  "gen_ai.operation.name",
  "http.request.method",
  "http.response.status_code",
  "url.path",
  "url.scheme",
  "server.address",
  "server.port",
];

const TOKEN_NAMES = [
  "gen_ai.usage.input_tokens",
  "gen_ai.usage.output_tokens",
  "gen_ai.input.messages",
  "gen_ai.output.messages",
];

function attempt(report, id) {
  const found = report.attempts.find((item) => item.id === id);
  assert.ok(found, id);
  return found;
}

test("the enabled window keeps WS7 field rules and zero-byte refusals", async () => {
  const report = await api.runEnableTestDisable();
  assert.equal(report.ws7_honesty_held, true);

  const health = attempt(report, "product_health");
  assert.equal(health.reason, "NOTHING_TO_EXPORT");
  assert.equal(health.bytes_sent, 0);
  assert.equal(health.transport_calls, 0);
  assert.deepEqual(health.attribute_keys, []);
  assert.equal(health.span_client, null);
  assert.equal(health.operational_block, "ORIGIN_NOT_OPERATIONAL");
  const healthText = JSON.stringify(health);
  for (const name of GEN_AI_HTTP) assert.equal(healthText.includes(name), false, name);

  const optics = attempt(report, "optics_success");
  assert.equal(optics.span_client, null);
  assert.equal(optics.span_instrumentation, null);
  assert.equal(optics.status_code, 0);
  assert.deepEqual(optics.body_status_codes, [0]);
  assert.equal(optics.bytes_sent, optics.encoded_bytes);
  assert.ok(optics.bytes_sent > 0);

  const unset = attempt(report, "success_without_http");
  assert.equal(unset.span_client, null);
  assert.equal(unset.status_code, 0);
  assert.deepEqual(unset.body_status_codes, [0]);
  assert.equal(unset.attribute_keys.includes("http.response.status_code"), false);
  assert.equal(unset.attribute_keys.includes("gen_ai.operation.name"), true);

  const prompt = attempt(report, "prompt_completion");
  assert.equal(prompt.bytes_sent, 0);
  assert.equal(prompt.transport_calls, 0);
  assert.equal(prompt.operational_block, "PROHIBITED_INPUT_IGNORED");
  assert.deepEqual(prompt.attribute_keys, []);
  const promptText = JSON.stringify(prompt);
  for (const name of TOKEN_NAMES) assert.equal(promptText.includes(name), false, name);

  const live = attempt(report, "live_identity");
  assert.equal(live.bytes_sent, 0);
  assert.equal(live.transport_calls, 0);
  assert.equal(live.operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");
  assert.equal(live.trace_context_present, false);
  assert.equal(live.span_client, null);
  assert.deepEqual(live.attribute_keys, []);

  const mapping = attempt(report, "mapping_package_stays_disabled");
  assert.equal(mapping.reason, "ADAPTERS_DISABLED");
  assert.equal(mapping.bytes_sent, 0);
  assert.equal(mapping.network, false);
  assert.equal(mapping.adapters_enabled, false);
  assert.equal(mapping.public_shipped_support, false);

  for (const id of ["otlp_metrics", "otlp_logs"]) {
    const signal = attempt(report, id);
    assert.equal(signal.reason, "SIGNAL_NOT_AUTHORIZED");
    assert.equal(signal.enabled, false);
    assert.equal(signal.bytes_sent, 0);
    assert.equal(signal.encoded_bytes, 0);
    assert.equal(signal.transport_calls, 0);
  }

  assert.equal(report.phase, "DISABLED");
  assert.equal(report.left_disabled, true);
  assert.equal(report.public_shipped_support, false);
});
