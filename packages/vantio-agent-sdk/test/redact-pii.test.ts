import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { redactPII } from "../src/index.ts";

describe("redactPII()", () => {
  test("does not rewrite an SSN", () => {
    const r = redactPII("my ssn is 123-45-6789");
    assert.equal(r.text, "my ssn is 123-45-6789");
    assert.deepEqual(r.redactions, []);
  });

  test("does not rewrite an email", () => {
    const r = redactPII("contact me at zach@vantio.ai please");
    assert.equal(r.text, "contact me at zach@vantio.ai please");
    assert.deepEqual(r.redactions, []);
  });

  test("does not rewrite a credit card number", () => {
    const original = "card: 4111 1111 1111 1111";
    const r = redactPII(original);
    assert.equal(r.text, original);
    assert.deepEqual(r.redactions, []);
  });

  test("does not rewrite a phone number", () => {
    const original = "call (555) 123-4567 now";
    const r = redactPII(original);
    assert.equal(r.text, original);
    assert.deepEqual(r.redactions, []);
  });

  test("does not rewrite mixed PII", () => {
    const original = "email a@b.com ssn 123-45-6789";
    const r = redactPII(original);
    assert.equal(r.text, original);
    assert.deepEqual(r.redactions, []);
  });

  test("does not rewrite when a type list is supplied", () => {
    const original = "email a@b.com ssn 123-45-6789";
    const r = redactPII(original, ["ssn"]);
    assert.equal(r.text, original);
    assert.deepEqual(r.redactions, []);
  });

  test("does not throw on an unknown type name", () => {
    assert.doesNotThrow(() => redactPII("hello", ["not_a_real_type"]));
  });

  test("returns ordinary text unchanged", () => {
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
