import { test } from "node:test";
import assert from "node:assert/strict";
import {
  normalizePolicy,
  evaluateRequest,
  DEFAULT_POLICY,
} from "../src/policy.js";

test("normalizePolicy coerces bad fields", () => {
  const p = normalizePolicy({
    enforce: "yes",
    blocked_hosts: null,
    max_request_bytes: -1,
  });
  assert.equal(p.enforce, false);
  assert.deepEqual(p.blocked_hosts, []);
  assert.equal(p.max_request_bytes, 0);
});

test("evaluate allows when enforce=false", () => {
  const r = evaluateRequest(
    { ...DEFAULT_POLICY, enforce: false, blocked_hosts: ["api.openai.com"] },
    { hostname: "api.openai.com", request_bytes: 100 },
  );
  assert.equal(r.would_block, false);
  assert.equal(r.primary_action, "OBSERVED");
});

test("evaluate would block host when enforce=true", () => {
  const r = evaluateRequest(
    {
      enforce: true,
      dry_run: true,
      blocked_hosts: ["api.openai.com"],
      allowed_hosts: [],
      redact_pii: false,
      pii_types: [],
      max_request_bytes: 0,
      spend_cap_usd: 0,
    },
    { hostname: "api.openai.com", request_bytes: 10 },
  );
  assert.equal(r.would_block, true);
  assert.equal(r.primary_action, "DRY_RUN_BLOCKED_HOST");
});

test("evaluate would block size", () => {
  const r = evaluateRequest(
    {
      enforce: true,
      dry_run: true,
      blocked_hosts: [],
      allowed_hosts: [],
      max_request_bytes: 100,
      spend_cap_usd: 0,
      redact_pii: false,
      pii_types: [],
    },
    { hostname: "api.openai.com", request_bytes: 500 },
  );
  assert.equal(r.would_block, true);
  assert.equal(r.primary_action, "DRY_RUN_BLOCKED_SIZE");
});
