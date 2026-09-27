"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const PACKAGE_ROOT = path.join(ROOT, "packages/pe-progressive-enforcement");

function walk(directory, files) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(absolute, files);
    else files.push(absolute);
  }
  return files;
}

test("package source does not touch the network, the filesystem, or a live product", () => {
  const files = walk(path.join(PACKAGE_ROOT, "src"), []);
  const banned = [
    /require\(["']fs["']\)/,
    /require\(["']node:fs["']\)/,
    /require\(["']http["']\)/,
    /require\(["']https["']\)/,
    /require\(["']net["']\)/,
    /require\(["']child_process["']\)/,
    /require\(["']undici["']\)/,
    /fetch\(/,
    /writeFile/,
    /appendFile/,
    /process\.env/,
    /vantio-cli/,
    /vantio-agent-sdk/,
    /optics-evidence-contract/,
    /child_process/,
  ];
  for (const file of files) {
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of banned) assert.equal(pattern.test(text), false, `${file} ${pattern}`);
  }
});

test("the package stays private and outside the workspace", () => {
  const workspace = fs.readFileSync(path.join(ROOT, "pnpm-workspace.yaml"), "utf8");
  assert.equal(workspace.includes("pe-progressive-enforcement"), false);
  const meta = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(meta.private, true);
  assert.equal(meta.version, "0.0.0-unstable-pre-1.0");
  assert.equal(Object.hasOwn(meta, "dependencies"), false);
});

test("live packages do not load the lifecycle", () => {
  const roots = [
    "packages/vantio-cli",
    "packages/vantio-agent-sdk",
    "packages/vantio-agent-sdk-py",
    "packages/vantio-gate-mcp",
    "packages/vantio-optics-mcp",
  ];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === "dist") continue;
      const absolute = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (/\.(js|cjs|mjs|ts|py|json)$/.test(entry.name)) {
        const text = fs.readFileSync(absolute, "utf8");
        assert.equal(text.includes("pe-progressive-enforcement"), false, absolute);
      }
    }
  }
  for (const relative of roots) visit(path.join(ROOT, relative));
  const cli = JSON.parse(fs.readFileSync(path.join(ROOT, "packages/vantio-cli/package.json"), "utf8"));
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.equal(cli.version, "0.3.24");
  assert.match(python, /version = "3\.1\.0"/);
});

test("new lifecycle files do not use retired public names", () => {
  const files = walk(PACKAGE_ROOT, []).concat(walk(path.join(ROOT, "docs/internal/pe-progressive-enforcement"), []));
  files.push(...walk(path.join(ROOT, "tests/pe-progressive-enforcement"), []));
  const retired = [
    new RegExp(["Sight", "Loop"].join(" ")),
    new RegExp(["sight", "loop"].join("-")),
    new RegExp(["sight", "loop"].join("_")),
    new RegExp(["Shadow", "AI"].join(" ")),
    new RegExp(["shadow", "ai"].join("-")),
  ];
  for (const file of files) {
    if (!/\.(cjs|md|json)$/.test(file)) continue;
    const text = fs.readFileSync(file, "utf8");
    for (const pattern of retired) assert.equal(pattern.test(text), false, `${file} ${pattern}`);
  }
});

test("the council slot stays pending", () => {
  const manifest = JSON.parse(fs.readFileSync(
    path.join(ROOT, "docs/internal/pe-progressive-enforcement/MANIFEST.json"),
    "utf8",
  ));
  assert.equal(manifest.producer_classification, "PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL");
  assert.equal(manifest.council_status, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(manifest.council_verdict, null);
  assert.equal(manifest.self_certified_council_pass, false);
  assert.equal(manifest.auto_enforce_from_observation, false);
  assert.equal(manifest.host_attachment, "NOT_PERFORMED");
  const slot = fs.readFileSync(path.join(ROOT, "docs/internal/pe-progressive-enforcement/05-COUNCIL-SLOT.md"), "utf8");
  assert.match(slot, /PENDING_INDEPENDENT_COUNCIL/);
  assert.equal(slot.includes("COUNCIL_PASS"), false);
});
