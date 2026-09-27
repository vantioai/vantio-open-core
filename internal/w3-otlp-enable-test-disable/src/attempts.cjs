"use strict";

const i3 = require("../../../packages/optics-otel-i3/src/index.cjs");
const mapping = require("../../../packages/optics-otel-mapping/src/index.cjs");

const {
  GEN_AI_HTTP_FIELDS,
  HARNESS_ENDPOINT,
  TOKEN_ATTRIBUTE_NAMES,
} = require("./boundary.cjs");
const {
  COMPLETION,
  LIVE_PROVIDER,
  LIVE_TRACE_ID,
  PROMPT,
  eligibleRecord,
  liveIdentityRecord,
  opticsSuccessRecord,
  productHealthRecord,
  promptRecord,
  successWithoutHttpRecord,
} = require("./records.cjs");

function fail(failures, code, actual, expected) {
  if (actual !== expected) failures.push(code);
}

function textHas(value, secret) {
  return JSON.stringify(value).includes(secret);
}

function attributeKeys(authority) {
  if (!authority || !authority.candidates) return [];
  return Object.keys(authority.candidates).sort();
}

function statusCode(eligibility) {
  if (!eligibility || typeof eligibility.status_code !== "number") return null;
  return eligibility.status_code;
}

function bodyStatusCodes(bodies) {
  const codes = [];
  for (const body of bodies) {
    const parsed = JSON.parse(body);
    const spans = parsed.resourceSpans[0].scopeSpans[0].spans;
    for (const span of spans) codes.push(span.status.code);
  }
  return codes;
}

function encodedBytes(bodies) {
  if (bodies.length !== 1) return 0;
  return Buffer.byteLength(bodies[0]);
}

function summarize(id, result, calls, bodies) {
  const authority = result.authority && result.authority[0] ? result.authority[0] : null;
  const eligibility = result.eligibility && result.eligibility[0] ? result.eligibility[0] : null;
  return {
    id,
    enabled: result.enabled === true,
    exported: result.exported === true,
    reason: result.reason,
    network: result.network === true,
    bytes_sent: result.bytes_sent,
    bytes_dropped: result.delivery ? result.delivery.bytes_dropped : 0,
    encoded_bytes: encodedBytes(bodies),
    transport_calls: calls,
    delivery_outcome: result.delivery ? result.delivery.outcome : null,
    status: result.delivery ? result.delivery.status : null,
    attribute_keys: attributeKeys(authority),
    span_client: authority && authority.span ? authority.span.client : null,
    span_instrumentation: authority && authority.span ? authority.span.instrumentation : null,
    status_code: statusCode(eligibility),
    body_status_codes: bodyStatusCodes(bodies),
    operational: authority ? authority.operational === true : false,
    operational_block: authority ? authority.operational_block : null,
    trace_context_present: Boolean(authority && authority.trace_context),
    public_shipped_support: result.public_shipped_support === true,
    product_otlp_export_authorized: result.product_otlp_export_authorized === true,
    records_seen: result.records_seen,
  };
}

async function enabledExport(records, transport) {
  let calls = 0;
  const bodies = [];
  const result = await i3.exportOpticsRecords(records, {
    enabled: true,
    adapter: "otlp_traces",
    endpoint: HARNESS_ENDPOINT,
    max_retries: 0,
    timeout_ms: 50,
    transport(request) {
      calls += 1;
      bodies.push(request.body);
      return transport(request);
    },
  });
  return { result, calls, bodies };
}

function assertNoSecrets(failures, code, value) {
  if (textHas(value, PROMPT) || textHas(value, COMPLETION)) failures.push(code);
  if (textHas(value, LIVE_TRACE_ID) || textHas(value, LIVE_PROVIDER)) failures.push(code);
}

function assertTokenNamesAbsent(failures, value) {
  const text = JSON.stringify(value);
  for (const name of TOKEN_ATTRIBUTE_NAMES) {
    if (text.includes(name)) failures.push("TOKEN_ATTR");
  }
}

function assertSpanNotOk(failures, code, summary) {
  if (summary.span_client === "OK") failures.push(code);
  if (summary.status_code === 1) failures.push(code);
  if (summary.body_status_codes.some((item) => item === 1)) failures.push(code);
}

