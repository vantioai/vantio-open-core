import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { assertShape, recheck } from "./seal-identity-recheck.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("the 6d3ce580 digest is recorded and not rebuilt from this tree", async () => {
  const body = await recheck(root);
  assert.deepEqual(assertShape(body), []);
  assert.equal(body.digest_role_on_main, "COMPARISON_SEAL");
  assert.equal(body.constants_moved, false);
  const saved = JSON.parse(readFileSync(join(root, "docs/planning/seal-identity-recheck/RESULT.json"), "utf8"));
  assert.deepEqual(saved, body);
  const prose = readFileSync(join(root, "docs/planning/seal-identity-recheck/00-RECHECK.md"), "utf8");
  assert.match(prose, /\*\*Verified\*\*/);
  assert.match(prose, /\*\*Lab-only\*\*/);
  assert.doesNotMatch(prose, /reproducible build/);
  assert.doesNotMatch(prose, /formally reproducible/);
});
