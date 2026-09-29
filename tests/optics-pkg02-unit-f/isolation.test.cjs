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

const api = require("../../packages/optics-record-reader/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-record-reader");
const BASE = "4e50dd9775d23899e1c68e5fa0e7a59c17066ea3";
const BANNER = "PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA";
const DOCS = [
  "BOUNDARY.md",
  "COMPATIBILITY.md",
  "DESIGN.md",
  "IMPLEMENTATION-REPORT.md",
  "KNOWN-LIMITATIONS.md",
  "NO-OPTIMISTIC-DEFAULTS.md",
  "ORDINARY-CLIENT-PROOF.md",
  "PRIVACY.md",
];
const ALLOWED_PREFIXES = [
  "packages/optics-record-reader/",
  "tests/optics-pkg02-unit-f/",
  "docs/internal/optics-pkg02-unit-f/",
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

test("public API is a read-and-explain reader", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "AUDIENCE",
    "FUTURE_CLI_PLACEHOLDER",
    "FUTURE_PYTHON_PLACEHOLDER",
    "POSTURE",
    "READER_NAME",
    "READER_VERSION",
    "SCHEMA_STATUS",
    "SCHEMA_VERSION",
    "UNICODE_PROFILE_ID",
    "UNITS_D_E",
    "explainCopy",
    "explainFixture",
    "readRunFile",
  ]);
  for (const name of ["writeRun", "activateWriter", "migrate", "convertLiveFile", "publish", "seal"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
  assert.equal(api.READER_NAME, "@vantio/optics-record-reader");
  assert.equal(api.READER_VERSION, "0.0.0-unstable-pre-1.0");
  assert.equal(api.SCHEMA_VERSION, 0);
  assert.equal(api.UNITS_D_E, "NOT_AUTHORIZED");
  assert.equal(api.FUTURE_CLI_PLACEHOLDER, "PKG02-FUTURE-CLI-UNASSIGNED");
  assert.equal(api.FUTURE_PYTHON_PLACEHOLDER, "PKG02-FUTURE-PYTHON-UNASSIGNED");
});

test("reader source does not write files or import live products", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
    /writeFile/,
    /appendFile/,
    /createWriteStream/,
    /unlinkSync/,
    /renameSync/,
    /rmSync/,
    /mkdirSync/,
    /require\(["']sqlite/,
    /better-sqlite/,
    /node:sqlite/,
    /child_process/,
    /~\/\.vantio/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
  }
});

test("explanation does not write the filesystem", () => {
  const calls = [];
  const original = fs.writeFileSync;
  fs.writeFileSync = (...args) => {
    calls.push(String(args[0]));
    return original.apply(fs, args);
  };
  try {
    const result = api.explainCopy({
      calls: [{ hostname: "api.example.com", status: 204 }],
      vantio_run_log: "1",
    });
    assert.equal(result.record_emitted, true);
    assert.equal(result.write_back, false);
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
  const reader = JSON.parse(read("packages/optics-record-reader/package.json"));
  const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
  const workspace = read("pnpm-workspace.yaml");
  assert.equal(cli.version, "0.3.24");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.equal(contract.version, "0.0.0-unstable-pre-1.0");
  assert.equal(vocabulary.version, "0.0.0-unstable-pre-1.0");
  assert.equal(adapter.version, "0.0.0-unstable-pre-1.0");
  assert.match(python, /version = "3.1.0"/);
  assert.equal(reader.private, true);
  assert.equal(reader.version, "0.0.0-unstable-pre-1.0");
  assert.equal(workspace.includes("optics-record-reader"), false);
  assert.equal(workspace.includes("optics-node-adapter"), false);
});

test("live CLI, SDK, and publish workflows do not import the reader", () => {
  const roots = [
    path.join(ROOT, "packages/vantio-cli"),
    path.join(ROOT, "packages/vantio-agent-sdk"),
    path.join(ROOT, "packages/vantio-agent-sdk-py"),
  ];
  for (const root of roots) {
    for (const file of walk(root, [])) {
      if (!file.endsWith(".js") && !file.endsWith(".cjs") && !file.endsWith(".mjs") && !file.endsWith(".py")) continue;
      const text = fs.readFileSync(file, "utf8");
      assert.equal(text.includes("optics-record-reader"), false, file);
      assert.equal(text.includes("readRunFile"), false, file);
    }
  }
  const workflows = walk(path.join(ROOT, ".github/workflows"), []);
  for (const file of workflows) {
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("optics-record-reader"), false, file);
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

test("committed and uncommitted paths stay inside Unit F", () => {
  const committed = parseDiffZ(gitZ(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(gitZ(["status", "--porcelain=v1", "-z"]));
  assertScoped(committed);
  assertScoped(uncommitted);
});

test("internal docs carry the inert banner and the council classification", () => {
  for (const name of DOCS) {
    const text = read(path.join("docs/internal/optics-pkg02-unit-f", name));
    assert.equal(text.includes(BANNER), true, name);
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
  }
  const report = read("docs/internal/optics-pkg02-unit-f/IMPLEMENTATION-REPORT.md");
  assert.equal(report.includes("OPTICS_PKG02_UNIT_F_READY_FOR_COUNCIL"), true);
  assert.equal(report.includes("NOT_AUTHORIZED"), true);
});
}
