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

const api = require("../../packages/optics-reader-compat-gates/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-reader-compat-gates");
const BASE = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";
const BANNER = "PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA";
const DOCS = [
  "ARCHITECTURE-COUNCIL-NOTES.md",
  "BOUNDARY.md",
  "DESIGN.md",
  "GATE-CATALOG.md",
  "IMPLEMENTATION-REPORT.md",
  "INVENTORY.md",
  "KNOWN-LIMITATIONS.md",
  "NO-WRITER.md",
];
const ALLOWED_PREFIXES = [
  "docs/internal/optics-pkg02-reader-compat-gates/",
  "packages/optics-reader-compat-gates/",
  "tests/optics-pkg02-reader-compat-gates/",
];
const FROZEN_TREES = [
  "packages/vantio-agent-sdk",
  "packages/vantio-agent-sdk-py",
  "packages/vantio-cli",
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

test("public API is an inert gate evaluator", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "ACHIEVEMENT",
    "AUDIENCE",
    "CLASSIFICATION_BLOCKED",
    "CLASSIFICATION_READY",
    "FROZEN_CLI_VERSION",
    "FUTURE_CLI_PLACEHOLDER",
    "FUTURE_PYTHON_PLACEHOLDER",
    "GATE_IDS",
    "PACKAGE_VERSION",
    "POSTURE",
    "REQUIRED_ROLES",
    "SCHEMA_STATUS",
    "SCHEMA_VERSION",
    "UNITS_D_E",
    "evaluateEntryGates",
  ]);
  for (const name of ["writeRun", "activateWriter", "migrate", "promoteOrigin", "publish", "seal"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
  assert.equal(api.UNITS_D_E, "NOT_AUTHORIZED");
  assert.equal(api.FROZEN_CLI_VERSION, "0.3.24");
  assert.equal(api.FUTURE_CLI_PLACEHOLDER, "PKG02-FUTURE-CLI-UNASSIGNED");
  assert.equal(api.FUTURE_PYTHON_PLACEHOLDER, "PKG02-FUTURE-PYTHON-UNASSIGNED");
  assert.equal(api.SCHEMA_VERSION, 0);
  assert.equal(api.CLASSIFICATION_READY, "OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL");
  assert.equal(api.GATE_IDS.includes("mixed_version_directories"), true);
  assert.equal(api.GATE_IDS.includes("reader_refuses_unsafe_promotion"), true);
  assert.equal(api.GATE_IDS.includes("rollback_without_record_rewriting"), true);
});

test("gate source does not write files or import a writer", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /writeFile/,
    /appendFile/,
    /createWriteStream/,
    /unlinkSync/,
    /renameSync/,
    /rmSync/,
    /mkdirSync/,
    /copyFile/,
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
    /require\(["']sqlite/,
    /better-sqlite/,
    /node:sqlite/,
    /child_process/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
  }
});

test("frozen package versions stay unchanged and this package stays private", () => {
  const cli = JSON.parse(read("packages/vantio-cli/package.json"));
  const nodeSdk = JSON.parse(read("packages/vantio-agent-sdk/package.json"));
  const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
  const reader = JSON.parse(read("packages/optics-record-reader/package.json"));
  const gates = JSON.parse(read("packages/optics-reader-compat-gates/package.json"));
  const workspace = read("pnpm-workspace.yaml");
  const frozenDisplay = read("packages/vantio-cli/bin/optics-cx.cjs");
  assert.equal(cli.version, "0.3.25");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.match(python, /version = "3.1.1"/);
  assert.equal(reader.version, "0.0.0-unstable-pre-1.0");
  assert.equal(gates.private, true);
  assert.equal(gates.version, "0.0.0-unstable-pre-1.0");
  assert.equal(workspace.includes("optics-reader-compat-gates"), false);
  assert.equal(workspace.includes("optics-record-reader"), false);
  assert.match(frozenDisplay, /function opticsStatusForRecordedCall\(\) \{\n  return "SUCCESS";\n\}/);
});

test("live CLI, SDK, and publish workflows do not import the gate package", () => {
  const roots = [
    path.join(ROOT, "packages/vantio-cli"),
    path.join(ROOT, "packages/vantio-agent-sdk"),
    path.join(ROOT, "packages/vantio-agent-sdk-py"),
  ];
  for (const root of roots) {
    for (const file of walk(root, [])) {
      if (!file.endsWith(".js") && !file.endsWith(".cjs") && !file.endsWith(".mjs") && !file.endsWith(".py")) continue;
      const text = fs.readFileSync(file, "utf8");
      assert.equal(text.includes("optics-reader-compat-gates"), false, file);
      assert.equal(text.includes("evaluateEntryGates"), false, file);
    }
  }
  const workflows = walk(path.join(ROOT, ".github/workflows"), []);
  for (const file of workflows) {
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("optics-reader-compat-gates"), false, file);
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

test("this force stays inside the gate paths and leaves frozen trees byte-identical", () => {
  const committed = parseDiffZ(gitZ(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(gitZ(["status", "--porcelain=v1", "-z"]));
  const unstaged = parseDiffZ(gitZ(["diff", "-z", "--name-only", "HEAD"]));
  assertScoped(committed);
  assertScoped(uncommitted);
  assertScoped(unstaged);
  for (const tree of FROZEN_TREES) {
    const diff = gitZ(["diff", "--name-only", BASE, "HEAD", "--", tree]).trim();
    const dirty = gitZ(["diff", "--name-only", "HEAD", "--", tree]).trim();
    assert.equal(diff, "", tree);
    assert.equal(dirty, "", tree);
  }
});

test("internal docs carry the inert banner and the producer classification", () => {
  for (const name of DOCS) {
    const text = read(path.join("docs/internal/optics-pkg02-reader-compat-gates", name));
    assert.equal(text.includes(BANNER), true, name);
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
    assert.equal(text.includes("Sight Loop"), false, name);
    assert.equal(text.includes("sight_loop"), false, name);
  }
  const report = read("docs/internal/optics-pkg02-reader-compat-gates/IMPLEMENTATION-REPORT.md");
  assert.equal(report.includes("OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL"), true);
  assert.equal(report.includes("NOT_AUTHORIZED"), true);
  assert.equal(report.includes("89f95099d0dce463307eb75d78e7fcf2ef99feb2"), true);
});

test("no Unit D or Unit E package is added", () => {
  assert.equal(fs.existsSync(path.join(ROOT, "packages/optics-future-cli")), false);
  assert.equal(fs.existsSync(path.join(ROOT, "packages/optics-future-python")), false);
  const diff = gitZ(["diff", "--name-only", BASE, "HEAD"]);
  assert.equal(diff.includes("packages/vantio-cli/"), false);
  assert.equal(diff.includes("packages/vantio-agent-sdk-py/"), false);
  assert.equal(diff.includes("packages/vantio-agent-sdk/"), false);
});
}
