"use strict";

const i3 = require("../../../packages/optics-otel-i3/src/index.cjs");
const mapping = require("../../../packages/optics-otel-mapping/src/index.cjs");

function freezeDeep(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    for (const item of value) freezeDeep(item);
    return Object.freeze(value);
  }
  for (const key of Object.keys(value)) freezeDeep(value[key]);
  return Object.freeze(value);
}

function restState() {
  const status = i3.adapterStatus();
  const document = mapping.mappingDocument();
  const adapters = mapping.adapters();
  return freezeDeep({
    adapter_id: status.adapter_id,
    adapter_classification: status.producer_classification,
    adapter_council: status.council,
    default_enabled: status.default_enabled,
    active: status.active,
    network_on_load: status.network_on_load,
    public_shipped_support: status.public_shipped_support,
    product_otlp_export_authorized: status.product_otlp_export_authorized,
    founder_decision_12: status.founder_decision_12,
    reads_environment: status.reads_environment,
    schema_status: status.schema_status,
    schema_url: status.schema_url,
    stable_schema: status.stable_schema,
    mapping_version: status.mapping_version,
    signals: {
      otlp_traces: status.signals.otlp_traces,
      otlp_metrics: status.signals.otlp_metrics,
      otlp_logs: status.signals.otlp_logs,
    },
    mapping_id: document.mapping_id,
    i3_status: document.i3_status,
    otlp_export_authorized: document.otlp_export_authorized,
    adapters_default_enabled: document.adapters_default_enabled,
    mapping_public_shipped_support: document.public_shipped_support,
    mapping_founder_decision_12: document.founder_decision_12,
    adapters: adapters.map((adapter) => ({
      id: adapter.id,
      signal: adapter.signal,
      enabled: adapter.enabled,
      default_enabled: adapter.default_enabled,
      implementation: adapter.implementation,
    })),
  });
}

function restIsDisabled(state) {
  if (!state || state.default_enabled !== false) return false;
  if (state.active !== false) return false;
  if (state.network_on_load !== false) return false;
  if (state.public_shipped_support !== false) return false;
  if (state.product_otlp_export_authorized !== false) return false;
  if (state.founder_decision_12 !== "unresolved") return false;
  if (state.mapping_founder_decision_12 !== "unresolved") return false;
  if (state.i3_status !== "NOT_AUTHORIZED") return false;
  if (state.otlp_export_authorized !== false) return false;
  if (state.adapters_default_enabled !== false) return false;
  if (state.mapping_public_shipped_support !== false) return false;
  if (state.reads_environment !== false) return false;
  if (state.schema_url !== null) return false;
  if (state.stable_schema !== false) return false;
  if (state.signals.otlp_traces !== "EXPLICIT_ENABLE_ONLY") return false;
  if (state.signals.otlp_metrics !== "NOT_AUTHORIZED") return false;
  if (state.signals.otlp_logs !== "NOT_AUTHORIZED") return false;
  if (!Array.isArray(state.adapters) || state.adapters.length !== 3) return false;
  for (const adapter of state.adapters) {
    if (adapter.enabled !== false) return false;
    if (adapter.default_enabled !== false) return false;
  }
  return true;
}

function assertRestDisabled(state) {
  if (!restIsDisabled(state)) {
    throw new Error("REST_NOT_DISABLED");
  }
}

module.exports = {
  assertRestDisabled,
  freezeDeep,
  restIsDisabled,
  restState,
};
