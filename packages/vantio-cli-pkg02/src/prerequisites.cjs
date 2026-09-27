"use strict";

const fs = require("node:fs");

const { adaptNodeCopy } = require("../../optics-node-adapter/src/adapt.cjs");
const boundary = require("./boundary.cjs");

function proveAdapterByteIdentity(filePath) {
  const before = fs.readFileSync(filePath);
  const loaded = require("../../optics-node-adapter/src/index.cjs");
  if (loaded.FUTURE_CLI_PLACEHOLDER !== "PKG02-FUTURE-CLI-UNASSIGNED") {
    return false;
  }
  if (typeof loaded.adaptNodeCopy !== "function") return false;
  const after = fs.readFileSync(filePath);
  return before.equals(after);
}

function opticsValues(value, found) {
  if (!value || typeof value !== "object") return;
  if (Object.prototype.hasOwnProperty.call(value, "optics_status")) found.push(value.optics_status);
  if (Object.prototype.hasOwnProperty.call(value, "opticsStatus")) found.push(value.opticsStatus);
  const keys = Object.keys(value);
  for (let i = 0; i < keys.length; i += 1) {
    if (keys[i] === "optics_status" || keys[i] === "opticsStatus") continue;
    opticsValues(value[keys[i]], found);
  }
}

function proveUnknownOpticsNotSuccess(record) {
  const input = record || {
    calls: [{ hostname: "api.openai.com", optics_status: "SUPER_SUCCESS", status: 200 }],
    schema_version: boundary.LEGACY_SCHEMA_VERSION,
    trace_id: "0xunknown",
    vantio_run_log: "1",
  };
  const adapted = adaptNodeCopy(input);
  const tokens = [];
  opticsValues(adapted, tokens);
  return {
    adapted,
    optimistic_default_forbidden: adapted.optimistic_default_forbidden === true,
    tokens,
    unknown_becomes_success: tokens.includes("SUCCESS"),
  };
}

module.exports = {
  proveAdapterByteIdentity,
  proveUnknownOpticsNotSuccess,
};
