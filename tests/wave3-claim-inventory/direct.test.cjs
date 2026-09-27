"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { freezeProblems } = require("../../internal/wave3-claim-inventory/freeze.cjs");

const ROOT = path.resolve(__dirname, "../..");
const LEDGER_PATH = "docs/programs/production-readiness/wave3/CLAIM-LEDGER.json";
const INVENTORY_PATH = "docs/programs/production-readiness/wave3/PUBLIC-SURFACE-INVENTORY.json";

function readText(rel) {
  return fs.readFileSync(path.join(ROOT, rel), "utf8");
}

function readJson(rel) {
  return JSON.parse(readText(rel));
}

const ledger = readJson(LEDGER_PATH);
const inventory = readJson(INVENTORY_PATH);

function walkDispositions(node, found) {
  if (Array.isArray(node)) {
    for (const item of node) walkDispositions(item, found);
    return;
  }
  if (!node || typeof node !== "object") return;
  for (const [key, value] of Object.entries(node)) {
    if (key === "disposition" || key === "disposition_default") found.push(value);
    else walkDispositions(value, found);
  }
}

test("the ledger is a frozen inventory and the freeze check is clean", () => {
  assert.equal(ledger.audience, "INTERNAL_RESTRICTED");
  assert.equal(ledger.track, "W3-T15");
  assert.equal(ledger.status, "FROZEN_INVENTORY");
  assert.equal(ledger.classification, "W3_PUBLIC_CLAIM_CONTENT_INVENTORY_READY_FOR_COUNCIL");
  assert.equal(ledger.freeze.status, "FROZEN_INVENTORY");
  assert.equal(ledger.freeze.kind, "INVENTORY_ONLY");
  assert.equal(ledger.freeze.frozen_on_et, "2026-09-27");
  assert.equal(ledger.freeze.timezone, "America/New_York");
  assert.equal(ledger.freeze.inventory_source_sha, "03995835c88a4ebcca2ee3b8c1ae7fa490d21653");
  assert.equal(ledger.source_inventory.refetched_public_http, false);
  assert.equal(ledger.t14_dispositions_mutated, false);
  assert.equal(ledger.public_surfaces_mutated, false);
  assert.equal(ledger.frozen_packages_reopened, false);
  assert.deepEqual(freezeProblems(ledger), []);
});

test("every claim is well-formed and none of the dispositions execute", () => {
  assert.ok(ledger.claims.length >= 60);
  const ids = ledger.claims.map((claim) => claim.claim_id);
  assert.deepEqual(ids, [...ids].sort());
  for (const claim of ledger.claims) {
    assert.equal(claim.executes_now, false);
    assert.ok(ledger.enums.evidence_status.includes(claim.evidence_status));
    assert.ok(ledger.enums.recommended_disposition.includes(claim.recommended_disposition));
    assert.ok(ledger.enums.claim_class.includes(claim.claim_class));
    assert.ok(claim.surfaces.length > 0);
    assert.ok(claim.evidence.length > 0);
    assert.equal(Array.isArray(claim.drift_ids), true);
  }
  assert.equal(
    ledger.claims.some((claim) => claim.recommended_disposition === "RETIRE"),
    false,
  );
});

test("drift D-01 through D-14 and the unpromoted gaps are covered", () => {
  for (let index = 1; index <= 14; index += 1) {
    const id = `D-${String(index).padStart(2, "0")}`;
    assert.equal(inventory.drift.some((item) => item.id === id), true);
    assert.equal(
      ledger.claims.some((claim) => claim.drift_ids.includes(id)),
      true,
      id,
    );
  }
  assert.equal(ledger.gaps_not_promoted.length, inventory.gaps.length);
  for (const gap of inventory.gaps) {
    const row = ledger.gaps_not_promoted.find((item) => item.inventory_id === gap.id);
    assert.ok(row, gap.id);
    assert.equal(row.promoted_to_claim, false);
    assert.equal(row.evidence_status, "UNKNOWN");
    assert.equal(row.executes_now, false);
  }
});

test("every Track 14 primary surface is pointed at by a claim", () => {
  for (const route of inventory.website.primary_routes) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "website.primary_route" && surface.url === route.url),
      ),
      true,
      route.url,
    );
  }
  for (const post of inventory.website.update_posts) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "website.update_post" && surface.url === post.url),
      ),
      true,
      post.url,
    );
  }
  for (const pkg of inventory.npm.packages) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "npm.package" && surface.name === pkg.name),
      ),
      true,
      pkg.name,
    );
  }
  for (const version of ["1.0.0", "2.0.0", "3.0.0", "3.0.14", "3.1.0"]) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "pypi.version" && surface.version === version),
      ),
      true,
      version,
    );
  }
  for (const id of ["linkedin-company", "linkedin-founder", "x"]) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "other_surface" && surface.id === id),
      ),
      true,
      id,
    );
  }
  for (const repo of inventory.github.repositories) {
    assert.equal(
      ledger.claims.some((claim) =>
        claim.surfaces.some((surface) => surface.kind === "github.repository" && surface.name === repo.name),
      ),
      true,
      repo.name,
    );
  }
});

test("Track 14 dispositions stay unreviewed and frozen versions stay closed", () => {
  assert.equal(inventory.disposition_default, "UNREVIEWED");
  assert.equal(inventory.classification, "W3_PUBLIC_ESTATE_INVENTORY_READY_FOR_COUNCIL");
  const dispositions = [];
  walkDispositions(inventory, dispositions);
  assert.ok(dispositions.length > 0);
  for (const value of dispositions) assert.equal(value, "UNREVIEWED");
  assert.equal(readJson("packages/vantio-cli/package.json").version, "0.3.24");
  assert.equal(readJson("packages/vantio-agent-sdk/package.json").version, "0.2.4");
  assert.match(readText("packages/vantio-agent-sdk-py/pyproject.toml"), /^version = "3\.1\.0"$/m);
  assert.match(readText("docs/products/optics/CHANGELOG-GUIDE.md"), /It is unpublished\./);
  assert.match(readText("packages/vantio-gate-mcp/server.json"), /https:\/\/api\.vantio\.ai/);
  assert.equal(readJson("docs/programs/production-readiness/wave3/STATUS.json").clean_host_internal_proof, false);
  assert.equal(readJson("docs/programs/production-readiness/wave3/STATUS.json").proved_external, false);
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
});

test("a seal commit records the introducing claim rows without changing them", () => {
  const sha = ledger.freeze.content_commit_sha;
  if (sha === null) {
    assert.match(ledger.freeze.tip_sha_note, /null until the seal commit/);
    return;
  }
  assert.match(sha, /^[0-9a-f]{40}$/);
  const shown = execFileSync("git", ["show", `${sha}:${LEDGER_PATH}`], {
    cwd: ROOT,
    encoding: "utf8",
  });
  const introduced = JSON.parse(shown);
  assert.equal(introduced.status, "FROZEN_INVENTORY");
  assert.equal(introduced.freeze.content_commit_sha, null);
  assert.equal(introduced.freeze.public_ship_authorization, false);
  assert.deepEqual(introduced.claims, ledger.claims);
  assert.deepEqual(introduced.gaps_not_promoted, ledger.gaps_not_promoted);
});
