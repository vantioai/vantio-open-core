"use strict";

const { readFileSync } = require("fs");
const path = require("path");
const { types } = require("util");
const privacy = require("./privacy.cjs");

const bounds = JSON.parse(
  readFileSync(path.join(__dirname, "..", "contract", "normalization.json"), "utf8"),
).bounds;

const OVERSIZE = "OVERSIZE";
const MALFORMED_TEXT = "MALFORMED_TEXT";

function boundMarker(kind, scan) {
  const marker = { __optics_bound: kind };
  if (scan) {
    marker.matched = scan.matched === true;
    marker.boundary = scan.boundary === true && scan.matched !== true;
  }
  return Object.freeze(marker);
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

function chainHasAccessor(value) {
  let proto = Object.getPrototypeOf(value);
  const seen = new Set();
  while (proto && proto !== Object.prototype && proto !== Array.prototype && !seen.has(proto)) {
    seen.add(proto);
    const descs = Object.getOwnPropertyDescriptors(proto);
    for (const key of Object.keys(descs)) {
      if (typeof descs[key].get === "function" || typeof descs[key].set === "function") return true;
    }
    proto = Object.getPrototypeOf(proto);
  }
  return false;
}

function containerKind(value) {
  if (types.isProxy(value)) return "proxy";
  const proto = Object.getPrototypeOf(value);
  if (Array.isArray(value)) return proto === Array.prototype ? "array" : "exotic";
  if (proto === Object.prototype || proto === null) return "object";
  return "exotic";
}

function rejectDescriptors(descs) {
  for (const key of Object.keys(descs)) {
    const desc = descs[key];
    if (!desc || typeof desc.get === "function" || typeof desc.set === "function") {
      return "ACCESSOR_PROPERTY_FORBIDDEN";
    }
  }
  return null;
}

function copyValue(value, state) {
  if (value === null) return { ok: true, value: null };
  const kind = typeof value;
  if (kind === "string") {
    if (Buffer.byteLength(value, "utf8") > bounds.max_string_chars) {
      return { ok: true, value: boundMarker(OVERSIZE, privacy.scanBoundedPrefix(value)) };
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
  if (kind === "function") {
    return { ok: false, reason: "UNSUPPORTED_COMPLEX_VALUE", disposition: "REJECT_FIELD" };
  }
  if (kind === "bigint" || kind === "symbol") {
    return { ok: false, reason: "HOSTILE_INPUT" };
  }
  if (kind !== "object") return { ok: false, reason: "HOSTILE_INPUT" };
  if (types.isUint8Array(value)) {
    return { ok: false, reason: "UNSUPPORTED_COMPLEX_VALUE", disposition: "REJECT_FIELD" };
  }
  const shape = containerKind(value);
  if (shape === "proxy" || (shape === "exotic" && chainHasAccessor(value))) {
    return { ok: false, reason: "ACCESSOR_PROPERTY_FORBIDDEN" };
  }
  if (shape === "exotic") return { ok: false, reason: "UNSUPPORTED_COMPLEX_VALUE" };
  if (state.seen.has(value)) return { ok: false, reason: "CYCLE_REJECTED" };
  if (state.depth >= bounds.max_depth) return { ok: false, reason: "EXCESSIVE_NESTING" };
  if (state.nodes >= bounds.max_nodes) return { ok: false, reason: "INPUT_BOUND" };
  if (Object.getOwnPropertySymbols(value).length > 0) {
    return { ok: false, reason: "UNSUPPORTED_COMPLEX_VALUE" };
  }

  const descs = Object.getOwnPropertyDescriptors(value);
  const descriptorProblem = rejectDescriptors(descs);
  if (descriptorProblem) return { ok: false, reason: descriptorProblem };

  state.seen.add(value);
  state.nodes += 1;
  state.depth += 1;
  try {
    if (shape === "array") {
      const lengthDesc = descs.length;
      const length = lengthDesc && Object.prototype.hasOwnProperty.call(lengthDesc, "value")
        ? lengthDesc.value
        : value.length;
      if (typeof length !== "number" || length < 0 || length > bounds.max_array) {
        return { ok: false, reason: "INPUT_BOUND" };
      }
      const out = [];
      for (let i = 0; i < length; i += 1) {
        const desc = descs[String(i)];
        if (!desc || !Object.prototype.hasOwnProperty.call(desc, "value")) continue;
        const child = copyValue(desc.value, state);
        if (!child.ok) return child;
        if (!child.skip) out.push(child.value);
      }
      return { ok: true, value: out };
    }

    const keys = Object.keys(descs).filter((key) => Object.prototype.hasOwnProperty.call(descs[key], "value"));
    if (keys.length > bounds.max_keys) return { ok: false, reason: "INPUT_BOUND" };
    const forms = new Set();
    for (const key of keys) {
      if (typeof key !== "string") return { ok: false, reason: "INVALID_FORMAT" };
      if (Buffer.byteLength(key, "utf8") > bounds.field_name_max_bytes) {
        return { ok: false, reason: "MAX_SIZE_EXCEEDED" };
      }
      const form = privacy.comparisonForm(key);
      if (forms.has(form)) return { ok: false, reason: "DUPLICATE_CANONICAL_FIELD" };
      forms.add(form);
    }
    const out = Object.create(null);
    for (const key of keys) {
      const child = copyValue(descs[key].value, state);
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
