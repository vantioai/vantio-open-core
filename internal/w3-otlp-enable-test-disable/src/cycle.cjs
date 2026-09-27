"use strict";

const i3 = require("../../../packages/optics-otel-i3/src/index.cjs");

const {
  HARNESS_ENDPOINT,
  PRODUCER_CLASSIFICATION,
} = require("./boundary.cjs");
const { runEnabledAttempts } = require("./attempts.cjs");
const { assertRestDisabled, freezeDeep, restIsDisabled, restState } = require("./rest.cjs");
const { eligibleRecord } = require("./records.cjs");

const WS7_FAILURES = new Set([
  "PRODUCT_HEALTH_FIELDS",
  "PRODUCT_HEALTH_EXPORTED",
  "OPTICS_SUCCESS_SPAN_OK",
  "SUCCESS_WITHOUT_HTTP_SPAN_OK",
  "PROMPT_COPIED",
  "TOKEN_ATTR",
  "LIVE_PROVIDER_COPIED",
  "LIVE_TRACE_COPIED",
  "LIVE_SPAN_OK",
]);

function probeSummary(id, result, calls) {
  return {
    id,
    enabled: result.enabled === true,
    exported: result.exported === true,
    reason: result.reason,
    network: result.network === true,
    bytes_sent: result.bytes_sent,
    transport_calls: calls,
    delivery_attempted: result.delivery.attempted === true,
    public_shipped_support: result.public_shipped_support === true,
    product_otlp_export_authorized: result.product_otlp_export_authorized === true,
  };
}

async function disabledProbe(id) {
  let calls = 0;
  const result = await i3.exportOpticsRecords([eligibleRecord("00000000000000c1")], {
    endpoint: HARNESS_ENDPOINT,
    adapter: "otlp_traces",
    transport() {
      calls += 1;
      return { status: 200 };
    },
  });
  return probeSummary(id, result, calls);
}

async function stringEnableProbe() {
  let calls = 0;
  const result = await i3.exportOpticsRecords([eligibleRecord("00000000000000c2")], {
    enabled: "true",
    adapter: "otlp_traces",
    endpoint: HARNESS_ENDPOINT,
    transport() {
      calls += 1;
      return { status: 200 };
    },
  });
  return probeSummary("string_enable", result, calls);
}

async function inheritedEnableProbe() {
  let calls = 0;
  const inherited = Object.create({ enabled: true, adapter: "otlp_traces" });
  inherited.endpoint = HARNESS_ENDPOINT;
  inherited.transport = () => {
    calls += 1;
    return { status: 200 };
  };
  const result = await i3.exportOpticsRecords([eligibleRecord("00000000000000c3")], inherited);
  return probeSummary("inherited_enable", result, calls);
}

function expectDisabled(failures, summary) {
  if (summary.reason !== "ADAPTER_DISABLED") failures.push(summary.id.toUpperCase() + "_REASON");
  if (summary.enabled !== false) failures.push(summary.id.toUpperCase() + "_ENABLED");
  if (summary.exported !== false) failures.push(summary.id.toUpperCase() + "_EXPORTED");
  if (summary.bytes_sent !== 0) failures.push(summary.id.toUpperCase() + "_BYTES");
  if (summary.network !== false) failures.push(summary.id.toUpperCase() + "_NETWORK");
  if (summary.transport_calls !== 0) failures.push(summary.id.toUpperCase() + "_CALLED");
  if (summary.delivery_attempted !== false) failures.push(summary.id.toUpperCase() + "_ATTEMPTED");
  if (summary.public_shipped_support !== false) failures.push(summary.id.toUpperCase() + "_PUBLIC_CLAIM");
}

async function runEnableTestDisable() {
  const failures = [];
  const before = restState();
  assertRestDisabled(before);
  const disabledBefore = await disabledProbe("disabled_before");
  expectDisabled(failures, disabledBefore);

  let phase = "ENABLED";
  let attempts = [];
  try {
    attempts = await runEnabledAttempts(failures);
  } catch {
    failures.push("UNEXPECTED");
    attempts = [];
  } finally {
    phase = "DISABLED";
  }

  const stringEnable = await stringEnableProbe();
  const inheritedEnable = await inheritedEnableProbe();
  const disabledAfter = await disabledProbe("disabled_after");
  expectDisabled(failures, stringEnable);
  expectDisabled(failures, inheritedEnable);
  expectDisabled(failures, disabledAfter);

  const after = restState();
  if (!restIsDisabled(after)) failures.push("REST_ENABLED_AFTER_CYCLE");
  if (phase !== "DISABLED") failures.push("PHASE_NOT_DISABLED");

  const ws7HonestyHeld = failures.every((code) => !WS7_FAILURES.has(code));
  const leftDisabled = phase === "DISABLED"
    && disabledAfter.reason === "ADAPTER_DISABLED"
    && disabledAfter.transport_calls === 0
    && restIsDisabled(after);

  return freezeDeep({
    ok: failures.length === 0 && leftDisabled && ws7HonestyHeld,
    producer_classification: PRODUCER_CLASSIFICATION,
    audience: "INTERNAL_RESTRICTED",
    phase,
    left_disabled: leftDisabled,
    default_enabled: after.default_enabled,
    enabled_at_rest: after.default_enabled,
    public_shipped_support: after.public_shipped_support,
    product_otlp_export_authorized: after.product_otlp_export_authorized,
    public_otlp_claim: false,
    founder_decision_12: after.founder_decision_12,
    i3_status: after.i3_status,
    i3_product_authorization: after.i3_status,
    dialed: false,
    schema_status: after.schema_status,
    schema_url: after.schema_url,
    stable_schema: after.stable_schema,
    ws7_honesty_held: ws7HonestyHeld,
    failures,
    rest_before: before,
    disabled_before: disabledBefore,
    attempts,
    string_enable: stringEnable,
    inherited_enable: inheritedEnable,
    disabled_after: disabledAfter,
    rest_after: after,
  });
}

module.exports = {
  runEnableTestDisable,
};
