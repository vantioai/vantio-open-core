"use strict";

const { createHash } = require("node:crypto");

const { MAX_JSON_DEPTH } = require("./boundary.cjs");

function coded(code) {
  const error = new Error(code);
  error.code = code;
  return error;
}

function canonicalJson(value) {
  return stringify(value, 0, new Set());
}

function stringify(value, depth, seen) {
  if (value === undefined) throw coded("UNDEFINED_REJECTED");
  if (depth > MAX_JSON_DEPTH) throw coded("MAX_DEPTH_EXCEEDED");
  if (value === null) return "null";
  const kind = typeof value;
  if (kind === "boolean") return value ? "true" : "false";
  if (kind === "number") {
    if (!Number.isFinite(value) || !Number.isInteger(value)) throw coded("NON_INTEGER_REJECTED");
    if (Object.is(value, -0)) return "0";
    if (!Number.isSafeInteger(value)) throw coded("UNSAFE_INTEGER_REJECTED");
    return String(value);
  }
  if (kind === "string") return JSON.stringify(value);
  if (kind !== "object") throw coded("UNSUPPORTED_VALUE");
  if (seen.has(value)) throw coded("CYCLE_REJECTED");
  seen.add(value);
  let out;
  if (Array.isArray(value)) {
    const parts = [];
    for (const item of value) parts.push(stringify(item, depth + 1, seen));
    out = `[${parts.join(",")}]`;
  } else {
    const keys = Object.keys(value).sort();
    const parts = [];
    for (const key of keys) {
      if (value[key] === undefined) throw coded("UNDEFINED_REJECTED");
      parts.push(`${JSON.stringify(key)}:${stringify(value[key], depth + 1, seen)}`);
    }
    out = `{${parts.join(",")}}`;
  }
  seen.delete(value);
  return out;
}

function digest(value) {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}

module.exports = {
  canonicalJson,
  digest,
};
