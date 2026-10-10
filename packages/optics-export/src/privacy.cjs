"use strict";

const { COVERAGE, DECISIONS, KINDS } = require("./schema.cjs");

const CANARY_RE = /canary[-_]/i;

function decodedForms(value) {
  const forms = [];
  const push = (text) => {
    if (typeof text === "string" && text.length > 0 && text.length < 8192) forms.push(text);
  };
  push(value);
  let current = String(value);
  for (let i = 0; i < 3; i += 1) {
    try {
      const next = decodeURIComponent(current.replace(/\+/g, " "));
      if (next === current) break;
      push(next);
      current = next;
    } catch {
      break;
    }
  }
  const chunks = String(value).match(/[A-Za-z0-9+/]{16,}={0,2}/g) || [];
  for (const chunk of chunks) {
    const pad = chunk.length % 4 === 0 ? chunk : chunk + "=".repeat((4 - (chunk.length % 4)) % 4);
    try {
      push(Buffer.from(pad, "base64").toString("utf8"));
    } catch {
      /* not base64 */
    }
  }
  return forms;
}

function textHasCanary(text) {
  if (typeof text !== "string" || text.length === 0) return false;
  return decodedForms(text).some((form) => CANARY_RE.test(form));
}

function eventHasCanary(event) {
  const strings = [];
  const walk = (value) => {
    if (typeof value === "string") strings.push(value);
    else if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") Object.values(value).forEach(walk);
  };
  walk(event);
  if (strings.some((text) => textHasCanary(text))) return true;
  if (textHasCanary(strings.join(""))) return true;
  for (let i = 0; i < strings.length; i += 1) {
    for (let j = 0; j < strings.length; j += 1) {
      if (i !== j && textHasCanary(strings[i] + strings[j])) return true;
    }
  }
  return false;
}

function stripQuery(value) {
  if (typeof value !== "string") return null;
  const cut = ["?", "#"].reduce((end, mark) => {
    const at = value.indexOf(mark);
    return at >= 0 ? Math.min(end, at) : end;
  }, value.length);
  return value.slice(0, cut);
}

function boundedText(value, max) {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (!text || text.length > max) return null;
  if (/[\r\n\0]/.test(text)) return null;
  return text;
}

function hostName(value) {
  const text = boundedText(value, 253);
  if (!text || text.includes(" ") || text.includes("/") || text.includes("@")) return null;
  if (text.includes("?") || text.includes("#")) return null;
  return text.toLowerCase();
}

function portNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(n) || n < 1 || n > 65535) return null;
  return n;
}

function byteCount(value) {
  if (value == null) return null;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value > 2 ** 53 - 1) return null;
  return value;
}

function pidNumber(value) {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(n) || n < 0 || n > 2 ** 31 - 1) return null;
  return n;
}

function executableName(value) {
  const text = boundedText(value, 128);
  if (!text || text.includes("/") || text.includes("\\") || text.includes("?")) return null;
  return text;
}

function lineage(value) {
  if (!Array.isArray(value)) return [];
  const out = [];
  for (const row of value.slice(0, 16)) {
    if (!row || typeof row !== "object") continue;
    const pid = pidNumber(row.pid);
    const executable = executableName(row.executable);
    if (pid == null || !executable) continue;
    out.push({ pid, executable });
  }
  return out;
}

function hexId(value, chars) {
  if (typeof value !== "string" || !new RegExp(`^[0-9a-f]{${chars}}$`, "i").test(value)) return null;
  return value.toLowerCase();
}

function digest(value) {
  if (typeof value !== "string" || !/^sha256:[0-9a-f]{64}$/.test(value)) return null;
  return value;
}

function project(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    return { ok: false, reason: "MALFORMED" };
  }
  const kind = KINDS.includes(input.kind) ? input.kind : null;
  if (!kind) return { ok: false, reason: "KIND" };
  const traceId = hexId(input.trace_id, 32);
  const spanId = hexId(input.span_id, 16);
  if (!traceId || !spanId) return { ok: false, reason: "TRACE" };
  const parent = input.parent_span_id == null ? null : hexId(input.parent_span_id, 16);
  if (input.parent_span_id != null && !parent) return { ok: false, reason: "TRACE" };
  const coverage = COVERAGE.includes(input.coverage_state) ? input.coverage_state : "UNKNOWN";
  const decision = input.decision == null ? null : (DECISIONS.includes(input.decision) ? input.decision : null);
  if ((kind === "phantom.decision" || kind === "enterprise.evidence") && !digest(input.policy_digest)) {
    return { ok: false, reason: "POLICY_DIGEST" };
  }
  if (kind === "phantom.decision" && !decision) return { ok: false, reason: "DECISION" };
  const event = {
    kind,
    trace_id: traceId,
    span_id: spanId,
    parent_span_id: parent,
    destination_host: hostName(input.destination_host),
    destination_port: portNumber(input.destination_port),
    pid: pidNumber(input.pid),
    executable: executableName(input.executable),
    lineage: lineage(input.lineage),
    request_bytes: byteCount(input.request_bytes),
    response_bytes: byteCount(input.response_bytes),
    duration_ms: byteCount(input.duration_ms),
    http_status: input.http_status == null ? null : portNumber(input.http_status) && input.http_status <= 599 ? Number(input.http_status) : null,
    optics_status: boundedText(input.optics_status, 32),
    application_status: boundedText(input.application_status, 64),
    workload_id: boundedText(input.workload_id, 128),
    coverage_state: coverage,
    decision,
    policy_digest: digest(input.policy_digest),
    path: stripQuery(typeof input.path === "string" ? input.path : null),
  };
  if (event.http_status != null && (event.http_status < 100 || event.http_status > 599)) event.http_status = null;
  if (eventHasCanary(event)) return { ok: false, reason: "PRIVACY" };
  return { ok: true, event };
}

module.exports = {
  CANARY_RE,
  eventHasCanary,
  project,
  stripQuery,
  textHasCanary,
};
