"use strict";

// Lab-only file join. It does not open a socket, enroll a host, or load a kernel program.
// A live OpenShell sandbox on an enrolled host stays Roadmap.

const fs = require("node:fs");

const { MAX_LINE_BYTES, MAX_RECORDS, MIN_UNIX_MS, MAX_UNIX_MS } = require("../src/boundary.cjs");
const { loadNdjson } = require("../src/load.cjs");
const { reconcile } = require("../src/reconcile.cjs");

const MAX_FILE_BYTES = MAX_RECORDS * 256;
const HOST_CLASS = "vantio-owned";

function rejected(detail) {
  return {
    status: "rejected",
    reason_code: "SCHEMA",
    detail,
    findings: [],
    label: "LAB_ONLY",
    live_stack: "ROADMAP",
    openshell_runtime: "not-executed",
    phantom_engine_runtime: "not-executed",
  };
}

function readBounded(file) {
  const textPath = String(file);
  if (textPath.toLowerCase().includes("navera")) {
    return { ok: false, reason_code: "SCHEMA", detail: "navera" };
  }
  let stat;
  try {
    stat = fs.statSync(textPath);
  } catch {
    return { ok: false, reason_code: "SCHEMA", detail: "path" };
  }
  if (!stat.isFile() || stat.size > MAX_FILE_BYTES) {
    return { ok: false, reason_code: "LIMIT_EXCEEDED", detail: "file" };
  }
  return { ok: true, text: fs.readFileSync(textPath, "utf8") };
}

function applyClock(row, offsetMs) {
  if (!row || typeof row !== "object" || Array.isArray(row)) {
    return row;
  }
  if (row.observed_at_ms != null || row.kernel_monotonic_ns == null) {
    return row;
  }
  if (typeof offsetMs !== "number" || !Number.isSafeInteger(offsetMs)) {
    return row;
  }
  if (typeof row.kernel_monotonic_ns !== "number" || !Number.isSafeInteger(row.kernel_monotonic_ns)) {
    return row;
  }
  const converted = offsetMs + Math.floor(row.kernel_monotonic_ns / 1000000);
  const copy = { ...row };
  delete copy.kernel_monotonic_ns;
  if (!Number.isSafeInteger(converted) || converted < MIN_UNIX_MS || converted > MAX_UNIX_MS) {
    return copy;
  }
  copy.observed_at_ms = converted;
  return copy;
}

function loadRecords(file) {
  const read = readBounded(file);
  if (!read.ok) {
    return read;
  }
  if (Buffer.byteLength(read.text, "utf8") > MAX_FILE_BYTES) {
    return { ok: false, reason_code: "LIMIT_EXCEEDED", detail: "file" };
  }
  const loaded = loadNdjson(read.text);
  if (!loaded.ok) {
    return loaded;
  }
  if (loaded.records.length > MAX_RECORDS) {
    return { ok: false, reason_code: "LIMIT_EXCEEDED", detail: "ndjson" };
  }
  return loaded;
}

function joinFiles(options) {
  if (options == null || options.hostClass !== HOST_CLASS) {
    return rejected("host_class");
  }
  const kernel = loadRecords(options.kernelPath);
  if (!kernel.ok) {
    return { ...rejected(kernel.detail || "kernel"), reason_code: kernel.reason_code };
  }
  const openshell = loadRecords(options.openshellPath);
  if (!openshell.ok) {
    return { ...rejected(openshell.detail || "openshell"), reason_code: openshell.reason_code };
  }
  const gate = loadRecords(options.gatePath);
  if (!gate.ok) {
    return { ...rejected(gate.detail || "gate"), reason_code: gate.reason_code };
  }
  const snapshot = {
    run: options.run,
    kernel: kernel.records.map((row) => applyClock(row, options.clockOffsetMs)),
    openshell: openshell.records,
    gate: gate.records,
  };
  const result = reconcile(snapshot);
  return {
    ...result,
    label: "LAB_ONLY",
    live_stack: "ROADMAP",
    openshell_runtime: "not-executed",
    phantom_engine_runtime: "not-executed",
    clock_offset_applied: Number.isSafeInteger(options.clockOffsetMs),
    line_budget: MAX_LINE_BYTES,
  };
}

module.exports = {
  HOST_CLASS,
  MAX_FILE_BYTES,
  applyClock,
  joinFiles,
};
