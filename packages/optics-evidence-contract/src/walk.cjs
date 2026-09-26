"use strict";

const { readFileSync } = require("fs");
const path = require("path");

const bounds = JSON.parse(
  readFileSync(path.join(__dirname, "..", "contract", "normalization.json"), "utf8"),
).bounds;

const OVERSIZE = "OVERSIZE";
const MALFORMED_TEXT = "MALFORMED_TEXT";

function boundMarker(kind) {
  return Object.freeze({ __optics_bound: kind });
}

function isBound(value) {
  return Boolean(value) && typeof value === "object" && value.__optics_bound;
}

function hasLoneSurrogate(text) {
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = text.charCodeAt(i + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) return true;
      i += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return true;
    }
  }
  return false;
}

function plainCopy(value) {
  const state = { nodes: 0, depth: 0, seen: new Set() };
  return copyValue(value, state);
}

function copyValue(value, state) {
  if (value === null) return { ok: true, value: null };
  const kind = typeof value;
  if (kind === "string") {
    if (value.length > bounds.max_string_chars) {
      return { ok: true, value: boundMarker(OVERSIZE) };
    }
    if (hasLoneSurrogate(value)) {
      return { ok: true, value: boundMarker(MALFORMED_TEXT) };
    }
    return { ok: true, value };
  }
  if (kind === "boolean") return { ok: true, value };
  if (kind === "number") {
    if (!Number.isFinite(value)) return { ok: false, reason: "HOSTILE_INPUT" };
    if (Object.is(value, -0)) return { ok: true, value: 0 };
    return { ok: true, value };
  }
  if (kind === "undefined") return { ok: true, skip: true };
  if (kind === "bigint" || kind === "function" || kind === "symbol") {
    return { ok: false, reason: "HOSTILE_INPUT" };
  }
  if (kind !== "object") return { ok: false, reason: "HOSTILE_INPUT" };
  if (state.seen.has(value)) return { ok: false, reason: "CYCLE_REJECTED" };
  if (state.depth >= bounds.max_depth) return { ok: false, reason: "EXCESSIVE_NESTING" };
  if (state.nodes >= bounds.max_nodes) return { ok: false, reason: "INPUT_BOUND" };

  state.seen.add(value);
  state.nodes += 1;
  state.depth += 1;
  try {
    if (Array.isArray(value)) {
      let length;
      try {
        length = value.length;
      } catch {
        return { ok: false, reason: "HOSTILE_INPUT" };
      }
      if (typeof length !== "number" || length < 0 || length > bounds.max_array) {
        return { ok: false, reason: "INPUT_BOUND" };
      }
      const out = [];
      for (let i = 0; i < length; i += 1) {
        let item;
        try {
          item = value[i];
        } catch {
          return { ok: false, reason: "HOSTILE_INPUT" };
        }
      const child = copyValue(item, state);
      if (!child.ok) return child;
      if (!child.skip) out.push(child.value);
      }
      return { ok: true, value: out };
    }

    let keys;
    try {
      keys = Object.keys(value);
    } catch {
      return { ok: false, reason: "HOSTILE_INPUT" };
    }
    if (keys.length > bounds.max_keys) return { ok: false, reason: "INPUT_BOUND" };
    const out = Object.create(null);
    for (const key of keys) {
      if (key.length > 128) return { ok: false, reason: "INPUT_BOUND" };
      let childValue;
      try {
        childValue = value[key];
      } catch {
        return { ok: false, reason: "HOSTILE_INPUT" };
      }
      const child = copyValue(childValue, state);
      if (!child.ok) return child;
      if (!child.skip) out[key] = child.value;
    }
    return { ok: true, value: out };
  } finally {
    state.depth -= 1;
    state.seen.delete(value);
  }
}

module.exports = {
  plainCopy,
  isBound,
  OVERSIZE,
  MALFORMED_TEXT,
  bounds,
};
