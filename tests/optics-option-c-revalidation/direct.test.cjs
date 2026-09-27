"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const PACKET = "docs/planning/optics-option-c-revalidation";
const PLAN = "docs/planning/optics-production";

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function sha256File(rel) {
  return sha256(fs.readFileSync(path.join(ROOT, rel)));
}

const manifest = readJson(`${PACKET}/REVALIDATION-MANIFEST.json`);
const planManifest = readJson(`${PLAN}/PRODUCTION-MANIFEST.json`);
const packages = readJson(`${PLAN}/PACKAGES.json`);
const decisionPack = readText("docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md");
const a2 = readText("docs/architecture/optics-foundation/03-OPERATIONAL-STORE-AND-PORTABLE-PROOF.md");
const gates = readText("docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md");
const architectureManifest = readJson("docs/architecture/optics-foundation/ARCHITECTURE-MANIFEST.json");

function refusalCodes(claim) {
  const codes = [];
  if (claim.producer_classification !== "OPTICS_OPTION_C_REVALIDATED_READY_FOR_COUNCIL") {
    codes.push("CLASSIFICATION");
  }
  if (claim.amendment !== "NOT_REQUIRED") codes.push("AMENDMENT");
  if (claim.decision.engine_source !== "CITED_FROM_RATIFIED_TEXT") codes.push("ENGINE_INFERRED");
  if (!decisionPack.includes(claim.decision.engine_sentence)) codes.push("ENGINE_CITATION");
  if (!a2.includes(claim.decision.a2_sentence)) codes.push("A2_CITATION");
  if (claim.decision.store_option_c !== "FOUNDER_RATIFIED_ARCHITECTURE_ONLY") codes.push("STORE_OPTION_C");
  if (claim.decision.node_binding !== "UNSELECTED") codes.push("NODE_BINDING");
  if (claim.decision.founder_decision_9 !== "UNRESOLVED") codes.push("DECISION_9");
  if (claim.decision.gate_8 !== "CLOSED") codes.push("GATE_8");
  if (claim.o7.status !== "NOT_AUTHORIZED") codes.push("O7_STATUS");
  if (claim.o7.store_write !== "NOT_ACTIVATED") codes.push("O7_WRITE");
  if (claim.hard_stops.database_created !== false) codes.push("DATABASE");
  if (claim.hard_stops.sqlite_file_present !== false) codes.push("SQLITE_FILE");
  if (claim.hard_stops.sqlite_dependency_present !== false) codes.push("SQLITE_DEPENDENCY");
  if (claim.hard_stops.node_binding_selected !== false) codes.push("BINDING_SELECTED");
  if (claim.hard_stops.cli_reopened !== false) codes.push("CLI_REOPENED");
  if (claim.hard_stops.cli_version !== "0.3.24") codes.push("CLI_VERSION");
  if (claim.hard_stops.gate_8_opened_in_architecture_file !== false) codes.push("GATE_8_FILE");
  if (claim.council_status !== "PENDING_INDEPENDENT_COUNCIL") codes.push("THIS_COUNCIL");
  if (claim.merged_plan.in_file_council_status !== "PENDING_COUNCIL") codes.push("PLAN_COUNCIL");
  if (claim.producer_identity.self_certified_council_pass !== false) codes.push("SELF_PASS");
  return codes;
}

test("the producer claim matches the ratified text and the closed store", () => {
  assert.deepEqual(refusalCodes(manifest), []);
  assert.equal(architectureManifest.store_option_c, "FOUNDER_RATIFIED_ARCHITECTURE_ONLY");
  assert.match(decisionPack, /9\. Node SQLite binding\. Not selected\./);
  assert.match(gates, /\| 8 \| Implementation Force \|.*\| \*\*Closed\. Not started\*\* \|/);
  assert.equal(readJson("packages/vantio-cli/package.json").version, "0.3.24");
});

