"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/optics-node-adapter/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-node-adapter");
const BASE = "587f3b94d47ea958f91d3a99125cd55931d995f1";
const BANNER = "PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA";
const DOCS = [
  "BOUNDARY.md",
  "DESIGN.md",
  "NO-OPTIMISTIC-DEFAULTS.md",
  "COMPATIBILITY-FIXTURES.md",
  "PRIVACY.md",
  "KNOWN-LIMITATIONS.md",
  "IMPLEMENTATION-REPORT.md",
];
const ALLOWED_PREFIXES = [
  "packages/optics-node-adapter/",
  "tests/optics-node-adapter/",
  "docs/internal/optics-pkg02-unit-b/",
  "tests/optics-record-vocabulary/isolation.test.cjs",
];

function walk(directory, files) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else files.push(absolute);
  }
  return files;
}

function read(relativePath) {
  return fs.readFileSync(path.join(ROOT, relativePath), "utf8");
}

test("public API is an inert copy adapter", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "ADAPTER_VERSION",
    "AUDIENCE",
    "FUTURE_CLI_PLACEHOLDER",
    "POSTURE",
    "SCHEMA_STATUS",
    "SCHEMA_VERSION",
    "UNICODE_PROFILE_ID",
    "adaptFixture",
    "adaptNodeCopy",
  ]);
  for (const name of ["writeRun", "activateWriter", "migrate", "convertLiveFile"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
  assert.equal(api.ADAPTER_VERSION, "0.0.0-unstable-pre-1.0");
  assert.equal(api.FUTURE_CLI_PLACEHOLDER, "PKG02-FUTURE-CLI-UNASSIGNED");
  assert.equal(api.SCHEMA_VERSION, 0);
});

test("adapter source does not write files or import live products", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
    /writeFile/,
    /appendFile/,
    /createWriteStream/,
    /sqlite/i,
    /child_process/,
    /~\/\.vantio/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
  }
});

test("adaptation does not write the filesystem", () => {
  const calls = [];
  const original = fs.writeFileSync;
  fs.writeFileSync = (...args) => {
    calls.push(String(args[0]));
    return original.apply(fs, args);
  };
  try {
    const result = api.adaptNodeCopy({
      calls: [{ hostname: "api.example.com", status: 204 }],
      vantio_run_log: "1",
    });
    assert.equal(result.record_emitted, true);
    assert.deepEqual(calls, []);
  } finally {
    fs.writeFileSync = original;
  }
});

test("frozen package versions are unchanged and this package stays private", () => {
  const cli = JSON.parse(read("packages/vantio-cli/package.json"));
  const nodeSdk = JSON.parse(read("packages/vantio-agent-sdk/package.json"));
  const contract = JSON.parse(read("packages/optics-evidence-contract/package.json"));
  const vocabulary = JSON.parse(read("packages/optics-record-vocabulary/package.json"));
  const adapter = JSON.parse(read("packages/optics-node-adapter/package.json"));
  const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
  assert.equal(cli.version, "0.3.24");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.equal(contract.version, "0.0.0-unstable-pre-1.0");
  assert.equal(vocabulary.version, "0.0.0-unstable-pre-1.0");
  assert.match(python, /version = "3.1.0"/);
  assert.equal(adapter.private, true);
  assert.equal(adapter.version, "0.0.0-unstable-pre-1.0");
  const workspace = read("pnpm-workspace.yaml");
  assert.equal(workspace.includes("optics-node-adapter"), false);
  assert.equal(workspace.includes("optics-record-vocabulary"), false);
});

test("live CLI sources do not import the adapter", () => {
  const files = walk(path.join(ROOT, "packages/vantio-cli"), []);
  for (const file of files) {
    if (!file.endsWith(".js") && !file.endsWith(".cjs") && !file.endsWith(".mjs")) continue;
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("optics-node-adapter"), false, file);
    assert.equal(text.includes("adaptNodeCopy"), false, file);
  }
  const pythonFiles = walk(path.join(ROOT, "packages/vantio-agent-sdk-py"), []);
  for (const file of pythonFiles) {
    if (!file.endsWith(".py")) continue;
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("optics-node-adapter"), false, file);
  }
});

function normalizeGitPath(file) {
  return String(file).replace(/\\/g, "/").replace(/^\.\//, "");
}

function scopeViolation(file) {
  const normalized = normalizeGitPath(file);
  if (normalized.length === 0) return null;
  if (ALLOWED_PREFIXES.some((prefix) => normalized === prefix || normalized.startsWith(prefix))) return null;
  return normalized;
}

function parseDiffZ(text) {
  return text.split("\0").map((part) => part.trim()).filter((part) => part.length > 0);
}

function parseStatusZ(text) {
  const parts = text.split("\0");
  if (parts.length > 0 && parts[parts.length - 1] === "") parts.pop();
  const paths = [];
  let index = 0;
  while (index < parts.length) {
    const entry = parts[index];
    if (entry.length < 4) {
      index += 1;
      continue;
    }
    const xy = entry.slice(0, 2);
    paths.push(entry.slice(3));
    index += 1;
    if (xy.includes("R") || xy.includes("C")) {
      if (index < parts.length) {
        paths.push(parts[index]);
        index += 1;
      }
    }
  }
  return paths;
}

function assertScoped(paths) {
  const outside = [];
  for (const file of paths) {
    const violation = scopeViolation(file);
    if (violation) outside.push(violation);
  }
  assert.deepEqual(outside, [], "out-of-scope path: " + outside.join(", "));
}

function gitZ(args) {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8" });
}

test("committed and uncommitted paths stay inside Unit B", () => {
  const committed = parseDiffZ(gitZ(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(gitZ(["status", "--porcelain=v1", "-z"]));
  const relevant = committed.filter((file) => !file.startsWith("docs/internal/optics-pkg02-unit-a/"));
  assertScoped(relevant);
  assertScoped(uncommitted);
});

test("internal docs carry the inert banner", () => {
  for (const name of DOCS) {
    const text = read(path.join("docs/internal/optics-pkg02-unit-b", name));
    assert.equal(text.includes(BANNER), true, name);
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
  }
  const report = read("docs/internal/optics-pkg02-unit-b/IMPLEMENTATION-REPORT.md");
  assert.equal(report.includes("OPTICS_PKG02_UNIT_B_READY_FOR_COUNCIL"), true);
});
}
