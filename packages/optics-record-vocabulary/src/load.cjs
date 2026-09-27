"use strict";

const fs = require("fs");
const path = require("path");

const PACKAGE_ROOT = path.resolve(__dirname, "..");

function freeze(value, seen) {
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return value;
  seen.add(value);
  if (Array.isArray(value)) {
    for (const item of value) freeze(item, seen);
  } else {
    for (const key of Object.keys(value)) freeze(value[key], seen);
  }
  return Object.freeze(value);
}

function readFrozen(relativePath) {
  const absolute = path.join(PACKAGE_ROOT, relativePath);
  const parsed = JSON.parse(fs.readFileSync(absolute, "utf8"));
  return freeze(parsed, new Set());
}

function loadVocabulary() {
  return readFrozen("vocabulary/record-vocabulary.json");
}

function loadFixtures() {
  return readFrozen("fixtures/conformance-fixtures.json");
}

module.exports = { loadFixtures, loadVocabulary };
