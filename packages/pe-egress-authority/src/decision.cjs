"use strict";

const { AUDIENCE, DIMENSIONS, RESULT_SET, VOCABULARY_ID } = require("./vocabulary.cjs");
const { classifyIp } = require("./match.cjs");

function isPlain(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function own(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

function blankDimensions() {
  const out = {};
  for (const name of DIMENSIONS) out[name] = { state: "not_evaluated", detail: null };
  return out;
}

function createContext() {
  return {
    dimensions: blankDimensions(),
    evidenceClass: "ABSENT",
    path: null,
    policy: null,
    attempt: null,
  };
}

function mark(ctx, name, state, detail) {
  ctx.dimensions[name] = { state, detail: detail == null ? null : detail };
}

function wireFor(result, reason) {
  if (result === "DENIED" && (reason === "host_not_permitted" || reason === "not_in_allowed_hosts")) return "BLOCKED_HOST";
  if (result === "DENIED" && reason === "payload_size") return "BLOCKED_SIZE";
  if (result === "DENIED" && reason === "spend_cap") return "BLOCKED_SPEND";
  if (result === "REDACTED") return "REDACTED";
  if (result === "ALLOWED") return "ALLOWED";
  if (result === "ENFORCEMENT_GAP" && (reason === "unscanned_body" || reason === "fail_open_policy_not_loaded")) {
    return "ENFORCEMENT_GAP";
  }
  return null;
}

function dryWire(would, authorityReason) {
  if (would === "DENIED" && (authorityReason === "host_not_permitted" || authorityReason === "not_in_allowed_hosts" || authorityReason === "redirect_hop_denied" || authorityReason === "dns_answer_denied")) {
    return "DRY_RUN_BLOCKED_HOST";
  }
  if (would === "DENIED" && authorityReason === "payload_size") return "DRY_RUN_BLOCKED_SIZE";
  if (would === "DENIED" && authorityReason === "spend_cap") return "DRY_RUN_BLOCKED_SPEND";
  if (would === "REDACTED") return "REDACTED";
  return null;
}

function emit(ctx, result, reason, extra) {
  if (!RESULT_SET.has(result)) {
    return emit(ctx, "UNKNOWN", "evaluator_fault", { fault: true });
  }
  const fields = extra || {};
  const authority = fields.authority && RESULT_SET.has(fields.authority) ? fields.authority : result;
  const would = fields.would == null ? null : fields.would;
  if (would != null && !RESULT_SET.has(would)) {
    return emit(ctx, "UNKNOWN", "evaluator_fault", { fault: true });
  }
  const wire = result === "ENFORCEMENT_GAP" && reason === "dry_run_pass_through"
    ? dryWire(would, fields.authorityReason || null)
    : wireFor(result, reason);
  return {
    result,
    reason,
    authority_disposition: authority,
    would_result: would,
    live_wire_action: wire,
    dimensions: ctx.dimensions,
    evidence_class: ctx.evidenceClass,
    path_id: ctx.path ? ctx.path.id : null,
    this_force_executed_host: false,
    this_force_executed_network: false,
    optimistic_allow: false,
    audience: AUDIENCE,
    vocabulary: VOCABULARY_ID,
    fault: fields.fault === true,
  };
}

function micro(n) {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  return Math.round(n * 1e6);
}

function normalizePort(value) {
  if (typeof value === "number") {
    if (!Number.isInteger(value) || value < 0 || value > 65535) return { ok: false };
    return { ok: true, port: String(value) };
  }
  if (typeof value === "string" && /^\d+$/.test(value)) {
    const n = Number(value);
    if (n > 65535) return { ok: false };
    return { ok: true, port: String(n) };
  }
  return { ok: false };
}

function normalizeProtocol(value) {
  if (typeof value !== "string" || value.trim() === "") return null;
  const text = value.trim().toLowerCase();
  return text.endsWith(":") ? text.slice(0, -1) : text;
}

function portListed(port, items) {
  for (const item of items) {
    const parsed = normalizePort(item);
    if (!parsed.ok) return { bad: true, listed: false };
    if (parsed.port === port) return { bad: false, listed: true };
  }
  return { bad: false, listed: false };
}

function protocolListed(protocol, items) {
  for (const item of items) {
    const parsed = normalizeProtocol(item);
    if (!parsed) return { bad: true, listed: false };
    if (parsed === protocol) return { bad: false, listed: true };
  }
  return { bad: false, listed: false };
}

function readDestination(attempt) {
  if (!own(attempt, "destination")) return { missing: true };
  const dest = attempt.destination;
  if (!isPlain(dest)) return { bad: true };
  let hostname = null;
  if (own(dest, "hostname") && dest.hostname != null) {
    if (typeof dest.hostname !== "string") return { bad: true };
    hostname = dest.hostname.trim().toLowerCase().replace(/\.$/, "");
    if (hostname.startsWith("[") && hostname.endsWith("]")) hostname = hostname.slice(1, -1);
    if (hostname === "") hostname = null;
    else if (/[^\x00-\x7f]/.test(hostname) || /\s/.test(hostname)) return { bad: true };
  }
  let ip = null;
  if (own(dest, "ip") && dest.ip != null) {
    if (typeof dest.ip !== "string" || !classifyIp(dest.ip)) return { bad: true };
    ip = dest.ip.trim().toLowerCase();
  }
  let port = null;
  if (own(dest, "port") && dest.port != null) {
    const parsed = normalizePort(dest.port);
    if (!parsed.ok) return { bad: true };
    port = parsed.port;
  }
  let protocol = null;
  if (own(dest, "protocol") && dest.protocol != null) {
    protocol = normalizeProtocol(dest.protocol);
    if (!protocol) return { bad: true };
  }
  let catalog = null;
  if (own(dest, "in_product_scope")) {
    if (typeof dest.in_product_scope !== "boolean") return { bad: true };
    catalog = dest.in_product_scope;
  }
  return { hostname, ip, port, protocol, catalog };
}

function httpConstraints(policy) {
  return policy.allowed_methods.length > 0
    || policy.denied_methods.length > 0
    || policy.allowed_path_prefixes.length > 0
    || policy.denied_path_prefixes.length > 0;
}

function applyLatch(ctx, decision) {
  const stopping = decision.result === "DENIED"
    || decision.result === "REDACTED"
    || decision.result === "CONTAINED"
    || decision.result === "REVOKED";
  if (!stopping) return decision;
  if (ctx.policy.enforce !== true) {
    return emit(ctx, "ENFORCEMENT_GAP", "enforce_off", {
      authority: decision.result,
      would: decision.result,
      authorityReason: decision.reason,
    });
  }
  if (ctx.policy.dry_run == null) {
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "dry_run_not_set", {
      authority: decision.result,
      would: decision.result,
    });
  }
  if (ctx.policy.dry_run === true) {
    return emit(ctx, "ENFORCEMENT_GAP", "dry_run_pass_through", {
      authority: decision.result,
      would: decision.result,
      authorityReason: decision.reason,
    });
  }
  return decision;
}

function controlEvidence(value) {
  return isPlain(value) && value.evidence === "supplied" && typeof value.control_id === "string" && value.control_id.length > 0;
}


module.exports = {
  applyLatch,
  controlEvidence,
  createContext,
  emit,
  httpConstraints,
  isPlain,
  mark,
  micro,
  own,
  portListed,
  protocolListed,
  readDestination,
};
