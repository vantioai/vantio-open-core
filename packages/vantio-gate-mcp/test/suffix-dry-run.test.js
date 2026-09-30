import { test } from "node:test";
import assert from "node:assert/strict";
import { evaluateRequest, hostMatches } from "../src/policy.js";

const base = {
  enforce: true,
  redact_pii: false,
  pii_types: [],
  allowed_hosts: [],
  max_request_bytes: 0,
  spend_cap_usd: 0,
};

test("host list matches a DNS suffix and not a lookalike", () => {
  assert.equal(hostMatches("api.openai.com", ["openai.com"]), true);
  assert.equal(hostMatches("notopenai.com", ["openai.com"]), false);
  assert.equal(hostMatches("openai.com", ["openai.com"]), true);
});

test("dry_run false names BLOCKED actions", () => {
  const r = evaluateRequest(
    { ...base, dry_run: false, blocked_hosts: ["openai.com"] },
    { hostname: "api.openai.com" },
  );
  assert.equal(r.would_block, true);
  assert.equal(r.primary_action, "BLOCKED_HOST");
});

test("dry_run true keeps the DRY_RUN prefix", () => {
  const r = evaluateRequest(
    { ...base, dry_run: true, blocked_hosts: ["api.openai.com"] },
    { hostname: "api.openai.com" },
  );
  assert.equal(r.primary_action, "DRY_RUN_BLOCKED_HOST");
});
