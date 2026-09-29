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

const api = require("../../packages/pe-ingress-authority/src/index.cjs");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/pe-ingress-authority");
const BASE = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";
const ALLOWED_PREFIXES = [
  "packages/pe-ingress-authority/",
  "tests/pe-ingress/",
  "docs/internal/pe-ingress/",
];

function walk(directory, files) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else files.push(absolute);
  }
  return files;
}

test("public API exposes the decision surface and no loader or deploy verbs", () => {
  assert.deepEqual(Object.keys(api).sort(), [
    "AUDIENCE",
    "FRESHNESS_RULE",
    "NOT_PRESENT",
    "PACKET_PLANE",
    "PRECEDENCE",
    "PROGRAM",
    "PROGRAM_CLASSIFICATION",
    "PROTECTION_STATES",
    "REASONS",
    "classifyListeners",
    "evaluateIngress",
    "listenerMatches",
    "lookupGrant",
    "openSession",
    "restartSession",
    "revokeActive",
    "rollbackSession",
  ]);
  for (const name of ["load", "deploy", "freeze", "attach", "publish", "seal", "execute"]) {
    assert.equal(Object.prototype.hasOwnProperty.call(api, name), false);
  }
  assert.equal(api.PROGRAM_CLASSIFICATION, "PE_INGRESS_PROGRAM_READY_FOR_COUNCIL");
  assert.equal(api.PACKET_PLANE, "OBSERVE_ONLY");
  assert.equal(api.FRESHNESS_RULE, "FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN");
});

test("package source does not touch the filesystem, network, or loader", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["']fs["']\)/,
    /require\(["']child_process["']\)/,
    /require\(["']net["']\)/,
    /require\(["']dgram["']\)/,
    /writeFile/,
    /appendFile/,
    /execFile/,
    /execSync/,
    /spawn\(/,
    /sudo/,
    /TC_ACT/,
    /bpf_override/,
    /vantio-loader/,
    /\/sys\/fs\/bpf/,
    /require\(["'][^"']*vantio-cli/,
    /require\(["'][^"']*vantio-agent-sdk/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) {
      assert.equal(pattern.test(text), false, `${path.relative(ROOT, file)} matched ${pattern}`);
    }
  }
});

test("the package is private and outside the pnpm workspace", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(manifest.private, true);
  assert.equal(manifest.version, "0.0.0-internal");
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("pe-ingress-authority"), false);
});

test("this force does not edit CLI 0.3.24, Python 3.1.0, or other trees", () => {
  const status = execFileSync("git", ["status", "--porcelain"], { cwd: ROOT, encoding: "utf8" });
  const diff = execFileSync("git", ["diff", "--name-only", BASE], { cwd: ROOT, encoding: "utf8" });
  const touched = new Set();
  for (const line of status.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    touched.add(trimmed.slice(3));
  }
  for (const line of diff.split("\n")) {
    const trimmed = line.trim();
    if (trimmed) touched.add(trimmed);
  }
  assert.ok(touched.size > 0);
  for (const relative of touched) {
    assert.equal(
      ALLOWED_PREFIXES.some((prefix) => relative.startsWith(prefix)),
      true,
      relative,
    );
  }
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  assert.equal(cli.version, "0.3.24");
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.match(python, /^version = "3.1.0"$/m);
});

test("internal notes keep the council pending and name the producer classification", () => {
  const docs = walk(path.join(ROOT, "docs/internal/pe-ingress"), []);
  assert.ok(docs.length > 0);
  const joined = docs.map((file) => fs.readFileSync(file, "utf8")).join("\n");
  assert.equal(joined.includes("PE_INGRESS_PROGRAM_READY_FOR_COUNCIL"), true);
  assert.equal(joined.includes("PENDING_INDEPENDENT_COUNCIL"), true);
  assert.equal(joined.includes("COUNCIL_PASSED"), false);
  assert.equal(joined.includes("PE_INGRESS_PROGRAM_COUNCIL_PASSED"), false);
});
}
