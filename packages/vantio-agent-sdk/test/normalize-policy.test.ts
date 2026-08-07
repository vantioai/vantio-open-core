import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { normalizePolicy, DEFAULT_POLICY } from "../src/index.ts";

describe("normalizePolicy()", () => {
  test("passes a well-formed policy through unchanged", () => {
    const input = {
      enforce: true,
      redact_pii: true,
      pii_types: ["ssn", "email"],
      allowed_hosts: ["api.openai.com"],
      blocked_hosts: ["evil.example.com"],
      max_request_bytes: 4096,
      spend_cap_usd: 5,
      dry_run: false,
    };
    assert.deepEqual(normalizePolicy(input), input);
  });

  test("dry_run defaults to false when absent", () => {
    assert.equal(normalizePolicy({}).dry_run, false);
    assert.equal(normalizePolicy({ dry_run: true }).dry_run, true);
  });

  test("coerces a non-boolean dry_run to the default (false)", () => {
    assert.equal(normalizePolicy({ dry_run: "true" }).dry_run, false);
    assert.equal(normalizePolicy({ dry_run: 1 }).dry_run, false);
  });

  test("falls back to DEFAULT_POLICY entirely for null/non-object input", () => {
    assert.deepEqual(normalizePolicy(null), DEFAULT_POLICY);
    assert.deepEqual(normalizePolicy(undefined), DEFAULT_POLICY);
    assert.deepEqual(normalizePolicy("not an object"), DEFAULT_POLICY);
    assert.deepEqual(normalizePolicy(42), DEFAULT_POLICY);
  });

  test("falls back to DEFAULT_POLICY for an empty object", () => {
    assert.deepEqual(normalizePolicy({}), DEFAULT_POLICY);
  });

  // Regression coverage for the exact malformed-payload shapes the source
  // comments call out as previously dangerous (would throw inside
  // enforcement's .includes/for..of/numeric comparisons if trusted verbatim).
  test("coerces a null blocked_hosts to the default empty array instead of throwing", () => {
    const p = normalizePolicy({ blocked_hosts: null });
    assert.deepEqual(p.blocked_hosts, []);
  });

  test("coerces a non-array pii_types (e.g. a bare string) to the default array", () => {
    const p = normalizePolicy({ pii_types: "email" });
    assert.deepEqual(p.pii_types, DEFAULT_POLICY.pii_types);
  });

  test("filters non-string entries out of a mixed-type array field", () => {
    const p = normalizePolicy({ allowed_hosts: ["good.com", 123, null, "also-good.com"] });
    assert.deepEqual(p.allowed_hosts, ["good.com", "also-good.com"]);
  });

  test('coerces a numeric-string spend_cap_usd (e.g. "x") to the default', () => {
    const p = normalizePolicy({ spend_cap_usd: "x" });
    assert.equal(p.spend_cap_usd, DEFAULT_POLICY.spend_cap_usd);
  });

  test("accepts a valid numeric string for a numeric field", () => {
    const p = normalizePolicy({ spend_cap_usd: "12.5" });
    assert.equal(p.spend_cap_usd, 12.5);
  });

  test("rejects a negative number for a non-negative field", () => {
    const p = normalizePolicy({ max_request_bytes: -100 });
    assert.equal(p.max_request_bytes, DEFAULT_POLICY.max_request_bytes);
  });

  test("coerces a non-boolean enforce value to the default", () => {
    assert.equal(normalizePolicy({ enforce: "true" }).enforce, DEFAULT_POLICY.enforce);
    assert.equal(normalizePolicy({ enforce: 1 }).enforce, DEFAULT_POLICY.enforce);
  });

  test("merges partial input with defaults field-by-field", () => {
    const p = normalizePolicy({ enforce: true });
    assert.equal(p.enforce, true);
    assert.deepEqual(p.pii_types, DEFAULT_POLICY.pii_types);
    assert.equal(p.spend_cap_usd, DEFAULT_POLICY.spend_cap_usd);
  });
});
