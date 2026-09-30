import { test } from "node:test";
import assert from "node:assert/strict";
import { parseIngestUrl } from "../bin/ingest-url.cjs";

test("Node keeps the VANTIO_INGEST_URL path", () => {
  const parsed = parseIngestUrl("http://127.0.0.1:9/custom/base/");
  assert.equal(parsed.ok, true);
  assert.equal(parsed.href, "http://127.0.0.1:9/custom/base");
  assert.equal(parsed.href.includes("/custom/base"), true);
  assert.notEqual(parsed.href, "http://127.0.0.1:9");
});

test("a missing ingest URL stays on the public origin", () => {
  const parsed = parseIngestUrl("");
  assert.equal(parsed.href, "https://vantio.ai");
  assert.equal(parsed.publicHost, true);
});
