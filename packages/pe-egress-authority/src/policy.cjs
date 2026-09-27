"use strict";

const SCOPES = new Set(["llm_and_named", "all_egress"]);

function isPlain(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function own(obj, key) {
  return Object.prototype.hasOwnProperty.call(obj, key);
}

function readStringArray(policy, key) {
  if (!own(policy, key)) return { ok: true, value: [] };
  const raw = policy[key];
  if (!Array.isArray(raw)) return { ok: false, reason: "policy_field_unclassifiable", field: key };
  const value = [];
  for (const item of raw) {
    if (typeof item !== "string") return { ok: false, reason: "policy_field_unclassifiable", field: key };
    value.push(item);
  }
  return { ok: true, value };
}

function readNonNeg(policy, key) {
  if (!own(policy, key)) return { ok: true, value: 0, present: false };
  const raw = policy[key];
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw < 0) {
    return { ok: false, reason: "policy_field_unclassifiable", field: key };
  }
  return { ok: true, value: raw, present: true };
}

function readBool(policy, key) {
  if (!own(policy, key)) return { ok: true, value: null };
  if (typeof policy[key] !== "boolean") return { ok: false, reason: "policy_field_unclassifiable", field: key };
  return { ok: true, value: policy[key] };
}

function readPolicy(raw) {
  if (!isPlain(raw)) {
    return { ok: false, result: "EVIDENCE_UNAVAILABLE", reason: "policy_absent" };
  }
  const enforce = readBool(raw, "enforce");
  if (!enforce.ok) return { ok: false, result: "UNKNOWN", reason: enforce.reason };
  if (enforce.value == null) return { ok: false, result: "EVIDENCE_UNAVAILABLE", reason: "enforce_not_set" };

  const dry = readBool(raw, "dry_run");
  if (!dry.ok) return { ok: false, result: "UNKNOWN", reason: dry.reason };

  const redact = readBool(raw, "redact_pii");
  if (!redact.ok) return { ok: false, result: "UNKNOWN", reason: redact.reason };

  const requireTls = readBool(raw, "require_tls_peer");
  if (!requireTls.ok) return { ok: false, result: "UNKNOWN", reason: requireTls.reason };

  const credentialRequired = readBool(raw, "credential_required");
  if (!credentialRequired.ok) return { ok: false, result: "UNKNOWN", reason: credentialRequired.reason };

  if (!own(raw, "scope")) return { ok: false, result: "EVIDENCE_UNAVAILABLE", reason: "scope_not_set" };
  if (typeof raw.scope !== "string" || !SCOPES.has(raw.scope)) {
    return { ok: false, result: "UNKNOWN", reason: "scope_unclassifiable" };
  }

  let sensitiveAction = "ignore";
  if (own(raw, "sensitive_action")) {
    if (raw.sensitive_action !== "ignore" && raw.sensitive_action !== "redact" && raw.sensitive_action !== "deny") {
      return { ok: false, result: "UNKNOWN", reason: "sensitive_action_unclassifiable" };
    }
    sensitiveAction = raw.sensitive_action;
  } else if (redact.value === true) {
    sensitiveAction = "redact";
  }

  const arrays = {};
  for (const key of [
    "blocked_hosts",
    "allowed_hosts",
    "blocked_ips",
    "allowed_ips",
    "allowed_protocols",
    "denied_protocols",
    "allowed_ports",
    "denied_ports",
    "allowed_methods",
    "denied_methods",
    "allowed_path_prefixes",
    "denied_path_prefixes",
    "pii_types",
  ]) {
    const read = readStringArray(raw, key);
    if (!read.ok) return { ok: false, result: "UNKNOWN", reason: read.reason };
    arrays[key] = read.value;
  }

  if (sensitiveAction === "redact" && arrays.pii_types.length === 0) {
    return { ok: false, result: "EVIDENCE_UNAVAILABLE", reason: "pii_types_not_set" };
  }
  if (sensitiveAction === "deny" && arrays.pii_types.length === 0) {
    return { ok: false, result: "EVIDENCE_UNAVAILABLE", reason: "pii_types_not_set" };
  }

  const maxRequest = readNonNeg(raw, "max_request_bytes");
  if (!maxRequest.ok) return { ok: false, result: "UNKNOWN", reason: maxRequest.reason };
  const spend = readNonNeg(raw, "spend_cap_usd");
  if (!spend.ok) return { ok: false, result: "UNKNOWN", reason: spend.reason };

  let resource = null;
  if (own(raw, "resource")) {
    if (!isPlain(raw.resource)) return { ok: false, result: "UNKNOWN", reason: "resource_policy_unclassifiable" };
    const maxChild = readNonNeg(raw.resource, "max_child_processes");
    if (!maxChild.ok) return { ok: false, result: "UNKNOWN", reason: "resource_policy_unclassifiable" };
    resource = {
      max_child_processes: maxChild.present ? maxChild.value : null,
    };
  }

  return {
    ok: true,
    policy: {
      enforce: enforce.value,
      dry_run: dry.value,
      redact_pii: redact.value === true,
      require_tls_peer: requireTls.value === true,
      credential_required: credentialRequired.value === true,
      scope: raw.scope,
      sensitive_action: sensitiveAction,
      max_request_bytes: maxRequest.value,
      spend_cap_usd: spend.value,
      resource,
      ...arrays,
    },
  };
}

module.exports = {
  readPolicy,
};
