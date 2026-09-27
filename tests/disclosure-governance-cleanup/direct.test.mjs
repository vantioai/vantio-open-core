import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  COLLISION_TEST_INVENTORY_PATH,
  checkRelease,
  collectLegacyHits,
  collisionTestInventoryProblems,
} from "../../docs/scripts/docs-release-lib.mjs";
import {
  disclosureRecordProblems,
  purgePacketProblems,
} from "../../docs/scripts/disclosure-review.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

test("documentation release checks pass with the collision test reviewed in place", () => {
  const result = checkRelease(ROOT);
  assert.equal(result.ok, true, JSON.stringify(result.failures, null, 2));
  const reviewed = result.checks.find((check) => check.id === "collision-test-inventory-reviewed");
  assert.equal(reviewed.ok, true, reviewed.detail);
});

test("collision test stays visible frozen debt at the live count", () => {
  const manifest = readJson("docs/governance/MANIFEST.json");
  const legacy = readJson("docs/governance/LEGACY-STALE-NAMES.json");
  const stale = readJson("docs/governance/STALE-NAMES.json");
  const liveHits = collectLegacyHits(ROOT, manifest.legacy_scan, stale.patterns);
  assert.equal(collisionTestInventoryProblems({ manifest, legacy, liveHits }), "");
  const review = legacy.reviewed_updates.find((item) => item.path === COLLISION_TEST_INVENTORY_PATH);
  assert.equal(review.disposition, "FROZEN_DEBT");
  assert.equal(review.reviewed_on, "2026-09-27");
  assert.equal(review.count, 2);
  const hit = legacy.hits.find((item) => item.path === COLLISION_TEST_INVENTORY_PATH);
  assert.equal(hit.count, 2);
  assert.equal(
    legacy.intentional_leftovers.hits.some((item) => item.path === COLLISION_TEST_INVENTORY_PATH),
    false,
  );
  const text = readFileSync(join(ROOT, COLLISION_TEST_INVENTORY_PATH), "utf8");
  assert.equal(text.includes("bpftool"), true);
  assert.equal(text.includes("kubectl apply"), true);
});

test("disclosure record and unsent purge packet agree", () => {
  const record = readJson("docs/internal/disclosure-governance-cleanup/DISCLOSURE-RECORD.json");
  const packet = readFileSync(
    join(ROOT, "docs/internal/disclosure-governance-cleanup/GITHUB-SUPPORT-PURGE-PACKET.md"),
    "utf8",
  );
  assert.deepEqual(disclosureRecordProblems(record), []);
  assert.deepEqual(purgePacketProblems(packet), []);
  assert.equal(existsSync(join(ROOT, "docs/customer/phantom-engine")), false);
  assert.equal(record.support_purge.contacted_github_support, false);
  assert.equal(record.public_pull_request.merged, false);
});
