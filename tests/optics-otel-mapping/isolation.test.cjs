"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-otel-mapping");

function walk(directory, files) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else files.push(absolute);
  }
  return files;
}

test("package source does not open a network, spawn, or write", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["']http["']\)/,
    /require\(["']https["']\)/,
    /require\(["']net["']\)/,
    /require\(["']dgram["']\)/,
    /require\(["']child_process["']\)/,
    /require\(["']undici["']\)/,
    /@opentelemetry/,
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
    /require\(["'][^"']*optics-evidence-contract/,
    /writeFile/,
    /appendFile/,
    /fetch\(/,
    /require\(["'][^"']*grpc/,
    /require\(["'][^"']*otlp/,
    /Exporter\(/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
  }
});

test("the private package is outside the pnpm workspace and stays private", () => {
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("optics-otel-mapping"), false);
  const meta = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(meta.private, true);
  assert.equal(meta.version, "0.0.0-unstable-pre-1.0");
  assert.equal(Object.hasOwn(meta, "dependencies"), false);
});

test("live packages do not load the mapping stub", () => {
  const roots = ["packages/vantio-cli", "packages/vantio-agent-sdk", "packages/vantio-agent-sdk-py"];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === "dist") continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (/\.(js|cjs|mjs|ts|py|json)$/.test(entry.name)) {
        const text = fs.readFileSync(absolute, "utf8");
        assert.equal(text.includes("optics-otel-mapping"), false, absolute);
      }
    }
  }
  for (const relative of roots) visit(path.join(ROOT, relative));
});

test("public API has no enable or emit function", () => {
  const api = require("../../packages/optics-otel-mapping/src/index.cjs");
  assert.deepEqual(Object.keys(api).sort(), [
    "ALLOWED_MAP_TARGETS",
    "POSTURE",
    "PROHIBITED_TARGETS",
    "adapters",
    "exportOpticsRecords",
    "mappingDocument",
    "preview",
  ]);
  for (const name of ["enableAdapter", "emitOtlp", "startExporter", "install"]) {
    assert.equal(Object.hasOwn(api, name), false);
  }
});
