"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");
const { buildObservationFragment, fragmentDigestMatches, SCHEMA_ID } = require("../../packages/optics-evidence-contract/src/fragment.cjs");

const record = {
  trace_id: "frag-1",
  calls: [
    {
      hostname: "api.openai.com",
      method: "POST",
      path: "/v1/chat/completions",
      status: 204,
      bytes: null,
      action: "OBSERVED",
      opticsStatus: "SUCCESS",
      applicationStatus: "SUCCESS",
    },
  ],
};

test("a fragment stays observational and keeps a missing byte count", () => {
  const built = buildObservationFragment(record, "cli", "0.3.25");
  assert.equal(built.ok, true);
  assert.equal(built.fragment.schema_id, SCHEMA_ID);
  assert.equal(built.fragment.enforcement_attached, false);
  assert.equal(built.fragment.claim_ceiling, "OBSERVATION_ONLY");
  assert.equal(built.fragment.live_enforcement, "NOT_APPLICABLE");
  assert.equal(built.fragment.calls[0].response_bytes, null);
  assert.equal(built.fragment.calls[0].action, "OBSERVED");
  assert.equal(fragmentDigestMatches(built.fragment), true);
});

test("an enforcement action is excluded", () => {
  const built = buildObservationFragment(
    { trace_id: "nope", calls: [{ hostname: "api.openai.com", action: "BLOCKED_HOST" }] },
    "cli",
    "0.3.25",
  );
  assert.equal(built.ok, false);
  assert.equal(built.reason, "ENFORCEMENT_ACTION_EXCLUDED");
  assert.equal(built.fragment, null);
});

test("the Python builder emits the same digest", () => {
  const nodeBuilt = buildObservationFragment(record, "cli", "0.3.25");
  const src = path.join(__dirname, "../../packages/optics-evidence-contract/src");
  const script = `
import json, sys
sys.path.insert(0, ${JSON.stringify(src)})
from fragment import build_observation_fragment
record = json.loads(sys.stdin.read())
built = build_observation_fragment(record, producer="cli", producer_version="0.3.25")
print(built["fragment"]["record_sha256"])
`;
  const result = spawnSync("python3", ["-c", script], {
    input: JSON.stringify(record),
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), nodeBuilt.fragment.record_sha256);
});
