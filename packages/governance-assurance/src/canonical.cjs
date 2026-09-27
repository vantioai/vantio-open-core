"use strict";

function sortValue(value) {
  if (Array.isArray(value)) return value.map((item) => sortValue(item));
  if (value === null || typeof value !== "object") return value;
  const sorted = {};
  for (const key of Object.keys(value).sort()) {
    if (value[key] !== undefined) sorted[key] = sortValue(value[key]);
  }
  return sorted;
}

function canonicalize(value) {
  return JSON.stringify(sortValue(value));
}

function stableStringify(value) {
  return `${JSON.stringify(sortValue(value), null, 2)}\n`;
}

module.exports = {
  canonicalize,
  sortValue,
  stableStringify,
};
