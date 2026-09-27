"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-otel-i3");

function walk(directory, files) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else files.push(absolute);
  }
  return files;
}

test("the private package is outside the pnpm workspace", () => {
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("optics-otel-i3"), false);
  assert.equal(workspace.includes("optics-otel-mapping"), false);
  const meta = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(meta.private, true);
  assert.equal(meta.version, "0.0.0-unstable-pre-1.0");
  assert.equal(Object.hasOwn(meta, "dependencies"), false);
});

test("live products and the mapping package do not load the adapter", () => {
  const roots = [
    "packages/vantio-cli",
    "packages/vantio-agent-sdk",
    "packages/vantio-agent-sdk-py",
    "packages/optics-otel-mapping",
  ];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === "dist") continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (/\.(js|cjs|mjs|ts|py|json|toml|md)$/.test(entry.name)) {
        const text = fs.readFileSync(absolute, "utf8");
        assert.equal(text.includes("optics-otel-i3"), false, absolute);
      }
    }
  }
  for (const relative of roots) visit(path.join(ROOT, relative));
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const nodeSdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.match(python, /version = "3.1.0"/);
});

test("adapter source does not read the environment or open a writer", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const transport = files.filter((file) => file.endsWith(path.join("src", "transport.cjs")));
  assert.equal(transport.length, 1);
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("process.env"), false, file);
    assert.equal(text.includes("child_process"), false, file);
    assert.equal(text.includes("@opentelemetry"), false, file);
    assert.equal(text.includes("writeFile"), false, file);
    assert.equal(text.includes("Date.now"), false, file);
    assert.equal(text.includes("Math.random"), false, file);
    assert.equal(/require\(["']fs["']\)/.test(text), false, file);
    assert.equal(text.includes("vantio-cli"), false, file);
    assert.equal(text.includes("vantio-agent-sdk"), false, file);
    assert.equal(text.includes("optics-evidence-contract"), false, file);
    const allowsHttp = file.endsWith(path.join("src", "transport.cjs"));
    if (!allowsHttp) {
      assert.equal(/require\(["']node:http["']\)/.test(text), false, file);
      assert.equal(/require\(["']node:https["']\)/.test(text), false, file);
      assert.equal(text.includes("setTimeout"), false, file);
    }
  }
});

test("public sketch still says Optics does not export OTLP", () => {
  const text = fs.readFileSync(path.join(ROOT, "docs/optics-otel-mapping.md"), "utf8");
  assert.match(text, /Optics does not export OTLP/);
  assert.equal(text.includes("OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED"), false);
});

test("new I3 files match the documentation-release stale-name gate", async () => {
  const { countPatterns } = await import("../../docs/scripts/docs-release-lib.mjs");
  const spec = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/governance/STALE-NAMES.json"), "utf8"));
  const extensions = [".md", ".txt", ".js", ".cjs", ".mjs", ".py", ".ts", ".json", ".yml", ".yaml", ".toml"];
  const scanned = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (extensions.some((ext) => entry.name.endsWith(ext))) scanned.push(absolute);
    }
  }
  for (const relative of [
    "docs/internal/ws7-otel-i3",
    "packages/optics-otel-i3",
    "tests/optics-otel-i3",
  ]) {
    visit(path.join(ROOT, relative));
  }
  assert.ok(scanned.length > 0);
  for (const file of scanned) {
    const count = countPatterns(fs.readFileSync(file, "utf8"), spec.patterns);
    assert.equal(count, 0, path.relative(ROOT, file));
  }
});
