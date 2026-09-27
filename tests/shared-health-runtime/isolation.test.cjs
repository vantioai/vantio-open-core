"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { produce } = require("../../packages/shared-health-runtime/src/index.cjs");
const contract = require("../../packages/shared-health-runtime/contract.json");
const { OPTIONS, ROOT, baseInput, enforcingFact } = require("./helpers.cjs");

const SOURCE_DIR = path.join(ROOT, "packages/shared-health-runtime/src");

function sourceText() {
  return fs.readdirSync(SOURCE_DIR)
    .filter((name) => name.endsWith(".cjs"))
    .map((name) => fs.readFileSync(path.join(SOURCE_DIR, name), "utf8"))
    .join("\n");
}

test("the runtime does not import live enforcement, network, or process execution", () => {
  const text = sourceText();
  for (const banned of ["child_process", "node:net", "node:http", "node:https", "node:dgram", "node:tls", "bpf", "SSL_write", "kubectl", "tc_enforce"]) {
    assert.equal(text.includes(banned), false, banned);
  }
  const produceText = fs.readFileSync(path.join(SOURCE_DIR, "produce.cjs"), "utf8");
  const consumeText = fs.readFileSync(path.join(SOURCE_DIR, "consume.cjs"), "utf8");
  assert.equal(produceText.includes("readFileSync"), false);
  assert.equal(produceText.includes("writeFile"), false);
  assert.equal(consumeText.includes("readFileSync"), false);
  assert.equal(consumeText.includes("writeFile"), false);
});

test("shipping packages and the frozen SDK surfaces do not import the runtime", () => {
  const roots = [
    "packages/vantio-cli",
    "packages/vantio-agent-sdk",
    "packages/vantio-agent-sdk-py",
    "packages/vantio-gate-mcp",
    "packages/vantio-optics-mcp",
  ];
  for (const rel of roots) {
    const text = walk(path.join(ROOT, rel));
    assert.equal(text.includes("shared-health-runtime"), false, rel);
  }
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const sdk = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.equal(sdk.version, "0.2.4");
  assert.match(python, /version = "3.1.0"/);
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("shared-health-runtime"), false);
});

test("the bound catalog directory and status tokens are not extended by this package", () => {
  const home = fs.readdirSync(path.join(ROOT, "docs/planning/shared-health-vocabulary")).sort();
  assert.deepEqual(home, [
    "00-BOUNDARY.md",
    "01-CATALOG.md",
    "BINDINGS.md",
    "COLLISION-MATRIX.json",
    "HEALTH-VOCABULARY.json",
    "INDEPENDENT-COUNCIL.md",
    "PLANNING-MANIFEST.json",
  ]);
  const tokens = fs.readFileSync(path.join(ROOT, "docs/governance/STATUS-TOKENS.json"), "utf8");
  assert.equal(tokens.includes("HEALTHY_ENFORCING"), false);
  assert.equal(tokens.includes("HEALTHY_OBSERVING"), false);
  const subjects = JSON.parse(fs.readFileSync(path.join(
    ROOT,
    "docs/planning/shared-health-vocabulary/HEALTH-VOCABULARY.json",
  ), "utf8")).subjects;
  assert.deepEqual(subjects, ["ARTIFACT", "HOST_PREREQUISITE", "LOADER", "COVERAGE", "CONTROL_PLANE", "LEDGER"]);
  assert.equal(subjects.includes("OPTICS"), false);
  assert.equal(contract.catalog_commit, "c1de02538f66df94d58aef58bf0ec8459ae797ad");
});

test("producing a state does not write a file", () => {
  const probe = path.join(ROOT, "packages/shared-health-runtime/.write-probe");
  assert.equal(fs.existsSync(probe), false);
  produce(baseInput({ facts: [enforcingFact()] }), OPTIONS);
  assert.equal(fs.existsSync(probe), false);
  const listing = fs.readdirSync(path.join(ROOT, "packages/shared-health-runtime"));
  assert.equal(listing.includes(".write-probe"), false);
});

function walk(dir) {
  let text = "";
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === "dist") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) text += walk(full);
    else if (/\.(cjs|js|mjs|ts|py|json|toml|md)$/.test(entry.name)) text += fs.readFileSync(full, "utf8");
  }
  return text;
}
