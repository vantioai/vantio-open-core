"use strict";

const KNOWN_FIELDS = new Set([
  "source_shape",
  "record_type",
  "evidence_origin",
  "provider",
  "provider_id",
  "provider_confidence",
  "destination_host",
  "destination_port",
  "hostname",
  "scheme",
  "method",
  "path",
  "http_status",
  "httpStatus",
  "application_status",
  "applicationStatus",
  "optics_status",
  "opticsStatus",
  "request_bytes",
  "response_bytes",
  "bytes",
  "duration_ms",
  "trace_id",
  "trace_id_basis",
  "span_id",
  "parent_span_id",
  "run_id",
  "session_id",
  "process_id",
  "ok",
  "action",
  "calls",
  "clock_quality",
  "start_time_unix_nano",
  "end_time_unix_nano",
]);

const UNSAFE_KEYS = new Set(["__proto__", "constructor", "prototype"]);

const CONTENT_EXACT = new Set([
  "prompt",
  "prompts",
  "completion",
  "completions",
  "message",
  "messages",
  "body",
  "request_body",
  "response_body",
  "customer_content",
  "system_instructions",
]);

const CREDENTIAL_EXACT = new Set([
  "password",
  "passwd",
  "secret",
  "api_key",
  "apikey",
  "token",
  "access_token",
  "refresh_token",
  "id_token",
  "credential",
  "credentials",
  "cookie",
  "set_cookie",
  "setcookie",
  "authorization",
  "proxy_authorization",
  "private_key",
  "headers",
  "header",
  "baggage",
  "tracestate",
  "trace_state",
  "env",
  "environment",
  "environ",
]);

const KERNEL_EXACT = new Set([
  "kernel",
  "ebpf",
  "bpf",
  "uprobe",
  "kprobe",
  "ssl_write",
  "gnutls",
  "gnutls_record_send",
  "phantom",
  "tc_act",
  "verifier",
]);

const COMPANY_EXACT = new Set([
  "revenue",
  "arr",
  "pipeline",
  "hubspot",
  "sdr",
  "quota",
  "payroll",
  "invoice",
  "mrr",
]);

const PROOF_EXACT = new Set([
  "proof",
  "slsa",
  "attestation",
  "zk_proof",
  "proof_json",
  "cluster_verified",
  "production_verified",
  "merkle",
]);

const CREDENTIAL_OPTION_KEYS = new Set([
  "headers",
  "authorization",
  "apiKey",
  "api_key",
  "token",
  "password",
  "secret",
  "credentials",
]);

function normalizeName(name) {
  return String(name).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

function safeFieldName(name) {
  if (typeof name !== "string") return null;
  if (UNSAFE_KEYS.has(name)) return null;
  if (name.length < 1 || name.length > 64) return null;
  if (!/^[A-Za-z0-9_.-]+$/.test(name)) return null;
  return name;
}

function blockingReason(name) {
  const normalized = normalizeName(name);
  if (!normalized) return "PROHIBITED_CONTENT";
  const parts = new Set(normalized.split("_").filter(Boolean));
  if (
    CONTENT_EXACT.has(normalized)
    || normalized.includes("prompt")
    || normalized.includes("completion")
    || normalized.includes("customer_content")
    || parts.has("message")
    || parts.has("messages")
    || parts.has("body")
  ) {
    return "PROHIBITED_CONTENT";
  }
  if (
    CREDENTIAL_EXACT.has(normalized)
    || normalized.includes("password")
    || normalized.includes("secret")
    || normalized.includes("api_key")
    || normalized.includes("private_key")
    || normalized.includes("credential")
    || normalized.includes("authorization")
    || parts.has("token")
    || parts.has("cookie")
    || parts.has("key")
  ) {
    return "CREDENTIAL_FIELD";
  }
  if (
    KERNEL_EXACT.has(normalized)
    || normalized.includes("ebpf")
    || normalized.includes("ssl_write")
    || normalized.includes("gnutls")
    || parts.has("kernel")
    || parts.has("uprobe")
    || parts.has("kprobe")
  ) {
    return "KERNEL_DETAIL_EXCLUDED";
  }
  if (COMPANY_EXACT.has(normalized)) return "COMPANY_OPS_EXCLUDED";
  if (
    PROOF_EXACT.has(normalized)
    || normalized.includes("cluster_verified")
    || normalized.includes("production_verified")
  ) {
    return "UNSUPPORTED_PROOF_EXCLUDED";
  }
  return null;
}

function credentialOptionPresent(options) {
  if (!options || typeof options !== "object") return false;
  for (const key of CREDENTIAL_OPTION_KEYS) {
    if (Object.prototype.hasOwnProperty.call(options, key)) return true;
  }
  return false;
}

module.exports = {
  CREDENTIAL_OPTION_KEYS,
  KNOWN_FIELDS,
  blockingReason,
  credentialOptionPresent,
  normalizeName,
  safeFieldName,
};
