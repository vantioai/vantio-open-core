"use strict";

const PROMPT = "w3-otlp-cycle-prompt-must-stay-out";
const COMPLETION = "w3-otlp-cycle-completion-must-stay-out";
const LIVE_PROVIDER = "live-provider-not-for-otel";
const LIVE_TRACE_ID = "abcdef0123456789abcdef0123456789";
const ELIGIBLE_TRACE_ID = "0123456789abcdef0123456789abcdef";

function eligibleRecord(spanId) {
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
    trace_id: ELIGIBLE_TRACE_ID,
    trace_id_basis: "APPLICATION_SUPPLIED",
    span_id: spanId,
    start_time_unix_nano: "1700000000000000000",
    end_time_unix_nano: "1700000000000000100",
  };
}

function productHealthRecord() {
  return {
    ...eligibleRecord("00000000000000b2"),
    evidence_origin: "PRODUCT_HEALTH",
  };
}

function opticsSuccessRecord() {
  const record = eligibleRecord("00000000000000a3");
  record.optics_status = "SUCCESS";
  delete record.application_status;
  return record;
}

function successWithoutHttpRecord() {
  const record = eligibleRecord("00000000000000a4");
  delete record.http_status;
  return record;
}

function promptRecord() {
  return {
    ...eligibleRecord("00000000000000b1"),
    prompt: PROMPT,
    completion: COMPLETION,
  };
}

function liveIdentityRecord() {
  return {
    source_shape: "live_display",
    provider: LIVE_PROVIDER,
    hostname: "api.openai.com",
    method: "POST",
    path: "/v1/chat/completions",
    httpStatus: 200,
    applicationStatus: "SUCCESS",
    opticsStatus: "SUCCESS",
    trace_id: LIVE_TRACE_ID,
    trace_id_basis: "APPLICATION_SUPPLIED",
    span_id: "fedcba9876543210",
    start_time_unix_nano: "1700000000000000000",
    end_time_unix_nano: "1700000000000000100",
  };
}

module.exports = {
  COMPLETION,
  ELIGIBLE_TRACE_ID,
  LIVE_PROVIDER,
  LIVE_TRACE_ID,
  PROMPT,
  eligibleRecord,
  liveIdentityRecord,
  opticsSuccessRecord,
  productHealthRecord,
  promptRecord,
  successWithoutHttpRecord,
};
