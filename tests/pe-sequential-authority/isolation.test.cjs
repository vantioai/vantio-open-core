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

const api = require("../../packages/pe-sequential-authority/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/pe-sequential-authority");
const BASE = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";
const BANNER = "INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA";
const DOCS = [
  "BOUNDARY.md",
  "DESIGN.md",
  "IMPLEMENTATION-REPORT.md",
  "INVARIANTS.md",
  "KNOWN-LIMITATIONS.md",
  "NO-OPTIMISTIC-DEFAULTS.md",
  "PENDING-COUNCIL.md",
];
const ALLOWED_PREFIXES = [
  "packages/pe-sequential-authority/",
  "tests/pe-sequential-authority/",
  "docs/internal/pe-sequential-authority/",
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

test("public API is the evaluate-only candidate", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "AUDIENCE",
    "AUTHORITY_SOURCES",
    "CLASSIFICATION",
    "COMPOSITIONS",
    "COUNCIL_STATUS",
    "ENFORCEMENT",
    "INVARIANTS",
    "LIMIT_AXES",
    "PACKAGE_NAME",
    "PACKAGE_VERSION",
    "POSTURE",
    "RESERVED_DOMAINS",
    "RESERVED_RIGHTS",
    "RULES",
    "SCHEMA_STATUS",
    "SCHEMA_VERSION",
    "STARTING_REF",
    "emptyLedger",
    "evaluate",
    "proposeDelegation",
    "revoke",
  ]);
  assert.equal(api.CLASSIFICATION, "PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL");
  assert.equal(api.COUNCIL_STATUS, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(api.PACKAGE_NAME, "@vantio/pe-sequential-authority");
  assert.equal(api.PACKAGE_VERSION, "0.0.0-unstable-pre-1.0");
  assert.equal(api.SCHEMA_VERSION, 0);
  assert.equal(api.ENFORCEMENT, "EVALUATE_ONLY");
  assert.equal(api.STARTING_REF, BASE);
  assert.equal(api.INVARIANTS.length, 9);
  assert.equal(api.LIMIT_AXES.length, 12);
  for (const name of ["enroll", "loadBpf", "publish", "fetchPolicy", "writeFile"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
});

test("candidate source does not touch the network, the filesystem, or live packages", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["']node:fs["']\)/,
    /require\(["']fs["']\)/,
    /require\(["']node:child_process["']\)/,
    /require\(["']child_process["']\)/,
    /require\(["']node:net["']\)/,
    /require\(["']node:http["']\)/,
    /vantio-cli/,
    /vantio-agent-sdk/,
    /writeFile/,
    /createWriteStream/,
    /fetch\(/,
  ];
  assert.equal(files.length > 0, true);
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
    assert.equal(text.includes("COUNCIL_PASSED"), false, file);
  }
});

test("frozen package versions are unchanged and this package stays private", () => {
  const cli = JSON.parse(read("packages/vantio-cli/package.json"));
  const nodeSdk = JSON.parse(read("packages/vantio-agent-sdk/package.json"));
  const candidate = JSON.parse(read("packages/pe-sequential-authority/package.json"));
  const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
  const workspace = read("pnpm-workspace.yaml");
  assert.equal(cli.version, "0.3.25");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.match(python, /version = "3.1.1"/);
  assert.equal(candidate.private, true);
  assert.equal(candidate.version, "0.0.0-unstable-pre-1.0");
  assert.equal(workspace.includes("pe-sequential-authority"), false);
});

test("live CLI, SDK, and workflows do not import the candidate", () => {
  const roots = [
    path.join(ROOT, "packages/vantio-cli"),
    path.join(ROOT, "packages/vantio-agent-sdk"),
    path.join(ROOT, "packages/vantio-agent-sdk-py"),
    path.join(ROOT, "packages/vantio-gate-mcp"),
  ];
  for (const root of roots) {
    for (const file of walk(root, [])) {
      if (!file.endsWith(".js") && !file.endsWith(".cjs") && !file.endsWith(".mjs") && !file.endsWith(".py") && !file.endsWith(".ts")) {
        continue;
      }
      const text = fs.readFileSync(file, "utf8");
      assert.equal(text.includes("pe-sequential-authority"), false, file);
    }
  }
  for (const file of walk(path.join(ROOT, ".github/workflows"), [])) {
    const text = fs.readFileSync(file, "utf8");
    assert.equal(text.includes("pe-sequential-authority"), false, file);
  }
});

test("CLI and Python trees match the starting commit byte for byte", () => {
  execFileSync("git", ["diff", "--exit-code", BASE, "--", "packages/vantio-cli", "packages/vantio-agent-sdk-py", "pnpm-workspace.yaml", ".github"], {
    cwd: ROOT,
    encoding: "utf8",
  });
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

test("committed and uncommitted paths stay inside the candidate", () => {
  const committed = parseDiffZ(gitZ(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(gitZ(["status", "--porcelain=v1", "-z"]));
  assertScoped(committed);
  assertScoped(uncommitted);
});

test("internal docs carry the candidate banner and leave the council pending", () => {
  for (const name of DOCS) {
    const text = read(path.join("docs/internal/pe-sequential-authority", name));
    assert.equal(text.includes(BANNER), true, name);
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
  }
  const report = read("docs/internal/pe-sequential-authority/IMPLEMENTATION-REPORT.md");
  assert.equal(report.includes("PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL"), true);
  const pending = read("docs/internal/pe-sequential-authority/PENDING-COUNCIL.md");
  assert.equal(pending.includes("PENDING_INDEPENDENT_COUNCIL"), true);
});
}
