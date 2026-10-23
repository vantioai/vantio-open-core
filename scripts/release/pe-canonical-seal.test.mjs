import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { laneSeal, publicPin, readCanonicalSeal, readSealHistory } from "./pe_canonical_seal.mjs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

test("the node reader matches the python helper and keeps the two roles apart", () => {
  const seal = readCanonicalSeal(root);
  const history = readSealHistory(root);
  assert.equal(publicPin(root), seal.public_pin.archive_sha256);
  assert.equal(laneSeal(root), seal.lane_seal.sha256);
  assert.notEqual(seal.public_pin.archive_sha256, seal.lane_seal.sha256);
  assert.equal(seal.signer_kid, null);
  assert.equal(seal.updated, "2026-10-23");
  assert.match(seal.lane_seal.note, /one seal/);
  assert.notEqual(history.previous_working_seal, seal.lane_seal.sha256);
  const retired = (history.retired_lane_seals ?? []).map((entry) => entry.sha256);
  assert.ok(retired.length > 0);
  for (const digest of retired) {
    assert.match(digest, /^[0-9a-f]{64}$/);
    assert.notEqual(digest, seal.lane_seal.sha256);
    assert.notEqual(digest, seal.public_pin.archive_sha256);
  }
  const py = spawnSync(
    "python3",
    [
      "-c",
      "import sys; sys.path.insert(0, 'scripts/release'); from pe_canonical_seal import lane_seal, public_pin, previous_working_seal; print(public_pin()); print(lane_seal()); print(previous_working_seal())",
    ],
    { cwd: root, encoding: "utf8" },
  );
  assert.equal(py.status, 0, py.stderr);
  const [pin, lane, previous] = py.stdout.trim().split("\n");
  assert.equal(pin, seal.public_pin.archive_sha256);
  assert.equal(lane, seal.lane_seal.sha256);
  assert.equal(previous, history.previous_working_seal);
});
