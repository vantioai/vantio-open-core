import { test, describe } from "node:test";
import assert from "node:assert/strict";
import {
  withVantio,
  shield,
  getCurrentTraceId,
  getCurrentContext,
} from "../src/index.ts";

describe("withVantio() / shield()", () => {
  test("shield is the same function as withVantio (canonical alias)", () => {
    assert.equal(shield, withVantio);
  });

  test("generates a random trace ID when none is supplied", async () => {
    let seen: string | undefined;
    await withVantio(async () => {
      seen = getCurrentTraceId();
    });
    assert.ok(seen);
    assert.match(seen!, /^[0-9a-f-]{36}$/i);
  });

  test("uses an explicitly supplied trace ID", async () => {
    let seen: string | undefined;
    await withVantio(
      async () => {
        seen = getCurrentTraceId();
      },
      { traceId: "fixed-trace-id-123" }
    );
    assert.equal(seen, "fixed-trace-id-123");
  });

  test("getCurrentTraceId() and getCurrentContext() are undefined outside any frame", () => {
    assert.equal(getCurrentTraceId(), undefined);
    assert.equal(getCurrentContext(), undefined);
  });

  test("propagates the trace ID across await boundaries and nested async calls", async () => {
    async function innerHop(): Promise<string | undefined> {
      await new Promise((resolve) => setTimeout(resolve, 5));
      return getCurrentTraceId();
    }

    let seenInHop: string | undefined;
    let seenAtRoot: string | undefined;
    await withVantio(
      async () => {
        seenAtRoot = getCurrentTraceId();
        seenInHop = await innerHop();
      },
      { traceId: "propagated-id" }
    );
    assert.equal(seenAtRoot, "propagated-id");
    assert.equal(seenInHop, "propagated-id");
  });

  test("nested withVantio scopes a new trace ID only within the inner callback", async () => {
    const seen: Record<string, string | undefined> = {};
    await withVantio(
      async () => {
        seen.outerBefore = getCurrentTraceId();
        await withVantio(
          async () => {
            seen.inner = getCurrentTraceId();
          },
          { traceId: "inner-id" }
        );
        seen.outerAfter = getCurrentTraceId();
      },
      { traceId: "outer-id" }
    );
    assert.equal(seen.outerBefore, "outer-id");
    assert.equal(seen.inner, "inner-id");
    assert.equal(seen.outerAfter, "outer-id", "outer context must be restored after the inner frame completes");
  });

  test("returns the callback's resolved value", async () => {
    const result = await withVantio(async () => 42);
    assert.equal(result, 42);
  });

  test("propagates a rejection from the callback", async () => {
    await assert.rejects(
      () => withVantio(async () => { throw new Error("boom"); }),
      /boom/
    );
  });

  test("concurrent withVantio calls don't leak trace IDs into each other", async () => {
    const results = await Promise.all([
      withVantio(async () => {
        await new Promise((r) => setTimeout(r, Math.random() * 10));
        return getCurrentTraceId();
      }, { traceId: "call-a" }),
      withVantio(async () => {
        await new Promise((r) => setTimeout(r, Math.random() * 10));
        return getCurrentTraceId();
      }, { traceId: "call-b" }),
    ]);
    assert.deepEqual(results.sort(), ["call-a", "call-b"]);
  });
});
