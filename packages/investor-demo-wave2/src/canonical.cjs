"use strict";

const { createHash } = require("node:crypto");

function canonicalize(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => canonicalize(item)).join(",")}]`;
  const keys = Object.keys(value).filter((key) => value[key] !== undefined).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalize(value[key])}`).join(",")}}`;
}

function sha256(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function withoutHash(doc) {
  const copy = { ...doc };
  delete copy.canonical_sha256;
  return copy;
}

function seal(doc) {
  const body = withoutHash(doc);
  return { ...body, canonical_sha256: sha256(canonicalize(body)) };
}

module.exports = {
  canonicalize,
  seal,
  sha256,
  withoutHash,
};
