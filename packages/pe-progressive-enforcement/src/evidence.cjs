"use strict";

const { CONTROL_KEYS, DROPPED_KEYS } = require("./boundary.cjs");
const { digest } = require("./canonical.cjs");

function stripValue(value, dropped, depth) {
  if (depth > 8) return null;
  if (value === null) return null;
  const kind = typeof value;
  if (kind === "string" || kind === "boolean") return value;
  if (kind === "number") return Number.isSafeInteger(value) ? value : null;
  if (kind !== "object") return null;
  if (Array.isArray(value)) {
    return value.map((item) => stripValue(item, dropped, depth + 1));
  }
  const out = {};
  for (const key of Object.keys(value)) {
    const lowered = key.toLowerCase();
    if (DROPPED_KEYS.has(lowered) || CONTROL_KEYS.has(lowered)) {
      dropped.push(key);
      continue;
    }
    out[key] = stripValue(value[key], dropped, depth + 1);
  }
  return out;
}

function stripRecord(value) {
  const dropped = [];
  const cleaned = stripValue(value, dropped, 0);
  return { value: cleaned, dropped };
}

function recordEvidence(engine, kind, body) {
  const stripped = stripRecord(body);
  engine.seq += 1;
  const payload = {
    kind,
    at: engine.now(),
    seq: engine.seq,
    body: stripped.value,
    dropped: stripped.dropped,
  };
  const evidenceId = `ev_${digest(payload).slice(0, 16)}`;
  const record = { evidence_id: evidenceId, ...payload };
  engine.evidence.push(record);
  return record;
}

module.exports = {
  recordEvidence,
  stripRecord,
};
