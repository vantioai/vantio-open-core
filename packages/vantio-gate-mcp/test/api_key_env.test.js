import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { fetchCloudConfig, fetchResidualRisk } from "../src/policy.js";

const root = dirname(fileURLToPath(import.meta.url));
const serverSrc = readFileSync(join(root, "../src/server.js"), "utf8");

function withEnv(name, value, fn) {
  const previous = process.env[name];
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      if (previous === undefined) delete process.env[name];
      else process.env[name] = previous;
    });
}

test("gate tool schemas do not accept an api_key argument", () => {
  assert.doesNotMatch(serverSrc, /api_key\s*:/);
  assert.doesNotMatch(serverSrc, /apiKey\s*:/);
  assert.doesNotMatch(serverSrc, /pass api_key/);
});

test("fetchCloudConfig sends the environment key and ignores a tool argument", async () => {
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    seen.push({ url, opts });
    return {
      ok: true,
      status: 200,
      json: async () => ({ tier: "phantom", policy: { enforce: false } }),
    };
  };
  try {
    await withEnv("VANTIO_API_KEY", "from-env", async () => {
      const result = await fetchCloudConfig({
        apiKey: "from-tool",
        apiBase: "https://example.test",
      });
      assert.equal(result.ok, true);
    });
  } finally {
    globalThis.fetch = original;
  }
  assert.equal(seen.length, 1);
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
  assert.equal(String(seen[0].url).startsWith("https://example.test/"), true);
});

test("fetchCloudConfig does not use a tool api key when the environment is empty", async () => {
  let called = false;
  const original = globalThis.fetch;
  globalThis.fetch = async () => {
    called = true;
    throw new Error("fetch should not run");
  };
  try {
    await withEnv("VANTIO_API_KEY", undefined, async () => {
      const result = await fetchCloudConfig({ apiKey: "from-tool" });
      assert.equal(result.ok, false);
      assert.equal(result.error, "missing_api_key");
      assert.doesNotMatch(result.hint || "", /pass api_key/);
    });
  } finally {
    globalThis.fetch = original;
  }
  assert.equal(called, false);
});

test("fetchResidualRisk sends the environment key and ignores a tool argument", async () => {
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    seen.push({ url, opts });
    return { ok: true, status: 200, json: async () => ({ gaps: [] }) };
  };
  try {
    await withEnv("VANTIO_API_KEY", "from-env", async () => {
      const result = await fetchResidualRisk({
        apiKey: "from-tool",
        apiBase: "https://example.test",
      });
      assert.equal(result.ok, true);
    });
  } finally {
    globalThis.fetch = original;
  }
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
});