test("plan input hashes, plan file hashes, and the dependency graph match this base", () => {
  for (const [rel, expected] of Object.entries(planManifest.input_sha256)) {
    assert.equal(sha256File(rel), expected, rel);
  }
  for (const [name, expected] of Object.entries(planManifest.files_sha256)) {
    assert.equal(sha256File(`${PLAN}/${name}`), expected, name);
  }
  const edges = JSON.stringify(packages.dependency_graph.edges);
  assert.equal(sha256(edges), planManifest.dependency_graph_sha256);
  assert.equal(sha256(edges), manifest.checks.dependency_graph_sha256);
});

test("the golden vector is the canonical line in A2 section 5.2", () => {
  const line = a2
    .split("\n")
    .find((row) => row.startsWith('{"completeness":"COMPLETE"'));
  assert.ok(line);
  const bytes = Buffer.from(line, "utf8");
  assert.equal(bytes.length, 428);
  assert.equal(sha256(bytes), "a12adfa5f7b59aa3c4c8c98a52d36a50dcf861c3f8aea9bee7ee2eac70fd263a");
  assert.equal(bytes.length, manifest.checks.golden_vector.byte_length);
  assert.equal(sha256(bytes), manifest.checks.golden_vector.sha256);
});

test("O7 stays unauthorized and its predecessors are unmet", () => {
  const byId = Object.fromEntries(packages.packages.map((row) => [row.id, row]));
  assert.equal(byId.O7.status, "NOT_AUTHORIZED");
  assert.equal(byId.O2.status, "CONSTRAINT_VERIFIED_NOT_AUTHORIZED");
  assert.equal(byId.O6.status, "NEEDS_FOUNDER_DECISION");
  assert.equal(byId.O12.status, "NOT_AUTHORIZED");
  assert.equal(byId.O1.status, "DESIGN_SKETCH_ONLY");
  assert.equal(byId.O11.status, "NOT_AUTHORIZED");
  const edges = packages.dependency_graph.edges.map((edge) => edge.join("->"));
  assert.ok(edges.includes("O2->O7"));
  assert.ok(edges.includes("O6->O7"));
  assert.ok(edges.includes("O12->O7"));
  assert.equal(manifest.o7.entry_steps.o2_contract_accepted, false);
  assert.equal(manifest.o7.entry_steps.founder_decision_9_then_o6, false);
  assert.equal(manifest.o7.entry_steps.o7_force_opened, false);
  assert.equal(packages.packages.every((row) => row.evidence_tier === "UNSET"), true);
});

test("the merged plan is an ancestor and its tree is unchanged", () => {
  const ancestor = execFileSync(
    "git",
    ["merge-base", "--is-ancestor", manifest.merged_plan.merge, manifest.revalidation_base],
    { cwd: ROOT, encoding: "utf8" },
  );
  assert.equal(ancestor, "");
  const architectureDiff = execFileSync(
    "git",
    [
      "diff",
      "--name-only",
      "587f3b94d47ea958f91d3a99125cd55931d995f1",
      manifest.revalidation_base,
      "--",
      "docs/architecture/optics-foundation",
    ],
    { cwd: ROOT, encoding: "utf8" },
  );
  assert.equal(architectureDiff, "");
  const planDiff = execFileSync(
    "git",
    ["diff", "--name-only", manifest.merged_plan.merge, manifest.revalidation_base, "--", PLAN],
    { cwd: ROOT, encoding: "utf8" },
  );
  assert.equal(planDiff, "");
  assert.match(
    readText(`${PLAN}/10-INDEPENDENT-COUNCIL-REPORT.md`),
    /Status: `PENDING_COUNCIL`/,
  );
});

test("packet hashes cover every file except the manifest", () => {
  const listed = manifest.files_sha256;
  const expected = new Set([
    `${PACKET}/00-REVALIDATION.md`,
    `${PACKET}/10-INDEPENDENT-COUNCIL.md`,
    "tests/optics-option-c-revalidation/direct.test.cjs",
    "tests/optics-option-c-revalidation/adversarial.test.cjs",
  ]);
  assert.deepEqual(new Set(Object.keys(listed)), expected);
  for (const rel of expected) {
    assert.equal(sha256File(rel), listed[rel], rel);
  }
});
