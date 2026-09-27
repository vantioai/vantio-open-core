"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../internal/w3-otlp-enable-test-disable/src/index.cjs");

const ROOT = path.join(__dirname, "../..");
const HARNESS = path.join(ROOT, "internal/w3-otlp-enable-test-disable");

function readTree(directory) {
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...readTree(absolute));
    else files.push(absolute);
  }
  return files;
}

test("rest registers match and stay disabled", () => {
  const internal = fs.readFileSync(
    path.join(ROOT, "docs/internal/wave3/otlp-enable-test-disable/REST-REGISTER.json"),
    "utf8",
  );
  const program = fs.readFileSync(
    path.join(ROOT, "docs/programs/production-readiness/wave3/OTLP-REST-REGISTER.json"),
    "utf8",
  );
  assert.equal(internal, program);
  assert.equal(api.REST_REGISTER.producer_classification, "W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL");
  assert.equal(api.REST_REGISTER.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(api.REST_REGISTER.council_verdict, null);
  assert.equal(api.REST_REGISTER.self_certified_council_pass, false);
  assert.equal(api.REST_REGISTER.starting_ref, "0cd36cf1d01c4db83a0a6999db0a322441f61c98");
  assert.equal(api.REST_REGISTER.default_enabled, false);
  assert.equal(api.REST_REGISTER.enabled_at_rest, false);
  assert.equal(api.REST_REGISTER.public_shipped_support, false);
  assert.equal(api.REST_REGISTER.founder_decision_12, "unresolved");
  assert.equal(api.REST_REGISTER.i3_status, "NOT_AUTHORIZED");
  assert.equal(api.REST_REGISTER.announced, false);
  assert.equal(api.REST_REGISTER.published, false);
  assert.equal(api.REST_REGISTER.host_attachment, false);
  assert.equal(api.REST_REGISTER.customer_deployed, false);
  assert.equal(api.REST_REGISTER.frozen_cli_reopened, false);
  assert.equal(api.HARNESS_ENDPOINT, "http://127.0.0.1:9/v1/traces");
});

test("frozen products, the mapping document, and the public sketch stay closed", () => {
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  const mapping = JSON.parse(fs.readFileSync(
    path.join(ROOT, "packages/optics-otel-mapping/mapping/otel-semantic-mapping.json"),
    "utf8",
  ));
  const sketch = fs.readFileSync(path.join(ROOT, "docs/optics-otel-mapping.md"), "utf8");
  const i3 = require("../../packages/optics-otel-i3/src/index.cjs");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3\.1\.0"/);
  assert.equal(workspace.includes("w3-otlp-enable-test-disable"), false);
  assert.equal(workspace.includes("optics-otel-i3"), false);
  assert.equal(mapping.i3_status, "NOT_AUTHORIZED");
  assert.equal(mapping.adapters_default_enabled, false);
  assert.equal(mapping.public_shipped_support, false);
  assert.equal(mapping.otlp_export_authorized, false);
  assert.equal(mapping.founder_decision_12, "unresolved");
  assert.match(sketch, /Optics does not export OTLP/);
  assert.equal(sketch.includes("W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL"), false);
  assert.equal(i3.POSTURE.default_enabled, false);
  assert.equal(i3.POSTURE.public_shipped_support, false);
  assert.equal(i3.POSTURE.producer_classification, "OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED");
  assert.equal(i3.adapterStatus().active, false);
});

test("live products do not load the harness", () => {
  const roots = [
    "packages/vantio-cli",
    "packages/vantio-agent-sdk",
    "packages/vantio-agent-sdk-py",
    "packages/optics-otel-mapping",
    "packages/optics-otel-i3",
  ];
  for (const relative of roots) {
    for (const file of readTree(path.join(ROOT, relative))) {
      if (file.includes(`${path.sep}node_modules${path.sep}`) || file.includes(`${path.sep}dist${path.sep}`)) continue;
      if (!/\.(js|cjs|mjs|ts|py|json|toml|md)$/.test(file)) continue;
      const text = fs.readFileSync(file, "utf8");
      assert.equal(text.includes("w3-otlp-enable-test-disable"), false, file);
    }
  }
});

test("harness source does not open a socket or flip the default", () => {
  const source = readTree(path.join(HARNESS, "src")).map((file) => fs.readFileSync(file, "utf8")).join("\n");
  const banned = [
    "process.env",
    "child_process",
    "node:http",
    "node:https",
    "default_enabled: true",
    "\"default_enabled\": true",
    "public_shipped_support: true",
    "product_otlp_export_authorized: true",
    "i3_status: \"AUTHORIZED\"",
    "otlp_export_authorized: true",
    "vantio-cli",
    "vantio-agent-sdk",
  ];
  for (const token of banned) assert.equal(source.includes(token), false, token);
  const meta = JSON.parse(fs.readFileSync(path.join(HARNESS, "package.json"), "utf8"));
  assert.equal(meta.private, true);
  assert.equal(meta.version, "0.0.0-unstable-pre-1.0");
  assert.equal(Object.hasOwn(meta, "dependencies"), false);
});

test("new OTLP proof files match the documentation-release stale-name gate", async () => {
  // docs-release-lib.mjs is ESM, so this CJS file loads it with import().
  const { countPatterns } = await import("../../docs/scripts/docs-release-lib.mjs");
  const spec = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/governance/STALE-NAMES.json"), "utf8"));
  const extensions = [".md", ".txt", ".js", ".cjs", ".mjs", ".py", ".ts", ".json", ".yml", ".yaml", ".toml"];
  const roots = [
    "internal/w3-otlp-enable-test-disable",
    "docs/internal/wave3/otlp-enable-test-disable",
    "tests/w3-otlp-enable-test-disable",
    "docs/programs/production-readiness/wave3/OTLP-ENABLE-TEST-DISABLE.md",
    "docs/programs/production-readiness/wave3/OTLP-REST-REGISTER.json",
  ];
  const scanned = [];
  for (const relative of roots) {
    const absolute = path.join(ROOT, relative);
    const stat = fs.statSync(absolute);
    if (stat.isFile()) scanned.push(absolute);
    else {
      for (const file of readTree(absolute)) {
        if (extensions.some((ext) => file.endsWith(ext))) scanned.push(file);
      }
    }
  }
  assert.ok(scanned.length > 8);
  for (const file of scanned) {
    const count = countPatterns(fs.readFileSync(file, "utf8"), spec.patterns);
    assert.equal(count, 0, path.relative(ROOT, file));
  }
});
