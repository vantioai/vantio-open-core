"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const {
  DISPOSITIONS,
  SHIP_FLAGS,
  dispositionExecutesNow,
  freezeProblems,
  publicShipAuthorized,
} = require("../../internal/wave3-claim-inventory/freeze.cjs");

const ROOT = path.resolve(__dirname, "../..");
const ledger = JSON.parse(
  fs.readFileSync(path.join(ROOT, "docs/programs/production-readiness/wave3/CLAIM-LEDGER.json"), "utf8"),
);

const AUTHORIZING_STATUSES = ["PUBLIC_SHIP_AUTHORIZED"];

test("FROZEN_INVENTORY is not a public-ship status", () => {
  assert.equal(publicShipAuthorized(ledger), false);
  assert.equal(AUTHORIZING_STATUSES.includes(ledger.status), false);
  assert.equal(AUTHORIZING_STATUSES.includes("FROZEN_INVENTORY"), false);
  for (const disposition of DISPOSITIONS) {
    assert.equal(dispositionExecutesNow(ledger, disposition), false);
  }
  for (const claim of ledger.claims) {
    assert.equal(dispositionExecutesNow(ledger, claim.recommended_disposition), false);
  }
});

test("flipping ship flags does not authorize a ship and does fail the freeze check", () => {
  const mutated = structuredClone(ledger);
  for (const flag of SHIP_FLAGS) mutated.freeze[flag] = true;
  mutated.public_surfaces_mutated = true;
  mutated.frozen_packages_reopened = true;
  mutated.claims[0].executes_now = true;
  mutated.claims[0].evidence_status = "SUCCESS";
  assert.equal(publicShipAuthorized(mutated), false);
  assert.equal(dispositionExecutesNow(mutated, "REWRITE"), false);
  assert.equal(dispositionExecutesNow(mutated, "RETIRE"), false);
  const problems = freezeProblems(mutated);
  for (const flag of SHIP_FLAGS) {
    assert.ok(problems.some((problem) => problem.includes(flag)), flag);
  }
  assert.ok(problems.some((problem) => problem.includes("executes_now")));
  assert.ok(problems.some((problem) => problem.includes("evidence_status")));
  assert.ok(problems.some((problem) => problem.includes("public_surfaces_mutated")));
  assert.ok(problems.some((problem) => problem.includes("frozen_packages_reopened")));
});

test("the freeze module has no ship branch", () => {
  const source = fs.readFileSync(path.join(ROOT, "internal/wave3-claim-inventory/freeze.cjs"), "utf8");
  assert.match(source, /function publicShipAuthorized\(_ledger\) \{\n  return false;\n\}/);
  assert.match(source, /function dispositionExecutesNow\(_ledger, _disposition\) \{\n  return false;\n\}/);
  assert.doesNotMatch(source, /require\("node:https"\)/);
  assert.doesNotMatch(source, /require\("node:http"\)/);
  assert.doesNotMatch(source, /child_process/);
  assert.doesNotMatch(source, /npm publish/);
  assert.doesNotMatch(source, /FROZEN_INVENTORY[\s\S]{0,80}return true/);
});
