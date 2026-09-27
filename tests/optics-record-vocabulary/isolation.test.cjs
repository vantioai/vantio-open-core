"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/optics-record-vocabulary/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/optics-record-vocabulary");
const DOCS = [
  "BOUNDARY.md",
  "VOCABULARY.md",
  "ALIASES.md",
  "COMPATIBILITY-FIXTURES.md",
  "NO-OPTIMISTIC-DEFAULTS.md",
  "KNOWN-LIMITATIONS.md",
  "IMPLEMENTATION-REPORT.md",
];
const BANNER = "PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA";
const ALLOWED_PREFIXES = [
  "packages/optics-record-vocabulary/",
  "tests/optics-record-vocabulary/",
  "docs/internal/optics-pkg02-unit-a/",
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

test("public API is vocabulary checks, not a converter or writer", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "POSTURE",
    "canonicalJson",
    "comparisonDocument",
    "evaluateFixture",
    "evaluateFixtures",
    "inspectAliasGraph",
    "loadFixtures",
    "loadVocabulary",
    "validateVocabulary",
  ]);
  for (const name of ["convertRecord", "migrate", "writeRun", "adaptRecord", "legacyEnvelopeToContract"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
});

test("package source does not import products or write files", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
    /require\(["'][^"']*optics-evidence-contract/,
    /writeFile/,
    /appendFile/,
    /sqlite/i,
    /child_process/,
    /~\/\.vantio/,
    /validate\.cjs/,
    /privacy\.py/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, file + " " + pattern);
  }
});

test("evaluation does not write the filesystem", () => {
  const vocabulary = api.loadVocabulary();
  const fixtures = api.loadFixtures();
  const calls = [];
  const original = fs.writeFileSync;
  fs.writeFileSync = (...args) => {
    calls.push(String(args[0]));
    return original.apply(fs, args);
  };
  try {
    const result = api.evaluateFixtures(fixtures, vocabulary);
    assert.equal(result.ok, true, result.errors.join("\n"));
    assert.deepEqual(calls, []);
  } finally {
    fs.writeFileSync = original;
  }
});

test("frozen package versions are unchanged", () => {
  const cli = JSON.parse(read("packages/vantio-cli/package.json"));
  const nodeSdk = JSON.parse(read("packages/vantio-agent-sdk/package.json"));
  const contract = JSON.parse(read("packages/optics-evidence-contract/package.json"));
  const vocabulary = JSON.parse(read("packages/optics-record-vocabulary/package.json"));
  const python = read("packages/vantio-agent-sdk-py/pyproject.toml");
  assert.equal(cli.version, "0.3.24");
  assert.equal(nodeSdk.version, "0.2.4");
  assert.equal(contract.version, "0.0.0-unstable-pre-1.0");
  assert.match(python, /version = "3.1.0"/);
  assert.equal(vocabulary.private, true);
  assert.equal(vocabulary.version, "0.0.0-unstable-pre-1.0");
  const workspace = read("pnpm-workspace.yaml");
  assert.equal(workspace.includes("optics-record-vocabulary"), false);
});

test("the worktree stays inside Unit A paths", () => {
  const output = execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8" });
  const files = output
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => line.slice(3).trim());
  assert.ok(files.length > 0);
  for (const file of files) {
    assert.equal(
      ALLOWED_PREFIXES.some((prefix) => file.startsWith(prefix)),
      true,
      file,
    );
  }
});

test("internal docs carry the inert banner", () => {
  for (const name of DOCS) {
    const text = read(path.join("docs/internal/optics-pkg02-unit-a", name));
    assert.equal(text.includes(BANNER), true, name);
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
  }
  const report = read("docs/internal/optics-pkg02-unit-a/IMPLEMENTATION-REPORT.md");
  assert.equal(report.includes("OPTICS_PKG02_UNIT_A_READY_FOR_COUNCIL"), true);
});
