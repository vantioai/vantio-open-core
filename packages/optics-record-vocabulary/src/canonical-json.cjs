"use strict";

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
  if (kind === "string") return quote(value);
  if (kind !== "object") throw coded("UNSUPPORTED_VALUE");
  if (seen.has(value)) throw coded("CYCLE_REJECTED");
  seen.add(value);
  let out;
  if (Array.isArray(value)) {
    out = "[";
    for (let i = 0; i < value.length; i += 1) {
      if (i) out += ",";
      out += stringify(value[i], depth + 1, seen);
    }
    out += "]";
  } else {
    const keys = Object.keys(value).sort();
    out = "{";
    for (let i = 0; i < keys.length; i += 1) {
      if (i) out += ",";
      out += quote(keys[i]) + ":" + stringify(value[keys[i]], depth + 1, seen);
    }
    out += "}";
  }
  seen.delete(value);
  return out;
}

function quote(text) {
  let out = "\"";
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code === 0x22) out += "\\\"";
    else if (code === 0x5c) out += "\\\\";
    else if (code === 0x08) out += "\\b";
    else if (code === 0x09) out += "\\t";
    else if (code === 0x0a) out += "\\n";
    else if (code === 0x0c) out += "\\f";
    else if (code === 0x0d) out += "\\r";
    else if (code < 0x20) out += "\\u" + code.toString(16).padStart(4, "0");
    else out += text[i];
  }
  return out + "\"";
}

module.exports = { canonicalJson };
