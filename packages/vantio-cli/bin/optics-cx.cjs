"use strict";

// Free Optics display vocabulary. Paid control-plane copy does not live here.
// JSON values are the stable tokens. Human labels are separate.

const SCHEMA_STATUS = "unstable-pre-1.0";

const VOCABULARY = Object.freeze([
  "OBSERVED",
  "NOT_OBSERVED",
  "UNSUPPORTED",
  "UNAVAILABLE",
  "APPLICATION_ERROR",
  "OPTICS_ERROR",
  "PARTIAL",
  "SUCCESS",
]);

const HUMAN = Object.freeze({
  OBSERVED: "Observed",
  NOT_OBSERVED: "Not observed",
  UNSUPPORTED: "Unsupported",
  UNAVAILABLE: "Unavailable",
  APPLICATION_ERROR: "Application error",
  OPTICS_ERROR: "Optics error",
  PARTIAL: "Partial",
  SUCCESS: "Successful",
});

const PROVIDER_SDKS = Object.freeze([
  { name: "openai", spec: "openai" },
  { name: "@anthropic-ai/sdk", spec: "@anthropic-ai/sdk" },
  { name: "@google/genai", spec: "@google/genai" },
  { name: "@google/generative-ai", spec: "@google/generative-ai" },
  { name: "cohere-ai", spec: "cohere-ai" },
  { name: "groq-sdk", spec: "groq-sdk" },
  { name: "@mistralai/mistralai", spec: "@mistralai/mistralai" },
]);

function humanStatus(token) {
  return HUMAN[token] || String(token || "Unavailable");
}

function normalizeHttpStatus(status) {
  if (status == null || status === "") return null;
  const n = typeof status === "number" ? status : Number(String(status).trim());
  if (!Number.isInteger(n)) return null;
  return n;
}

// Derive the application outcome from the raw HTTP status only.
// The stored `ok` boolean is ignored. Python 3.0.x can store ok=true on 4xx/5xx.
function applicationStatusFromHttp(status) {
  const n = normalizeHttpStatus(status);
  if (n == null) return "UNAVAILABLE";
  if (n >= 200 && n < 400) return "SUCCESS";
  if (n >= 400 && n <= 599) return "APPLICATION_ERROR";
  return "UNAVAILABLE";
}

function opticsStatusForRecordedCall() {
  return "SUCCESS";
}

function rawHttpStatus(call) {
  if (!call || typeof call !== "object") return null;
  if (call.status != null && call.status !== "") return call.status;
  if (call.httpStatus != null && call.httpStatus !== "") return call.httpStatus;
  return null;
}

function displayCall(call) {
  const src = call && typeof call === "object" ? call : {};
  const raw = rawHttpStatus(src);
  const httpStatus = normalizeHttpStatus(raw);
  const opticsStatus = opticsStatusForRecordedCall();
  const applicationStatus = applicationStatusFromHttp(raw);
  return {
    hostname: src.hostname || null,
    provider: src.provider || null,
    method: src.method || null,
    path: src.path || null,
    bytes: src.bytes ?? null,
    ts: src.ts || null,
    httpStatus,
    opticsStatus,
    applicationStatus,
    opticsLabel: humanStatus(opticsStatus),
    applicationLabel: humanStatus(applicationStatus),
  };
}

function rollupCalls(calls) {
  const list = Array.isArray(calls) ? calls : [];
  if (list.length === 0) {
    return { opticsStatus: "NOT_OBSERVED", applicationStatus: "NOT_OBSERVED" };
  }
  const apps = new Set(list.map((call) => applicationStatusFromHttp(call && call.status)));
  return {
    opticsStatus: "SUCCESS",
    applicationStatus: apps.size === 1 ? [...apps][0] : "PARTIAL",
  };
}

function telemetryPosture(env) {
  const source = env || {};
  if (source.VANTIO_TELEMETRY_DISABLED === "1" || source.DO_NOT_TRACK === "1") return "disabled";
  if (source.VANTIO_TELEMETRY === "1") return "opt-in";
  return "off";
}

function withSchema(body) {
  return Object.assign({ schema_status: SCHEMA_STATUS }, body);
}

module.exports = {
  SCHEMA_STATUS,
  VOCABULARY,
  HUMAN,
  PROVIDER_SDKS,
  humanStatus,
  normalizeHttpStatus,
  applicationStatusFromHttp,
  opticsStatusForRecordedCall,
  displayCall,
  rollupCalls,
  telemetryPosture,
  withSchema,
};
