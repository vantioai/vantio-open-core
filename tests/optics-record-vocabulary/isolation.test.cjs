"use strict";

const assert = require("node:assert/strict");
const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/optics-record-vocabulary/src/index.cjs");
const { writeVocabulary } = require("../../packages/optics-record-vocabulary/tools/build-vocabulary.cjs");
const { writeFixtures } = require("../../packages/optics-record-vocabulary/tools/emit-fixtures.cjs");

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
const BASE = "14249ba84ff1f3d5aa8ad7a7366172f29235c76e";

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

function normalizeGitPath(file) {
  return String(file).replace(/\\/g, "/").replace(/^\.\//, "");
}

function scopeViolation(file) {
  const normalized = normalizeGitPath(file);
  if (normalized.length === 0) return null;
  if (ALLOWED_PREFIXES.some((prefix) => normalized.startsWith(prefix))) return null;
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

test("committed and uncommitted paths stay inside Unit A", () => {
  assert.deepEqual(parseStatusZ(""), []);
  assertScoped([]);
  const renamed = parseStatusZ("R  packages/vantio-cli/package.json\0packages/optics-record-vocabulary/src/index.cjs\0");
  assert.deepEqual(renamed, [
    "packages/vantio-cli/package.json",
    "packages/optics-record-vocabulary/src/index.cjs",
  ]);
  assert.equal(scopeViolation(renamed[0]), renamed[0]);
  assert.equal(scopeViolation(renamed[1]), null);

  const committed = parseDiffZ(gitZ(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(gitZ(["status", "--porcelain=v1", "-z"]));
  assert.ok(committed.includes("packages/optics-record-vocabulary/vocabulary/record-vocabulary.json"));
  assertScoped(committed);
  assertScoped(uncommitted);
});

test("an out-of-scope path is named without reading the file", () => {
  const outside = "packages/vantio-cli/package.json";
  assert.throws(
    () => assertScoped([outside]),
    (error) => error.message.includes("out-of-scope path: " + outside),
  );
  assert.equal(scopeViolation("docs/internal/optics-pkg02-unit-a/BOUNDARY.md"), null);
  assert.equal(scopeViolation("tests/optics-record-vocabulary/isolation.test.cjs"), null);
});

test("direct builder invocation cannot write outside the sandbox", () => {
  const outsideDir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-a-scope-"));
  const outside = path.join(outsideDir, "escape.json");
  const outsideFile = path.join(outsideDir, "file-escape.json");
  const link = path.join(PACKAGE_ROOT, "vocabulary", "sandbox-link-probe");
  const vocabFileLink = path.join(PACKAGE_ROOT, "vocabulary", "file-symlink-probe.json");
  const fixtureFileLink = path.join(PACKAGE_ROOT, "fixtures", "file-symlink-probe.json");
  const originalWrite = fs.writeFileSync;
  try {
    assert.throws(() => writeVocabulary(outside), (error) => error.code === "PATH_OUTSIDE_SANDBOX");
    assert.throws(() => writeFixtures(outside), (error) => error.code === "PATH_OUTSIDE_SANDBOX");
    assert.equal(fs.existsSync(outside), false);

    fs.symlinkSync(outsideDir, link, "dir");
    assert.throws(
      () => writeVocabulary(path.join(link, "escape.json")),
      (error) => error.code === "PATH_OUTSIDE_SANDBOX",
    );
    assert.equal(fs.existsSync(outside), false);

    fs.writeFileSync(outsideFile, "sealed");
    fs.symlinkSync(outsideFile, vocabFileLink);
    fs.symlinkSync(outsideFile, fixtureFileLink);
    assert.throws(() => writeVocabulary(vocabFileLink), (error) => error.code === "PATH_OUTSIDE_SANDBOX");
    assert.throws(() => writeFixtures(fixtureFileLink), (error) => error.code === "PATH_OUTSIDE_SANDBOX");
    assert.equal(fs.readFileSync(outsideFile, "utf8"), "sealed");
    const buildLink = spawnSync(process.execPath, [path.join(PACKAGE_ROOT, "tools", "build-vocabulary.cjs"), vocabFileLink], {
      encoding: "utf8",
    });
    const emitLink = spawnSync(process.execPath, [path.join(PACKAGE_ROOT, "tools", "emit-fixtures.cjs"), fixtureFileLink], {
      encoding: "utf8",
    });
    assert.notEqual(buildLink.status, 0);
    assert.notEqual(emitLink.status, 0);
    assert.match(buildLink.stderr, /PATH_OUTSIDE_SANDBOX/);
    assert.match(emitLink.stderr, /PATH_OUTSIDE_SANDBOX/);
    assert.equal(fs.readFileSync(outsideFile, "utf8"), "sealed");
    assert.equal(fs.lstatSync(vocabFileLink).isSymbolicLink(), true);
    assert.equal(fs.lstatSync(fixtureFileLink).isSymbolicLink(), true);

    const calls = [];
    fs.writeFileSync = (file) => {
      calls.push(String(file));
    };
    writeVocabulary(path.join(PACKAGE_ROOT, "vocabulary", "sandbox-probe.json"));
    writeFixtures(path.join(PACKAGE_ROOT, "fixtures", "sandbox-probe.json"));
    fs.writeFileSync = originalWrite;
    assert.equal(calls.length, 2);
    for (const file of calls) {
      const relative = path.relative(PACKAGE_ROOT, file).replace(/\\/g, "/");
      assert.equal(relative.startsWith("vocabulary/") || relative.startsWith("fixtures/"), true, relative);
    }

    const build = spawnSync(process.execPath, [path.join(PACKAGE_ROOT, "tools", "build-vocabulary.cjs"), outside], {
      encoding: "utf8",
    });
    const emit = spawnSync(process.execPath, [path.join(PACKAGE_ROOT, "tools", "emit-fixtures.cjs"), outside], {
      encoding: "utf8",
    });
    assert.notEqual(build.status, 0);
    assert.notEqual(emit.status, 0);
    assert.match(build.stderr, /PATH_OUTSIDE_SANDBOX/);
    assert.match(emit.stderr, /PATH_OUTSIDE_SANDBOX/);
    assert.equal(fs.existsSync(outside), false);
  } finally {
    fs.writeFileSync = originalWrite;
    for (const probe of [link, vocabFileLink, fixtureFileLink]) {
      try {
        if (fs.lstatSync(probe).isSymbolicLink()) fs.unlinkSync(probe);
      } catch (_error) {
        // The probe was not created.
      }
    }
    fs.rmSync(outsideDir, { recursive: true, force: true });
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
