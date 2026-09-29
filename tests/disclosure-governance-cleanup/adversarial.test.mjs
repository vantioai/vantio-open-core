import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  COLLISION_TEST_INVENTORY_PATH,
  collectLegacyHits,
  collisionTestInventoryProblems,
  diffLegacyInventory,
} from "../../docs/scripts/docs-release-lib.mjs";
import {
  disclosureRecordProblems,
  fixtureDisclosureRecord,
  fixturePurgePacket,
  purgePacketProblems,
} from "../../docs/scripts/disclosure-review.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");

function readJson(rel) {
  return JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
}

function reviewedInput() {
  const manifest = readJson("docs/governance/MANIFEST.json");
  const legacy = structuredClone(readJson("docs/governance/LEGACY-STALE-NAMES.json"));
  const liveHits = [
    { path: COLLISION_TEST_INVENTORY_PATH, count: 2 },
  ];
  return { manifest, legacy, liveHits };
}

test("hiding the collision test path fails the review", () => {
  const input = reviewedInput();
  input.manifest = structuredClone(input.manifest);
  input.manifest.legacy_scan.exclude_prefixes = [
    ...input.manifest.legacy_scan.exclude_prefixes,
    "tests/shared-health-vocabulary/",
  ];
  input.liveHits = [];
  const problems = collisionTestInventoryProblems(input);
  assert.match(problems, /hidden by exclude prefix/);
  assert.match(problems, /does not see the collision test/);
});

test("an intentional leftover is not a silent exception for the collision test", () => {
  const input = reviewedInput();
  input.legacy.intentional_leftovers.hits.push({
    path: COLLISION_TEST_INVENTORY_PATH,
    count: 2,
  });
  const review = input.legacy.reviewed_updates.find((item) => item.path === COLLISION_TEST_INVENTORY_PATH);
  review.disposition = "EXCEPTED";
  const problems = collisionTestInventoryProblems(input);
  assert.match(problems, /intentional leftover/);
  assert.match(problems, /not FROZEN_DEBT/);
});

test("a different new retired-name file is still new debt", () => {
  const stale = readJson("docs/governance/STALE-NAMES.json");
  const wordPatterns = stale.patterns.filter((pattern) => pattern.regex.includes(" "));
  assert.ok(wordPatterns.length >= 2);
  const dir = mkdtempSync(join(tmpdir(), "vantio-disclosure-"));
  try {
    mkdirSync(join(dir, "notes"));
    writeFileSync(join(dir, "notes/extra.md"), `${wordPatterns.map((pattern) => pattern.regex).join("\n")}\n`);
    const seen = collectLegacyHits(dir, {
      extensions: [".md"],
      exclude_prefixes: [],
    }, stale.patterns);
    assert.deepEqual(seen, [{ path: "notes/extra.md", count: wordPatterns.length }]);
    const hidden = collectLegacyHits(dir, {
      extensions: [".md"],
      exclude_prefixes: ["notes/"],
    }, stale.patterns);
    assert.deepEqual(hidden, []);
    const problems = diffLegacyInventory(seen, [{ path: COLLISION_TEST_INVENTORY_PATH, count: 2 }], []);
    assert.match(problems.join("\n"), /notes\/extra.md/);
    assert.match(problems.join("\n"), /no longer present/);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("a merged pull request or a sent purge packet fails the disclosure review", () => {
  const record = fixtureDisclosureRecord();
  const packet = fixturePurgePacket();
  const merged = structuredClone(record);
  merged.public_pull_request.merged = true;
  merged.public_pull_request.merged_at = "2026-09-27T12:00:00Z";
  merged.merge_to_public_main = "MERGED";
  merged.support_purge.contacted_github_support = true;
  merged.support_purge.status = "SENT";
  const problems = disclosureRecordProblems(merged);
  assert.ok(problems.some((item) => item.includes("not unmerged")));
  assert.ok(problems.some((item) => item.includes("public main merge")));
  assert.ok(problems.some((item) => item.includes("contacted")));
  assert.ok(problems.some((item) => item.includes("not prepared")));

  const sent = packet.replace("PACKET_STATUS: PREPARED_NOT_SENT", "PACKET_STATUS: SENT");
  assert.match(purgePacketProblems(sent).join("\n"), /marked sent/);
  const contacted = packet.replace("GITHUB_SUPPORT_CONTACTED: false", "GITHUB_SUPPORT_CONTACTED: true");
  assert.match(purgePacketProblems(contacted).join("\n"), /support was contacted/);
});

test("changing one reviewed hash fails the disclosure record", () => {
  const record = structuredClone(fixtureDisclosureRecord());
  record.reviewed_hashes.files[0].public_tip_sha256 = "0".repeat(64);
  const problems = disclosureRecordProblems(record);
  assert.ok(problems.some((item) => item.includes("public_tip_sha256 drifted")));
});
