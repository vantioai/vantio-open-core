import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { redactPII } from "../src/index.ts";

describe("redactPII()", () => {
  test("redacts an SSN", () => {
    const r = redactPII("my ssn is 123-45-6789");
    assert.equal(r.text, "my ssn is [VANTIO_REDACTED:SSN]");
    assert.deepEqual(r.redactions, ["ssn"]);
  });

  test("redacts an email", () => {
    const r = redactPII("contact me at zach@vantio.ai please");
    assert.equal(r.text, "contact me at [VANTIO_REDACTED:EMAIL] please");
    assert.deepEqual(r.redactions, ["email"]);
  });

  test("redacts a credit card number", () => {
    const r = redactPII("card: 4111 1111 1111 1111");
    assert.match(r.text, /\[VANTIO_REDACTED:CC\]/);
    assert.ok(r.redactions.includes("credit_card"));
  });

  test("redacts a phone number", () => {
    const r = redactPII("call (555) 123-4567 now");
    assert.match(r.text, /\[VANTIO_REDACTED:PHONE\]/);
    assert.ok(r.redactions.includes("phone"));
  });

  test("redacts multiple PII types in one string", () => {
    const r = redactPII("email a@b.com ssn 123-45-6789");
    assert.equal(r.redactions.length, 2);
    assert.doesNotMatch(r.text, /a@b\.com/);
    assert.doesNotMatch(r.text, /123-45-6789/);
  });

  test("only redacts the requested pii types", () => {
    const r = redactPII("email a@b.com ssn 123-45-6789", ["ssn"]);
    assert.deepEqual(r.redactions, ["ssn"]);
    assert.match(r.text, /a@b\.com/); // email untouched — not in the requested list
  });

  test("is case-insensitive on pii type names (dashboard persists uppercase)", () => {
    const r = redactPII("email a@b.com", ["EMAIL"]);
    assert.deepEqual(r.redactions, ["email"]);
  });

  test("ignores unknown pii type names instead of throwing", () => {
    assert.doesNotThrow(() => redactPII("hello", ["not_a_real_type"]));
  });

  test("returns the input unchanged when there is nothing to redact", () => {
    const r = redactPII("nothing sensitive here");
    assert.equal(r.text, "nothing sensitive here");
    assert.deepEqual(r.redactions, []);
  });

  test("never throws on non-string input — returns it unchanged", () => {
    // @ts-expect-error deliberately passing a bad type to verify runtime safety
    const r = redactPII(12345);
    assert.equal(r.text, 12345);
    assert.deepEqual(r.redactions, []);
  });
});
