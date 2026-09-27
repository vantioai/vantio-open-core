"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const store = require("../../packages/optics-operational-store/src/index.cjs");
const reader = require("../../packages/optics-record-reader/src/boundary.cjs");

const ROOT = path.resolve(__dirname, "../..");

function readJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, rel), "utf8"));
}

test("node open does not create a store file", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "o7-node-"));
  const previous = process.env.VANTIO_HOME;
  process.env.VANTIO_HOME = dir;
  try {
    const opened = store.openStore({ create: true, sqlite: true, migrate: true, write: true, activate: true });
    assert.equal(opened.opened, false);
    assert.equal(opened.file_created, false);
    assert.equal(opened.writes_enabled, false);
    assert.equal(opened.application_continues, true);
    assert.equal(opened.default_write_path, false);
    assert.equal(opened.reason_code, "NODE_BINDING_UNSELECTED");
    assert.equal(opened.node_binding, "UNSELECTED");
    assert.equal(opened.founder_decision_9, "UNRESOLVED");
    assert.equal(opened.evidence_tier, "UNSET");
    assert.equal(opened.schema_status, "unstable-pre-1.0");
    assert.equal(fs.existsSync(path.join(dir, "optics", "store.sqlite")), false);
    const homeStore = path.join(os.homedir(), ".vantio", "optics", "store.sqlite");
    assert.equal(opened.store_path, path.join(dir, "optics", "store.sqlite"));
    assert.notEqual(opened.store_path, homeStore);
  } finally {
    if (previous === undefined) delete process.env.VANTIO_HOME;
    else process.env.VANTIO_HOME = previous;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("node put, get, and query reject caller sql and do not write", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "o7-node-sql-"));
  try {
    const handle = store.openStore({ evidenceRoot: dir });
    const putResult = store.put(handle, "DROP TABLE records", { applicationResult: { token: "APP" } });
    assert.equal(putResult.reason_code, "SQL_REJECTED");
    assert.equal(putResult.stored, false);
    assert.equal(putResult.application_continues, true);
    assert.equal(putResult.application_result.token, "APP");
    const named = store.put(handle, { sql: "DELETE FROM records" });
    assert.equal(named.reason_code, "SQL_REJECTED");
    const queried = store.query(handle, { sql: "SELECT * FROM records" });
    assert.equal(queried.reason_code, "SQL_REJECTED");
    assert.equal(queried.completeness, "UNAVAILABLE");
    assert.notEqual(queried.freshness, "CURRENT");
    assert.equal(fs.existsSync(path.join(dir, "optics", "store.sqlite")), false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("writer flags match PKG-02 data and the store does not import that package", () => {
  assert.deepEqual([...store.PKG02_WRITER_FLAGS], [...reader.WRITER_FLAGS]);
  const source = fs.readFileSync(path.join(ROOT, "packages/optics-operational-store/src/open.cjs"), "utf8");
  assert.equal(source.includes("optics-record-reader"), false);
  assert.equal(source.includes("vantio-cli"), false);
  assert.equal(source.includes("node:sqlite"), false);
  assert.equal(source.includes("better-sqlite"), false);
});

test("frozen product versions and the closed architecture gate stay in place", () => {
  assert.equal(readJson("packages/vantio-cli/package.json").version, "0.3.24");
  assert.equal(readJson("packages/vantio-agent-sdk/package.json").version, "0.2.4");
  const python = fs.readFileSync(path.join(ROOT, "packages/vantio-agent-sdk-py/pyproject.toml"), "utf8");
  assert.match(python, /^version = "3.1.0"$/m);
  const gates = fs.readFileSync(path.join(ROOT, "docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md"), "utf8");
  assert.match(gates, /\| 8 \| Implementation Force \|.*\| \*\*Closed\. Not started\*\* \|/);
  const decision = fs.readFileSync(
    path.join(ROOT, "docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md"),
    "utf8",
  );
  assert.match(decision, /9\. Node SQLite binding\. Not selected\./);
  assert.equal(readJson("packages/optics-operational-store/package.json").private, true);
  assert.equal(readJson("packages/optics-operational-store/package.json").version, "0.0.0-unstable-pre-1.0");
  assert.equal(store.SCHEMA_STATUS, "unstable-pre-1.0");
  assert.equal(store.OPERATIONAL_SCHEMA_VERSION, 1);
  assert.equal(store.PRIVACY_GENERATION, 1);
});

test("the store manifest hashes match the packet and the implementation", () => {
  const manifest = readJson("docs/planning/optics-o7-store/STORE-MANIFEST.json");
  assert.equal(
    manifest.producer_classification,
    "OPTICS_O7_STORE_BLOCKED_NODE_BINDING_UNSELECTED_REVISION_READY_FOR_COUNCIL",
  );
  assert.equal(manifest.evidence_tier, "UNSET");
  assert.equal(manifest.default_write_path, false);
  assert.equal(manifest.node_binding, "UNSELECTED");
  assert.equal(manifest.founder_decision_9, "UNRESOLVED");
  assert.equal(manifest.catalog_o7_status_left_untouched, "NOT_AUTHORIZED");
  for (const [rel, expected] of Object.entries(manifest.files_sha256)) {
    const bytes = fs.readFileSync(path.join(ROOT, rel));
    const actual = crypto.createHash("sha256").update(bytes).digest("hex");
    assert.equal(actual, expected, rel);
  }
});
