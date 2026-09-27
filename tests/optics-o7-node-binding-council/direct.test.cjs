"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

const decision = readJson("docs/internal/optics-o7/BINDING-DECISION.json");
const council = readJson("docs/programs/production-readiness/wave3/O7-NODE-BINDING-DECISION.json");

test("the council passes one binding and pins the runtime floor", () => {
  assert.equal(decision.verdict, "O7_NODE_BINDING_COUNCIL_PASSED");
  assert.equal(council.verdict, "O7_NODE_BINDING_COUNCIL_PASSED");
  assert.equal(decision.selected_binding, "node:sqlite");
  assert.equal(decision.selected_version, "24.15.0");
  assert.equal(decision.selected_binding_at_version, "node:sqlite@24.15.0");
  assert.equal(council.selected_binding_at_version, "node:sqlite@24.15.0");
  assert.equal(decision.dependency_pin.npm, null);
  assert.equal(decision.dependency_pin.package_json_edited, false);
  assert.equal(decision.engine.remains, "embedded SQLite with WAL");
  assert.equal(council.engine_remains, "embedded SQLite with WAL");
});

test("the fallback is named and not installed", () => {
  assert.equal(decision.fallback.binding_at_version, "better-sqlite3@13.0.3");
  assert.equal(decision.fallback.installed, false);
  assert.equal(decision.fallback.load_on_primary_failure, false);
  assert.equal(council.fallback_binding_at_version, "better-sqlite3@13.0.3");
  assert.equal(council.fallback_installed, false);
  assert.equal(decision.operational_fallback, "FAIL_OPEN_NO_FILE");
  assert.equal(decision.rollback.automatic_switch_to_fallback_binding, false);
});

test("the decision does not claim runtime proof or open the gate", () => {
  assert.equal(decision.honesty.evidence_tier, "UNSET");
  assert.equal(decision.honesty.gate_8, "CLOSED");
  assert.equal(decision.honesty.runtime_proof, false);
  assert.equal(decision.honesty.stranger_host, false);
  assert.equal(decision.honesty.external_proof, "NOT_CLAIMED");
  assert.equal(decision.honesty.customer_migration, false);
  assert.equal(decision.honesty.default_write_path, false);
  assert.equal(decision.honesty.architecture_pack_amended, false);
  assert.equal(decision.honesty.running_open_store_reason, "NODE_BINDING_UNSELECTED");
  assert.equal(decision.honesty.running_founder_decision_9, "UNRESOLVED");
  assert.equal(council.evidence_tier, "UNSET");
  assert.equal(council.external_proof, "NOT_CLAIMED");
  assert.equal(council.runtime_proof, false);
  const unasserted = council.claims.find((claim) => claim.id === "CL-W3-O7-03");
  assert.equal(unasserted.status, "NOT_ASSERTED");
});

test("frozen manifests and the historical not-selected sentence stay put", () => {
  assert.equal(readJson("packages/vantio-cli/package.json").version, "0.3.24");
  assert.equal(readJson("packages/vantio-agent-sdk/package.json").version, "0.2.4");
  assert.match(readText("packages/vantio-agent-sdk-py/pyproject.toml"), /^version = "3.1.0"$/m);
  assert.equal(readJson("docs/governance/VERSION-METADATA.json").packages[0].version, "0.3.24");
  assert.equal(decision.release_impact.cli_modified, false);
  assert.equal(decision.release_impact.python_sdk_modified, false);
  assert.equal(decision.release_impact.version_metadata_edited, false);
  assert.match(
    readText("docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md"),
    /9\. Node SQLite binding\. Not selected\./,
  );
  assert.match(
    readText("docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md"),
    /\| 8 \| Implementation Force \|.*\| \*\*Closed\. Not started\*\* \|/,
  );
  const manifest = readJson("docs/planning/optics-o7-store/STORE-MANIFEST.json");
  assert.equal(manifest.founder_decision_9, "UNRESOLVED");
  assert.equal(manifest.node_binding, "UNSELECTED");
});

test("no package manifest gained a sqlite dependency and the facade still refuses", () => {
  const banned = new Set(["sqlite3", "better-sqlite3", "better-sqlite", "node:sqlite"]);
  const files = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name === ".git") continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name === "package.json") files.push(full);
    }
  }
  walk(ROOT);
  for (const full of files) {
    const body = JSON.parse(fs.readFileSync(full, "utf8"));
    for (const field of ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]) {
      for (const name of Object.keys(body[field] || {})) {
        assert.equal(banned.has(name), false, full + " " + name);
      }
    }
  }
  const source = readText("packages/optics-operational-store/src/open.cjs");
  assert.equal(source.includes("node:sqlite"), false);
  assert.equal(source.includes("better-sqlite"), false);
  const store = require("../../packages/optics-operational-store/src/index.cjs");
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "o7-binding-council-"));
  try {
    const opened = store.openStore({ evidenceRoot: dir, create: true, sqlite: true });
    assert.equal(opened.reason_code, "NODE_BINDING_UNSELECTED");
    assert.equal(opened.file_created, false);
    assert.equal(opened.founder_decision_9, "UNRESOLVED");
    assert.equal(fs.existsSync(path.join(dir, "optics", "store.sqlite")), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
