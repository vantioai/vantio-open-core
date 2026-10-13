"use strict";

const fs = require("node:fs");

const PROTOCOLS = new Set([
  "otlp-http-json",
  "otlp-http-protobuf",
  "otlp-grpc",
]);

function headerMap(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  for (const [name, raw] of Object.entries(value)) {
    if (!/^[A-Za-z0-9-]{1,64}$/.test(name)) continue;
    if (typeof raw !== "string" || raw.length > 4096 || /[\r\n]/.test(raw)) continue;
    out[name] = raw;
  }
  return out;
}

function readHeaderSource(config) {
  let fromEnv = {};
  if (typeof config.headers_env === "string" && config.headers_env) {
    const raw = process.env[config.headers_env];
    if (raw) fromEnv = headerMap(JSON.parse(raw));
  }
  let fromFile = {};
  if (typeof config.headers_file === "string" && config.headers_file) {
    const stat = fs.statSync(config.headers_file);
    if ((stat.mode & 0o077) !== 0) throw new Error("headers file mode");
    fromFile = headerMap(JSON.parse(fs.readFileSync(config.headers_file, "utf8")));
  }
  return { ...fromFile, ...fromEnv };
}

function loadConfig(filePath) {
  const parsed = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!parsed || typeof parsed !== "object") return { enabled: false, reason: "DISABLED" };
  if (parsed.headers) throw new Error("inline headers are refused");
  if (parsed.enabled !== true) {
    return { enabled: false, reason: "DISABLED" };
  }
  if (typeof parsed.endpoint !== "string" || !parsed.endpoint) {
    return { enabled: false, reason: "NO_ENDPOINT" };
  }
  const protocol = PROTOCOLS.has(parsed.protocol) ? parsed.protocol : "otlp-http-json";
  let url;
  try {
    url = new URL(parsed.endpoint);
  } catch {
    return { enabled: false, reason: "BAD_ENDPOINT" };
  }
  const loopback = url.hostname === "localhost" || url.hostname === "127.0.0.1" || url.hostname === "::1";
  const tlsOn = parsed.tls !== false && url.protocol !== "http:";
  if (url.protocol === "http:" && !loopback && parsed.allow_insecure_plaintext !== true) {
    return { enabled: false, reason: "PLAINTEXT_REFUSED" };
  }
  if (url.protocol === "http:" && loopback && parsed.allow_insecure_localhost !== true) {
    return { enabled: false, reason: "LOCALHOST_PLAINTEXT_REFUSED" };
  }
  const headers = readHeaderSource(parsed);
  return {
    enabled: true,
    endpoint: parsed.endpoint,
    protocol,
    headers,
    tls: tlsOn,
    caFile: parsed.ca_file || null,
    certFile: parsed.cert_file || null,
    keyFile: parsed.key_file || null,
    compression: parsed.compression === "gzip" ? "gzip" : "none",
    maxBatch: Math.min(Math.max(Number(parsed.max_batch) || 32, 1), 256),
    maxDelayMs: Math.min(Math.max(Number(parsed.max_delay_ms) || 1000, 10), 30000),
    maxQueue: Math.min(Math.max(Number(parsed.max_queue) || 256, 1), 5000),
    timeoutMs: Math.min(Math.max(Number(parsed.timeout_ms) || 1000, 50), 10000),
    jsonlPath: parsed.jsonl_path || null,
    jsonlMaxBytes: Math.min(Math.max(Number(parsed.jsonl_max_bytes) || 1_048_576, 1024), 8_388_608),
    syslog: parsed.syslog || null,
    webhook: parsed.webhook || null,
    allowInsecurePlaintext: parsed.allow_insecure_plaintext === true,
    allowInsecureLocalhost: parsed.allow_insecure_localhost === true,
  };
}

module.exports = { loadConfig };
