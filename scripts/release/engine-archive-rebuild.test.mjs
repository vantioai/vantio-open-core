import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { attempt, classify, workingSeal } from "./engine-archive-rebuild.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const seal = "6".padEnd(64, "a");

test("a missing source is not a match or a mismatch", () => {
  const body = classify(seal, { source_present: false });
  assert.equal(body.comparison, "NOT_PERFORMED");
  assert.equal(body.match, null);
  assert.equal(body.rebuilt_sha256, null);
  assert.equal(body.reason, "source_unavailable");
  assert.equal(body.label, "Lab-only");
  assert.equal(body.formal_reproducibility, "NOT_CLAIMED");
});

test("a rebuilt digest is a match only when it equals the working seal", () => {
  const same = classify(seal, { source_present: true, build_completed: true, rebuilt_sha256: seal });
  assert.equal(same.comparison, "MATCH");
  assert.equal(same.match, true);
  const other = classify(seal, { source_present: true, build_completed: true, rebuilt_sha256: "b".repeat(64) });
  assert.equal(other.comparison, "MISMATCH");
  assert.equal(other.match, false);
});

test("this checkout records the live attempt", () => {
  const body = attempt(root);
  assert.equal(body.working_seal, workingSeal(root));
  assert.equal(body.working_seal.startsWith("97f15bbb"), true);
  assert.equal(body.label, "Lab-only");
  assert.equal(body.formal_reproducibility, "NOT_CLAIMED");
  const saved = JSON.parse(readFileSync(join(root, "docs/planning/engine-archive-rebuild/RESULT.json"), "utf8"));
  for (const key of ["comparison", "reason", "match", "rebuilt_sha256", "working_seal", "label", "source_dir_found", "formal_reproducibility"]) {
    assert.equal(saved[key], body[key], key);
  }
  const prose = readFileSync(join(root, "docs/planning/engine-archive-rebuild/00-ATTEMPT.md"), "utf8");
  assert.match(prose, /\*\*Lab-only\*\*/);
  assert.doesNotMatch(prose, /reproducible build/);
  assert.doesNotMatch(prose, /formally reproducible/);
});
