"use strict";

// Same four categories as interceptor.cjs PII_PATTERNS at 89f95099.
// This module does not load the interceptor. JSON walk redacts string values only.

const PATTERNS = {
  ssn: /\b\d{3}-\d{2}-\d{4}\b/g,
  email: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,
  credit_card: /\b(?:\d[ -]?){13,16}\b/g,
  phone: /\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,
};

function scanString(text, types) {
  const found = [];
  for (const type of types) {
    const key = String(type).trim().toLowerCase();
    const re = PATTERNS[key];
    if (!re) continue;
    re.lastIndex = 0;
    if (re.test(text)) found.push(key);
  }
  return found;
}

function scanJson(value, types, found) {
  if (typeof value === "string") {
    for (const hit of scanString(value, types)) found.push(hit);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) scanJson(item, types, found);
    return;
  }
  if (value && typeof value === "object") {
    for (const key of Object.keys(value)) scanJson(value[key], types, found);
  }
}

function scanText(text, types) {
  if (typeof text !== "string") return { ok: false };
  const trimmed = text.trim();
  if (trimmed && (trimmed[0] === "{" || trimmed[0] === "[")) {
    try {
      const parsed = JSON.parse(text);
      const found = [];
      scanJson(parsed, types, found);
      return { ok: true, found, bytes: Buffer.byteLength(text) };
    } catch {
      // Not JSON. Fall through to a full-string scan.
    }
  }
  return { ok: true, found: scanString(text, types), bytes: Buffer.byteLength(text) };
}

module.exports = {
  PATTERNS,
  scanText,
};
