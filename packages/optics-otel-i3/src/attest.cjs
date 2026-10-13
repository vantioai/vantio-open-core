"use strict";

const { createHash } = require("node:crypto");

// In-process source binding. A caller-supplied signature field is not read.
// This is not a Phantom Engine ledger signature and not a production key.

const registry = new WeakMap();

function stable(value, seen) {
  if (value === undefined) return "null";
  if (value === null) return "null";
  const kind = typeof value;
  if (kind === "string" || kind === "number" || kind === "boolean") return JSON.stringify(value);
  if (kind !== "object") return null;
  if (seen.has(value)) return null;
  seen.add(value);
  if (Array.isArray(value)) {
    const parts = [];
    for (const item of value) {
      const encoded = stable(item, seen);
      if (encoded == null) return null;
      parts.push(encoded);
    }
    return `[${parts.join(",")}]`;
  }
  const parts = [];
  for (const key of Object.keys(value).sort()) {
    const encoded = stable(value[key], seen);
    if (encoded == null) return null;
    parts.push(`${JSON.stringify(key)}:${encoded}`);
  }
  return `{${parts.join(",")}}`;
}

function digestRecord(record) {
  const encoded = stable(record, new Set());
  if (encoded == null) return null;
  return createHash("sha256").update(encoded).digest("hex");
}

function freezeDeep(value, seen) {
  if (value === null || typeof value !== "object") return;
  if (seen.has(value)) return;
  seen.add(value);
  if (Array.isArray(value)) {
    for (const item of value) freezeDeep(item, seen);
  } else {
    for (const key of Object.keys(value)) freezeDeep(value[key], seen);
  }
  Object.freeze(value);
}

function plainClone(value, seen) {
  if (value === undefined || value === null) return value;
  const kind = typeof value;
  if (kind === "string" || kind === "number" || kind === "boolean") return value;
  if (kind !== "object") return null;
  if (seen.has(value)) return null;
  seen.add(value);
  if (Array.isArray(value)) {
    const copy = [];
    for (const item of value) {
      const child = plainClone(item, seen);
      if (child === null && item !== null) return null;
      copy.push(child);
    }
    return copy;
  }
  const copy = {};
  for (const key of Object.keys(value)) {
    const child = plainClone(value[key], seen);
    if (child === null && value[key] !== null) return null;
    copy[key] = child;
  }
  return copy;
}

function attestSourceRecord(record) {
  if (record === null || typeof record !== "object" || Array.isArray(record)) {
    return { ok: false, reason: "RECORD_NOT_OBJECT" };
  }
  let snapshot = null;
  try {
    snapshot = plainClone(record, new Set());
  } catch {
    snapshot = null;
  }
  if (!snapshot || Array.isArray(snapshot)) return { ok: false, reason: "RECORD_UNREADABLE" };
  let digest = null;
  try {
    digest = digestRecord(snapshot);
  } catch {
    digest = null;
  }
  if (!digest) return { ok: false, reason: "RECORD_UNREADABLE" };
  try {
    freezeDeep(snapshot, new Set());
  } catch {
    return { ok: false, reason: "RECORD_UNREADABLE" };
  }
  registry.set(record, { digest, snapshot });
  return { ok: true, attestation: "producer" };
}

function sourceAttestation(record) {
  if (record === null || typeof record !== "object" || Array.isArray(record)) {
    return { state: "unattested", snapshot: null };
  }
  const stored = registry.get(record);
  if (!stored) return { state: "unattested", snapshot: null };
  let live = null;
  try {
    live = plainClone(record, new Set());
  } catch {
    return { state: "mismatch", snapshot: stored.snapshot };
  }
  let digest = null;
  try {
    digest = live ? digestRecord(live) : null;
  } catch {
    digest = null;
  }
  if (!digest || digest !== stored.digest) return { state: "mismatch", snapshot: stored.snapshot };
  return { state: "producer", snapshot: stored.snapshot };
}

module.exports = {
  attestSourceRecord,
  sourceAttestation,
};
