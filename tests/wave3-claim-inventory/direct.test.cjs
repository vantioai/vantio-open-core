"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const ROOT = path.resolve(__dirname, "../..");
const WAVE3 = "docs/programs/production-readiness/wave3";
const REMOVED = [
  `${WAVE3}/CLAIM-LEDGER.json`,
  `${WAVE3}/PUBLIC-SURFACE-INVENTORY.json`,
];
const REMOVED_SCHEMAS = [
  "vantio.program.production-readiness.wave3.public-surface-inventory/v1",
  "vantio.program.production-readiness.wave3.claim-ledger/v1",
];

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

function jsonFilesUnder(relDir) {
  const abs = path.join(ROOT, relDir);
  const found = [];
  const visit = (dir, prefix) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name;
      const child = path.join(dir, entry.name);
      if (entry.isDirectory()) visit(child, rel);
      else if (entry.isFile() && entry.name.endsWith(".json")) found.push(`${relDir}/${rel}`);
    }
  };
  visit(abs, "");
  return found;
}

test("claim and public-surface inventory JSON are absent from the public wave3 tree", () => {
  for (const rel of REMOVED) {
    assert.equal(fs.existsSync(path.join(ROOT, rel)), false, rel);
  }
  const names = jsonFilesUnder(WAVE3).map((rel) => path.basename(rel));
  assert.equal(names.includes("CLAIM-LEDGER.json"), false);
  assert.equal(names.includes("PUBLIC-SURFACE-INVENTORY.json"), false);
  for (const rel of jsonFilesUnder(WAVE3)) {
    const text = readText(rel);
    for (const schema of REMOVED_SCHEMAS) {
      assert.equal(text.includes(schema), false, rel);
    }
    assert.equal(text.includes('"track": "W3-T14"'), false, rel);
    assert.equal(text.includes('"track": "W3-T15"'), false, rel);
  }
});

test("frozen package versions stay closed", () => {
  assert.equal(readJson("packages/vantio-cli/package.json").version, "0.3.24");
  assert.equal(readJson("packages/vantio-agent-sdk/package.json").version, "0.2.4");
  assert.match(readText("packages/vantio-agent-sdk-py/pyproject.toml"), /^version = "3\.1\.0"$/m);
  assert.match(readText("docs/products/optics/CHANGELOG-GUIDE.md"), /It is unpublished\./);
  assert.match(readText("packages/vantio-gate-mcp/server.json"), /https:\/\/api\.vantio\.ai/);
  assert.equal(readJson(`${WAVE3}/STATUS.json`).clean_host_internal_proof, false);
  assert.equal(readJson(`${WAVE3}/STATUS.json`).proved_external, false);
});

test("the reading guide names the freeze and does not treat it as a ship", () => {
  const guide = [
    "docs/internal/wave3/claim-inventory/README.md",
    "docs/internal/wave3/claim-inventory/00-BOUNDARY.md",
    "docs/internal/wave3/claim-inventory/01-METHOD.md",
    "docs/internal/wave3/claim-inventory/02-DISPOSITIONS.md",
    "docs/internal/wave3/claim-inventory/03-DRIFT.md",
    "docs/internal/wave3/claim-inventory/04-FREEZE.md",
  ].map(readText).join("\n");
  assert.match(guide, /W3_PUBLIC_CLAIM_CONTENT_INVENTORY_READY_FOR_COUNCIL/);
  assert.match(guide, /FROZEN_INVENTORY/);
  assert.match(guide, /INTERNAL_RESTRICTED/);
  assert.match(guide, /UNREVIEWED/);
  for (let index = 1; index <= 14; index += 1) {
    assert.match(guide, new RegExp(`D-${String(index).padStart(2, "0")}`));
  }
  assert.match(guide, /not permission to rewrite, publish, or announce/);
  assert.equal(guide.includes("docs/programs/production-readiness/wave3/CLAIM-LEDGER.json"), false);
  assert.equal(guide.includes("docs/programs/production-readiness/wave3/PUBLIC-SURFACE-INVENTORY.json"), false);
});
