"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const PACKET = "docs/planning/optics-option-c-revalidation";

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

function sha256(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

const manifest = readJson(`${PACKET}/REVALIDATION-MANIFEST.json`);
const a2 = readText("docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md");
const decisionPack = readText("docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md");

const DEPENDENCY_NAMES = new Set(["sqlite3", "better-sqlite3", "better-sqlite", "node:sqlite"]);
const IMPORT_RE =
  /^\s*(?:import\s+sqlite3\b|from\s+sqlite3\b|require\(\s*["'](?:sqlite3|better-sqlite3|better-sqlite|node:sqlite)["']|import\s+.*\s+from\s+["'](?:sqlite3|better-sqlite3|better-sqlite|node:sqlite)["'])/u;

function walk(dir, out) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name === ".git") continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

function refusalCodes(claim) {
  const codes = [];
  if (claim.producer_classification !== "OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL") {
    codes.push("CLASSIFICATION");
  }
  if (claim.amendment !== "NOT_REQUIRED") codes.push("AMENDMENT");
  if (claim.decision.engine_source !== "CITED_FROM_RATIFIED_TEXT") codes.push("ENGINE_INFERRED");
  if (!decisionPack.includes(claim.decision.engine_sentence)) codes.push("ENGINE_CITATION");
  if (!a2.includes(claim.decision.a2_sentence)) codes.push("A2_CITATION");
  if (claim.decision.node_binding !== "UNSELECTED") codes.push("NODE_BINDING");
  if (claim.o7.status !== "NOT_AUTHORIZED") codes.push("O7_STATUS");
  if (claim.o7.store_write !== "NOT_ACTIVATED") codes.push("O7_WRITE");
  if (claim.hard_stops.database_created !== false) codes.push("DATABASE");
  if (claim.hard_stops.sqlite_file_present !== false) codes.push("SQLITE_FILE");
  if (claim.hard_stops.cli_version !== "0.3.24") codes.push("CLI_VERSION");
  if (claim.decision.gate_8 !== "CLOSED") codes.push("GATE_8");
  if (claim.council_status !== "PENDING_INDEPENDENT_COUNCIL") codes.push("THIS_COUNCIL");
  if (claim.merged_plan.in_file_council_status !== "PENDING_COUNCIL") codes.push("PLAN_COUNCIL");
  return codes;
}

test("a mutated claim is refused field by field", () => {
  const cases = [
    ["producer_classification", "OPTICS_OPTION_C_AMENDMENT_REQUIRED_READY_FOR_COUNCIL", "CLASSIFICATION"],
    ["amendment", "REQUIRED", "AMENDMENT"],
    ["council_status", "PASSED", "THIS_COUNCIL"],
  ];
  for (const [field, value, code] of cases) {
    const claim = structuredClone(manifest);
    claim[field] = value;
    assert.ok(refusalCodes(claim).includes(code), code);
  }

  const nested = [
    [["decision", "engine_source"], "INFERRED", "ENGINE_INFERRED"],
    [["decision", "engine_sentence"], "Embedded DuckDB is the operational store.", "ENGINE_CITATION"],
    [["decision", "a2_sentence"], "Option B is the operational store.", "A2_CITATION"],
    [["decision", "node_binding"], "better-sqlite3", "NODE_BINDING"],
    [["decision", "gate_8"], "OPEN", "GATE_8"],
    [["o7", "status"], "AUTHORIZED", "O7_STATUS"],
    [["o7", "store_write"], "ACTIVATED", "O7_WRITE"],
    [["hard_stops", "database_created"], true, "DATABASE"],
    [["hard_stops", "sqlite_file_present"], true, "SQLITE_FILE"],
    [["hard_stops", "cli_version"], "0.3.25", "CLI_VERSION"],
    [["merged_plan", "in_file_council_status"], "PASSED", "PLAN_COUNCIL"],
  ];
  for (const [pathParts, value, code] of nested) {
    const claim = structuredClone(manifest);
    let cursor = claim;
    for (const part of pathParts.slice(0, -1)) cursor = cursor[part];
    cursor[pathParts[pathParts.length - 1]] = value;
    assert.ok(refusalCodes(claim).includes(code), code);
  }
});

test("one inserted space breaks the golden vector", () => {
  const line = a2
    .split("\n")
    .find((row) => row.startsWith('{"completeness":"COMPLETE"'));
  const broken = line.replace(":", ": ");
  assert.equal(sha256(broken), "2196636fef240005e8c489e097baa91618ea9ff2226be5c8bcb608f016dba2f9");
  assert.notEqual(sha256(broken), manifest.checks.golden_vector.sha256);
});

test("the working tree has no sqlite file, dependency, or import", () => {
  const files = walk(ROOT, []);
  const sqliteNames = files.filter((full) => full.endsWith(".sqlite") || full.endsWith(".sqlite3"));
  assert.deepEqual(sqliteNames, []);

  const manifests = files.filter((full) => {
    const base = path.basename(full);
    return base === "package.json" || base === "pyproject.toml";
  });
  for (const full of manifests) {
    const text = fs.readFileSync(full, "utf8");
    if (path.basename(full) === "package.json") {
      const body = JSON.parse(text);
      for (const field of ["dependencies", "devDependencies", "optionalDependencies", "peerDependencies"]) {
        for (const name of Object.keys(body[field] || {})) {
          assert.equal(DEPENDENCY_NAMES.has(name), false, `${full} ${name}`);
        }
      }
    } else {
      assert.equal(/^\s*(?:sqlite3|better-sqlite3)\b/m.test(text), false, full);
    }
  }

  const sources = files.filter((full) => /\.(?:js|cjs|mjs|py|ts)$/.test(full));
  for (const full of sources) {
    const lines = fs.readFileSync(full, "utf8").split("\n");
    for (const line of lines) {
      assert.equal(IMPORT_RE.test(line), false, full);
    }
  }
});

test("this packet contains no schema script and names no Node binding", () => {
  const packetFiles = walk(path.join(ROOT, PACKET), []);
  for (const full of packetFiles) {
    assert.equal(full.endsWith(".sql"), false);
    assert.equal(full.endsWith(".sqlite"), false);
    const text = fs.readFileSync(full, "utf8");
    assert.equal(/CREATE TABLE/i.test(text), false, full);
    assert.equal(/selected binding/i.test(text), false, full);
  }
  assert.match(
    readText(`${PACKET}/00-REVALIDATION.md`),
    /The engine in this packet is the engine named in the ratified text\./,
  );
  assert.equal(manifest.decision.engine_source, "CITED_FROM_RATIFIED_TEXT");
  assert.equal(manifest.decision.node_binding, "UNSELECTED");
  assert.match(
    readText("docs/planning/shared-health-vocabulary/00-BOUNDARY.md"),
    /Optics store writes, and O7/,
  );
  const boundary = readText("packages/optics-record-reader/src/boundary.cjs");
  assert.match(boundary, /"sqlite"/);
  assert.match(readText(`${PACKET}/10-INDEPENDENT-COUNCIL.md`), /Status: `PENDING_INDEPENDENT_COUNCIL`/);
});
