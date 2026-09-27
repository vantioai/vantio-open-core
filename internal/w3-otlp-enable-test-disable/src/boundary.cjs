"use strict";

const PRODUCER_CLASSIFICATION = "W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const STARTING_REF = "0cd36cf1d01c4db83a0a6999db0a322441f61c98";
const HARNESS_ENDPOINT = "http://127.0.0.1:9/v1/traces";

const PRODUCER = Object.freeze({
  id: "bc-620ad0a8-456f-506c-b043-dd5c6351cfe5",
  url: "https://cursor.com/agents/bc-620ad0a8-456f-506c-b043-dd5c6351cfe5",
});

const REST_FIELDS = Object.freeze({
  public_shipped_support: false,
  product_otlp_export_authorized: false,
  public_otlp_claim: false,
  otlp_export_authorized: false,
  founder_decision_12: "unresolved",
  i3_status: "NOT_AUTHORIZED",
  i3_product_authorization: "NOT_AUTHORIZED",
  default_enabled: false,
  enabled_at_rest: false,
  adapters_default_enabled: false,
  reads_environment: false,
  announced: false,
  published: false,
  host_attachment: false,
  customer_deployed: false,
  frozen_cli_reopened: false,
  python_sdk_mutated: false,
  node_sdk_mutated: false,
  metrics_authorized: false,
  logs_authorized: false,
});

const SIGNALS_AT_REST = Object.freeze({
  otlp_traces: "DISABLED",
  otlp_metrics: "NOT_AUTHORIZED",
  otlp_logs: "NOT_AUTHORIZED",
});

const HARNESS_REGISTER = Object.freeze({
  module: "internal/w3-otlp-enable-test-disable",
  package: "@vantio/w3-otlp-enable-test-disable",
  version: "0.0.0-unstable-pre-1.0",
  workspace_member: false,
  default_enabled: false,
  public_shipped_support: false,
  enable_scope: "HARNESS_CALL_ONLY",
});

const GEN_AI_HTTP_FIELDS = Object.freeze([
  "gen_ai.provider.name",
  "gen_ai.operation.name",
  "http.request.method",
  "http.response.status_code",
  "url.path",
  "url.scheme",
  "server.address",
  "server.port",
]);

const TOKEN_ATTRIBUTE_NAMES = Object.freeze([
  "gen_ai.usage.input_tokens",
  "gen_ai.usage.output_tokens",
  "gen_ai.input.messages",
  "gen_ai.output.messages",
]);

module.exports = {
  COUNCIL_STATUS,
  GEN_AI_HTTP_FIELDS,
  HARNESS_ENDPOINT,
  HARNESS_REGISTER,
  PRODUCER,
  PRODUCER_CLASSIFICATION,
  REST_FIELDS,
  SIGNALS_AT_REST,
  STARTING_REF,
  TOKEN_ATTRIBUTE_NAMES,
};
