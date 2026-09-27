"use strict";

const PROHIBITED_KEYS = new Set([
  "access_token",
  "api_key",
  "authorization",
  "completion",
  "completions",
  "credential",
  "credentials",
  "packet",
  "password",
  "payload",
  "private_key",
  "prompt",
  "prompts",
  "raw_body",
  "refresh_token",
  "secret",
  "secrets",
  "session_token",
]);

const DANGEROUS_KEYS = new Set(["__proto__", "constructor", "prototype"]);
const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const HASH_PATTERN = /^[A-Za-z0-9]{16,128}$/;
const CONSENSUS_KEYS = ["agent_consensus", "agent_votes", "consensus", "votes"];
const ROLE_KEYS = ["claimed_role", "role", "role_labels", "roles"];

function scanRecord(value, depth = 0, nodes = { n: 0 }) {
  nodes.n += 1;
  if (nodes.n > 400) return "RECORD_TOO_LARGE";
  if (depth > 12) return "RECORD_TOO_DEEP";
  if (!value || typeof value !== "object") return null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const hit = scanRecord(item, depth + 1, nodes);
      if (hit) return hit;
    }
    return null;
  }
  for (const key of Object.keys(value)) {
    if (DANGEROUS_KEYS.has(key)) return "DANGEROUS_KEY";
    if (PROHIBITED_KEYS.has(key)) return "PROHIBITED_FIELD";
    const hit = scanRecord(value[key], depth + 1, nodes);
    if (hit) return hit;
  }
  return null;
}

function isSafeId(value) {
  return typeof value === "string" && ID_PATTERN.test(value);
}

function isHash(value) {
  return typeof value === "string" && HASH_PATTERN.test(value);
}

function distinct(ids) {
  const seen = new Set();
  const out = [];
  for (const id of ids) {
    if (!seen.has(id)) {
      seen.add(id);
      out.push(id);
    }
  }
  return out;
}

function parseTime(value) {
  if (typeof value !== "string" || value.length < 10 || value.length > 40) return null;
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return null;
  return ms;
}

function hasConsensusSignal(input) {
  if (!input || typeof input !== "object") return false;
  return CONSENSUS_KEYS.some((key) => Object.prototype.hasOwnProperty.call(input, key));
}

function hasRoleSignal(input) {
  if (!input || typeof input !== "object") return false;
  return ROLE_KEYS.some((key) => Object.prototype.hasOwnProperty.call(input, key));
}

module.exports = {
  distinct,
  hasConsensusSignal,
  hasRoleSignal,
  isHash,
  isSafeId,
  parseTime,
  scanRecord,
};
