"use strict";

const POSTURE = Object.freeze({
  audience: "INTERNAL_RESTRICTED",
  banner: "PRIVATE | INERT | NOT SHIPPED | ADAPTERS DISABLED | NO OTLP EXPORTER | NO STABLE SCHEMA",
  mapping_id: "WS7-I2",
  mapping_version: 0,
  schema_status: "unstable-pre-1.0",
  stable_schema: false,
  public_shipped_support: false,
  otlp_export_authorized: false,
  adapters_default_enabled: false,
  i3_status: "NOT_AUTHORIZED",
  founder_decision_12: "unresolved",
  producer_classification: "OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL",
});

module.exports = { POSTURE };
