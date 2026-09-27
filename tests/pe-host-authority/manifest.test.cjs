"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "../..");
const manifest = require("../../docs/internal/pe-host-authority/HOST-AUTHORITY-MANIFEST.json");
const { SURFACES } = require("../../packages/pe-host-authority/src/catalog.cjs");
const { CASES } = require("../../packages/pe-host-authority/src/cases.cjs");

test("manifest hashes match the proof files", () => {
  assert.equal(manifest.producer_classification, "PE_HOST_AUTHORITY_READY_FOR_COUNCIL");
  assert.equal(manifest.council_verdict, "PENDING_INDEPENDENT_COUNCIL");
  assert.equal(manifest.kernel_loaded_this_force, false);
  assert.equal(manifest.loader_mutated_this_force, false);
  assert.equal(manifest.universal_linux_control, false);
  assert.equal(manifest.loader_this_force_read, "NOT_READ");
  assert.equal(manifest.contract_cases, CASES.length);
  for (const [file, hash] of Object.entries(manifest.files)) {
    const actual = crypto.createHash("sha256").update(fs.readFileSync(path.join(root, file))).digest("hex");
    assert.equal(actual, hash, file);
  }
});

test("coverage notes name every surface and stay internal", () => {
  const coverage = fs.readFileSync(path.join(root, "docs/internal/pe-host-authority/01-MECHANISM-COVERAGE.md"), "utf8");
  const boundary = fs.readFileSync(path.join(root, "docs/internal/pe-host-authority/00-BOUNDARY.md"), "utf8");
  for (const surface of SURFACES) {
    assert.equal(coverage.toLowerCase().includes(surface.id.replaceAll("_", " ")) || coverage.includes(surface.id), true, surface.id);
  }
  assert.match(boundary, /PE_HOST_AUTHORITY_READY_FOR_COUNCIL/);
  assert.match(boundary, /PENDING_INDEPENDENT_COUNCIL|separate council/);
  const tree = [
    "docs/internal/pe-host-authority",
    "packages/pe-host-authority",
    "tests/pe-host-authority",
  ];
  for (const dir of tree) {
    const names = fs.readdirSync(path.join(root, dir), { recursive: true }).map(String);
    for (const name of names) {
      assert.equal(/CUSTOMER-MANUAL|PRIVATE-MANUAL/.test(name), false, name);
    }
  }
});