function assertByteHonesty(failures, summary, expectedCalls) {
  fail(failures, summary.id.toUpperCase() + "_CALLS", summary.transport_calls, expectedCalls);
  if (expectedCalls === 0) {
    fail(failures, summary.id.toUpperCase() + "_BYTES", summary.bytes_sent, 0);
    fail(failures, summary.id.toUpperCase() + "_ENCODED", summary.encoded_bytes, 0);
    return;
  }
  if (summary.encoded_bytes <= 0) failures.push(summary.id.toUpperCase() + "_ENCODED");
  if (summary.exported) {
    fail(failures, summary.id.toUpperCase() + "_BYTES", summary.bytes_sent, summary.encoded_bytes);
    fail(failures, summary.id.toUpperCase() + "_DROPPED", summary.bytes_dropped, 0);
  }
}

async function runEnabledAttempts(failures) {
  const attempts = [];
  const captured = [];

  const accepted = await enabledExport([eligibleRecord("00000000000000a1")], () => ({ status: 200 }));
  const acceptedSummary = summarize("accepted", accepted.result, accepted.calls, accepted.bodies);
  attempts.push(acceptedSummary);
  captured.push(accepted);
  fail(failures, "ACCEPTED_OUTCOME", accepted.result.reason, "ACCEPTED");
  fail(failures, "ACCEPTED_EXPORTED", accepted.result.exported, true);
  fail(failures, "ACCEPTED_CALLS", accepted.calls, 1);
  fail(failures, "ACCEPTED_BYTES", accepted.result.bytes_sent, acceptedSummary.encoded_bytes);
  fail(failures, "ACCEPTED_DROPPED", accepted.result.delivery.bytes_dropped, 0);
  if (acceptedSummary.encoded_bytes <= 0) failures.push("ACCEPTED_ZERO");
  fail(failures, "ACCEPTED_PUBLIC_CLAIM", accepted.result.public_shipped_support, false);
  fail(failures, "ACCEPTED_PRODUCT_AUTH", accepted.result.product_otlp_export_authorized, false);
  assertTokenNamesAbsent(failures, accepted.bodies[0]);
  assertNoSecrets(failures, "CROSS_LEAK", accepted.result);
  assertNoSecrets(failures, "CROSS_LEAK", accepted.bodies[0]);

  const unavailable = await enabledExport([eligibleRecord("00000000000000a2")], () => {
    throw new Error("harness-exporter-unavailable");
  });
  const unavailableSummary = summarize(
    "exporter_unavailable",
    unavailable.result,
    unavailable.calls,
    unavailable.bodies,
  );
  attempts.push(unavailableSummary);
  captured.push(unavailable);
  fail(failures, "FAILURE_OUTCOME", unavailable.result.reason, "EXPORTER_UNAVAILABLE");
  fail(failures, "FAILURE_EXPORTED", unavailable.result.exported, false);
  fail(failures, "FAILURE_CALLS", unavailable.calls, 1);
  fail(failures, "FAILURE_BYTES_SENT", unavailable.result.bytes_sent, 0);
  fail(failures, "FAILURE_BYTES_DROPPED", unavailable.result.delivery.bytes_dropped, unavailableSummary.encoded_bytes);
  if (unavailableSummary.encoded_bytes <= 0) failures.push("FAILURE_ENCODED");
  fail(failures, "FAILURE_NETWORK", unavailable.result.network, true);
  assertNoSecrets(failures, "CROSS_LEAK", unavailable.result);

  const empty = await enabledExport([], () => ({ status: 200 }));
  const emptySummary = summarize("nothing_to_export", empty.result, empty.calls, empty.bodies);
  attempts.push(emptySummary);
  captured.push(empty);
  fail(failures, "NOTHING_REASON", empty.result.reason, "NOTHING_TO_EXPORT");
  fail(failures, "NOTHING_EXPORTED", empty.result.exported, false);
  fail(failures, "NOTHING_CALLS", empty.calls, 0);
  fail(failures, "NOTHING_BYTES", empty.result.bytes_sent, 0);
  fail(failures, "NOTHING_NETWORK", empty.result.network, false);
  fail(failures, "NOTHING_ENABLED", empty.result.enabled, true);

  const health = await enabledExport([productHealthRecord()], () => ({ status: 200 }));
  const healthSummary = summarize("product_health", health.result, health.calls, health.bodies);
  attempts.push(healthSummary);
  captured.push(health);
  fail(failures, "PRODUCT_HEALTH_EXPORTED", health.result.reason, "NOTHING_TO_EXPORT");
  fail(failures, "PRODUCT_HEALTH_CALLS", health.calls, 0);
  fail(failures, "PRODUCT_HEALTH_BYTES", health.result.bytes_sent, 0);
  fail(failures, "PRODUCT_HEALTH_BLOCK", health.result.authority[0].operational_block, "ORIGIN_NOT_OPERATIONAL");
  fail(failures, "PRODUCT_HEALTH_CLIENT", health.result.authority[0].span.client, null);
  if (healthSummary.attribute_keys.length !== 0) failures.push("PRODUCT_HEALTH_FIELDS");
  const healthText = JSON.stringify(health.result);
  for (const name of GEN_AI_HTTP_FIELDS) {
    if (healthText.includes(name)) failures.push("PRODUCT_HEALTH_FIELDS");
  }
  if (healthText.includes("api.openai.com")) failures.push("PRODUCT_HEALTH_FIELDS");
  assertNoSecrets(failures, "CROSS_LEAK", health.result);

  const optics = await enabledExport([opticsSuccessRecord()], () => ({ status: 200 }));
  const opticsSummary = summarize("optics_success", optics.result, optics.calls, optics.bodies);
  attempts.push(opticsSummary);
  captured.push(optics);
  assertByteHonesty(failures, opticsSummary, 1);
  assertSpanNotOk(failures, "OPTICS_SUCCESS_SPAN_OK", opticsSummary);
  fail(failures, "OPTICS_SUCCESS_STATUS", opticsSummary.status_code, 0);
  fail(failures, "OPTICS_SUCCESS_CLIENT", opticsSummary.span_client, null);
  if (opticsSummary.body_status_codes.length !== 1 || opticsSummary.body_status_codes[0] !== 0) {
    failures.push("OPTICS_SUCCESS_SPAN_OK");
  }
  assertTokenNamesAbsent(failures, optics.bodies[0]);

  const unset = await enabledExport([successWithoutHttpRecord()], () => ({ status: 200 }));
  const unsetSummary = summarize("success_without_http", unset.result, unset.calls, unset.bodies);
  attempts.push(unsetSummary);
  captured.push(unset);
  assertByteHonesty(failures, unsetSummary, 1);
  assertSpanNotOk(failures, "SUCCESS_WITHOUT_HTTP_SPAN_OK", unsetSummary);
  fail(failures, "SUCCESS_WITHOUT_HTTP_STATUS", unsetSummary.status_code, 0);
  if (unsetSummary.attribute_keys.includes("http.response.status_code")) {
    failures.push("SUCCESS_WITHOUT_HTTP_SPAN_OK");
  }

  const prompt = await enabledExport([promptRecord()], () => ({ status: 200 }));
  const promptSummary = summarize("prompt_completion", prompt.result, prompt.calls, prompt.bodies);
  attempts.push(promptSummary);
  captured.push(prompt);
  fail(failures, "PROMPT_REASON", prompt.result.reason, "NOTHING_TO_EXPORT");
  fail(failures, "PROMPT_CALLS", prompt.calls, 0);
  fail(failures, "PROMPT_BYTES", prompt.result.bytes_sent, 0);
  fail(failures, "PROMPT_BLOCK", prompt.result.authority[0].operational_block, "PROHIBITED_INPUT_IGNORED");
  if (textHas(prompt.result, PROMPT) || textHas(prompt.result, COMPLETION)) failures.push("PROMPT_COPIED");
  assertTokenNamesAbsent(failures, prompt.result);
  if (promptSummary.attribute_keys.some((key) => TOKEN_ATTRIBUTE_NAMES.includes(key))) {
    failures.push("TOKEN_ATTR");
  }

  const live = await enabledExport([liveIdentityRecord()], () => ({ status: 200 }));
  const liveSummary = summarize("live_identity", live.result, live.calls, live.bodies);
  attempts.push(liveSummary);
  captured.push(live);
  fail(failures, "LIVE_REASON", live.result.reason, "NOTHING_TO_EXPORT");
  fail(failures, "LIVE_CALLS", live.calls, 0);
  fail(failures, "LIVE_BYTES", live.result.bytes_sent, 0);
  fail(failures, "LIVE_BLOCK", live.result.authority[0].operational_block, "LIVE_DISPLAY_IS_NOT_PROVENANCE");
  fail(failures, "LIVE_CLIENT", live.result.authority[0].span.client, null);
  fail(failures, "LIVE_TRACE_PRESENT", live.result.authority[0].trace_context, null);
  if (liveSummary.attribute_keys.length !== 0) failures.push("LIVE_PROVIDER_COPIED");
  if (textHas(live.result, LIVE_TRACE_ID)) failures.push("LIVE_TRACE_COPIED");
  if (textHas(live.result, LIVE_PROVIDER)) failures.push("LIVE_PROVIDER_COPIED");
  if (liveSummary.span_client === "OK" || liveSummary.status_code === 1) failures.push("LIVE_SPAN_OK");

  const mappingResult = mapping.exportOpticsRecords([eligibleRecord("00000000000000d1")], {
    enabled: true,
    adapter: "otlp_traces",
    endpoint: HARNESS_ENDPOINT,
  });
  const mappingSummary = {
    id: "mapping_package_stays_disabled",
    enabled: false,
    exported: mappingResult.exported === true,
    reason: mappingResult.reason,
    network: mappingResult.network === true,
    bytes_sent: mappingResult.bytes_sent,
    bytes_dropped: 0,
    encoded_bytes: 0,
    transport_calls: 0,
    delivery_outcome: null,
    status: null,
    attribute_keys: [],
    span_client: null,
    span_instrumentation: null,
    status_code: null,
    body_status_codes: [],
    operational: false,
    operational_block: null,
    trace_context_present: false,
    public_shipped_support: false,
    product_otlp_export_authorized: false,
    records_seen: mappingResult.records_seen,
    adapters_enabled: mappingResult.adapters.some((adapter) => adapter.enabled === true),
  };
  attempts.push(mappingSummary);
  fail(failures, "MAPPING_REASON", mappingResult.reason, "ADAPTERS_DISABLED");
  fail(failures, "MAPPING_BYTES", mappingResult.bytes_sent, 0);
  fail(failures, "MAPPING_NETWORK", mappingResult.network, false);
  if (mappingSummary.adapters_enabled) failures.push("MAPPING_ENABLED");
  if (textHas(mappingResult, PROMPT)) failures.push("PROMPT_COPIED");
  if (mapping.mappingDocument().i3_status !== "NOT_AUTHORIZED") failures.push("MAPPING_I3_STATUS");
  if (mapping.mappingDocument().public_shipped_support !== false) failures.push("MAPPING_PUBLIC_CLAIM");

  for (const adapter of ["otlp_metrics", "otlp_logs"]) {
    let calls = 0;
    const result = await i3.exportOpticsRecords([eligibleRecord("00000000000000d2")], {
      enabled: true,
      adapter,
      endpoint: HARNESS_ENDPOINT,
      transport() {
        calls += 1;
        return { status: 200 };
      },
    });
    const summary = summarize(adapter, result, calls, []);
    attempts.push(summary);
    fail(failures, adapter.toUpperCase() + "_REASON", result.reason, "SIGNAL_NOT_AUTHORIZED");
    fail(failures, adapter.toUpperCase() + "_ENABLED", result.enabled, false);
    fail(failures, adapter.toUpperCase() + "_BYTES", result.bytes_sent, 0);
    fail(failures, adapter.toUpperCase() + "_CALLS", calls, 0);
  }

  for (const item of captured) {
    assertNoSecrets(failures, "CROSS_LEAK", item.result);
    for (const body of item.bodies) assertNoSecrets(failures, "CROSS_LEAK", body);
  }

  return attempts;
}

module.exports = {
  runEnabledAttempts,
};
