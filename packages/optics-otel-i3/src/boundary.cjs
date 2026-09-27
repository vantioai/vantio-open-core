"use strict";

const POSTURE = Object.freeze({
  audience: "INTERNAL_RESTRICTED",
  banner: "PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA",
  adapter_id: "WS7-I3",
  producer_classification: "OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED",
  mapping_id: "WS7-I2",
  mapping_version: 0,
  schema_status: "unstable-pre-1.0",
  stable_schema: false,
  schema_url: null,
  public_shipped_support: false,
  product_otlp_export_authorized: false,
  founder_decision_12: "unresolved",
  default_enabled: false,
  reads_environment: false,
  otlp_json: true,
  otlp_protobuf: false,
  council: "PENDING_COUNCIL",
});

const LIMITS = Object.freeze({
  defaultMaxRetries: 2,
  hardMaxAttempts: 5,
  defaultMaxQueue: 8,
  hardMaxQueue: 32,
  defaultTimeoutMs: 1000,
  minTimeoutMs: 50,
  hardMaxTimeoutMs: 5000,
});

const SCOPE = Object.freeze({
  name: "vantio.optics.i3",
  version: "0.0.0-unstable-pre-1.0",
});

const SIGNALS = Object.freeze({
  otlp_traces: "EXPLICIT_ENABLE_ONLY",
  otlp_metrics: "NOT_AUTHORIZED",
  otlp_logs: "NOT_AUTHORIZED",
});

module.exports = {
  LIMITS,
  POSTURE,
  SCOPE,
  SIGNALS,
};
