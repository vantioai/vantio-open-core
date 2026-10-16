"use strict";

const {
  CONVERSATION_KEYS,
  MAX_DEPTH,
  MAX_KEYS,
  MAX_RECORDS,
  MAX_STRING,
  SECRET_KEYS,
} = require("./boundary.cjs");

const SECRET_KEY_SET = new Set(SECRET_KEYS);
const CONVERSATION_KEY_SET = new Set(CONVERSATION_KEYS);

function problem(reasonCode, detail) {
  return { ok: false, reason_code: reasonCode, detail };
}

function isSecretString(value) {
  if (typeof value !== "string" || value.length === 0 || value.length > MAX_STRING) {
    return false;
  }
  if (/^bearer\s+\S+/i.test(value)) {
    return true;
  }
  if (/^sk-[A-Za-z0-9]/.test(value)) {
    return true;
  }
  if (/AKIA[0-9A-Z]{16}/.test(value)) {
    return true;
  }
  if (/-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(value)) {
    return true;
  }
  if (/^[a-z][a-z0-9+.-]*:\/\/[^\s/@]+:[^\s/@]+@/i.test(value)) {
    return true;
  }
  return false;
}

function safeSegment(segment) {
  if (typeof segment === "number") {
    return `[${segment}]`;
  }
  if (typeof segment !== "string") {
    return ".redacted-key";
  }
  if (isSecretString(segment) || !/^[A-Za-z0-9_.-]{1,64}$/.test(segment)) {
    return ".redacted-key";
  }
  return `.${segment}`;
}

function joinPath(base, segment) {
  if (base === "") {
    if (typeof segment === "number") {
      return `[${segment}]`;
    }
    return safeSegment(segment).slice(1);
  }
  if (typeof segment === "number") {
    return `${base}[${segment}]`;
  }
  return `${base}${safeSegment(segment)}`;
}

function scan(value, path, depth, seen) {
  if (depth > MAX_DEPTH) {
    return problem("LIMIT_EXCEEDED", path || "root");
  }
  if (value === null || value === undefined || typeof value === "boolean") {
    return { ok: true };
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      return problem("SCHEMA", path || "root");
    }
    return { ok: true };
  }
  if (typeof value === "string") {
    if (value.length > MAX_STRING) {
      return problem("LIMIT_EXCEEDED", path || "root");
    }
    if (isSecretString(value)) {
      return problem("SECRET_FIELD", path || "root");
    }
    return { ok: true };
  }
  if (typeof value !== "object") {
    return problem("SCHEMA", path || "root");
  }
  if (seen.has(value)) {
    return problem("SCHEMA", path || "root");
  }
  seen.add(value);
  if (Array.isArray(value)) {
    if (value.length > MAX_RECORDS) {
      return problem("LIMIT_EXCEEDED", path || "root");
    }
    for (let index = 0; index < value.length; index += 1) {
      const child = scan(value[index], joinPath(path, index), depth + 1, seen);
      if (!child.ok) {
        return child;
      }
    }
    return { ok: true };
  }
  const keys = Object.keys(value);
  if (keys.length > MAX_KEYS) {
    return problem("LIMIT_EXCEEDED", path || "root");
  }
  for (const key of keys) {
    const leaf = key.toLowerCase();
    const next = joinPath(path, key);
    if (leaf === "__proto__" || leaf === "prototype" || leaf === "constructor") {
      return problem("SCHEMA", next);
    }
    if (SECRET_KEY_SET.has(leaf)) {
      return problem("SECRET_FIELD", next);
    }
    if (CONVERSATION_KEY_SET.has(leaf)) {
      return problem("CONVERSATION_FIELD", next);
    }
    const child = scan(value[key], next, depth + 1, seen);
    if (!child.ok) {
      return child;
    }
  }
  return { ok: true };
}

function scanValue(value, path) {
  return scan(value, path, 0, new WeakSet());
}

module.exports = {
  isSecretString,
  scanValue,
};
