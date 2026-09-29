"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { test: privateTreeSkipTest } = require("node:test");

if (!fs.existsSync(path.resolve(__dirname, "../../docs/internal"))) {
  privateTreeSkipTest("docs/internal", { skip: "PRIVATE_TREE_REMOVED_FROM_PUBLIC_TIP" }, () => {});
} else {
"use strict";

const assert = require("node:assert/strict");
const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/vantio-cli-pkg02/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const BASE = "dd3344dcc636136ed22df75e8df3866c993efd27";
const ALLOWED_PREFIXES = [
  "docs/internal/optics-pkg02-unit-d/",
  "docs/planning/optics-pkg02/04-COMPATIBILITY-MATRIX.md",
  "docs/planning/optics-pkg02/RECORD-COMPATIBILITY-MATRIX.json",
  "packages/vantio-cli-pkg02/",
  "tests/optics-pkg02-unit-d/",
];
const FROZEN = [
  "packages/vantio-agent-sdk",
  "packages/vantio-agent-sdk-py",
  "packages/vantio-cli",
  "packages/optics-evidence-contract",
  "packages/optics-node-adapter",
  "packages/optics-record-reader",
  "packages/optics-reader-compat-gates",
];

function git(args) {
  return execFileSync("git", args, { cwd: ROOT, encoding: "utf8" });
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

function outside(file) {
  const normalized = String(file).replace(/\\/g, "/").replace(/^\.\//, "");
  if (!normalized) return null;
  if (ALLOWED_PREFIXES.some((prefix) => normalized === prefix || normalized.startsWith(prefix))) return null;
  return normalized;
}

test("this unit does not edit frozen trees and stays inside its paths", () => {
  const committed = parseDiffZ(git(["diff", "-z", "--name-only", BASE, "HEAD"]));
  const uncommitted = parseStatusZ(git(["status", "--porcelain=v1", "-z"]));
  const violations = committed.concat(uncommitted).map(outside).filter(Boolean);
  assert.deepEqual(violations, []);
  for (const tree of FROZEN) {
    const diff = git(["diff", "--name-only", BASE, "HEAD", "--", tree]).trim();
    const dirty = git(["diff", "--name-only", "HEAD", "--", tree]).trim();
    assert.equal(diff, "", tree);
    assert.equal(dirty, "", tree);
  }
});

test("frozen package versions stay put and Unit E is not activated", () => {
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const future = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli-pkg02/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3.1.0"/);
  assert.equal(future.version, "0.4.0-pkg02-unit-d");
  assert.equal(future.private, true);
  assert.equal(future.vantio.activates_unit_d, true);
  assert.equal(future.vantio.activates_unit_e, false);
  assert.equal(future.vantio.shipped_product, false);
  assert.equal(api.activates_unit_d, true);
  assert.equal(api.activates_unit_e, false);
  assert.equal(api.shipped_product, false);
  assert.equal(workspace.includes("vantio-cli-pkg02"), false);
  assert.equal(fs.existsSync(path.join(ROOT, "packages/optics-future-python")), false);
});

test("internal notes stay internal and do not claim a council pass", () => {
  const dir = path.join(ROOT, "docs/internal/optics-pkg02-unit-d");
  const names = fs.readdirSync(dir).filter((name) => name.endsWith(".md"));
  assert.equal(names.includes("IMPLEMENTATION-REPORT.md"), true);
  for (const name of names) {
    const text = fs.readFileSync(path.join(dir, name), "utf8");
    assert.equal(text.includes("INTERNAL_RESTRICTED"), true, name);
    assert.equal(text.includes("COUNCIL_PASSED"), false, name);
    assert.equal(text.includes("NOT PUBLISHED"), true, name);
  }
  const report = fs.readFileSync(path.join(dir, "IMPLEMENTATION-REPORT.md"), "utf8");
  assert.equal(report.includes("OPTICS_PKG02_UNIT_D_READY_FOR_COUNCIL"), true);
  assert.equal(report.includes("activates_unit_e"), true);
});

test("the future launcher does not start a Python writer", () => {
  const child = spawnSync(process.execPath, [
    path.join(ROOT, "packages/vantio-cli-pkg02/bin/vantio-future.cjs"),
    "run",
    "python3",
    "-c",
    "print(1)",
  ], { encoding: "utf8" });
  assert.equal(child.status, 1);
  assert.equal(String(child.stdout || "").includes("1"), false);
});
}
