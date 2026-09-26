"use strict";

// Canonical JSON for cross-language comparison.
// UTF-8, sorted keys, no insignificant whitespace.
// Controls use the same short escapes as Python json.dumps.
// Non-ASCII is left unescaped. U+2028 and U+2029 are not emitted by the validator.

function canonicalJson(value) {
  return stringify(value);
}

function stringify(value) {
  if (value === null) return "null";
  const kind = typeof value;
  if (kind === "boolean") return value ? "true" : "false";
  if (kind === "number") {
    if (!Number.isFinite(value) || !Number.isInteger(value)) {
      throw new TypeError("canonical JSON allows integers only");
    }
    if (Object.is(value, -0)) return "0";
    return String(value);
  }
  if (kind === "string") return quote(value);
  if (Array.isArray(value)) {
    let out = "[";
    for (let i = 0; i < value.length; i += 1) {
      if (i) out += ",";
      out += stringify(value[i]);
    }
    return out + "]";
  }
  if (kind === "object") {
    const keys = Object.keys(value).sort();
    let out = "{";
    for (let i = 0; i < keys.length; i += 1) {
      if (i) out += ",";
      out += quote(keys[i]) + ":" + stringify(value[keys[i]]);
    }
    return out + "}";
  }
  throw new TypeError("unsupported canonical value");
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
