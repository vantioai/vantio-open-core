import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { fetchCloudConfig, fetchResidualRisk } from "../src/policy.js";
import { createGateMcpServer } from "../src/server.js";

const root = dirname(fileURLToPath(import.meta.url));
const serverSrc = readFileSync(join(root, "../src/server.js"), "utf8");

function withEnv(pairs, fn) {
  const previous = new Map();
  for (const [name, value] of Object.entries(pairs)) {
    previous.set(name, process.env[name]);
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
  return Promise.resolve()
    .then(fn)
    .finally(() => {
      for (const [name, value] of previous) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    });
}

async function captureFetch(fn) {
  const seen = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    seen.push({ url: String(url), opts });
    return {
      ok: true,
      status: 200,
      json: async () => ({ tier: "phantom", policy: { enforce: false }, gaps: [] }),
    };
  };
  try {
    await fn();
  } finally {
    globalThis.fetch = original;
  }
  return seen;
}

test("gate_get_policy and gate_residual_risk do not take an api_base tool argument", () => {
  assert.doesNotMatch(serverSrc, /api_base\s*:/);
  assert.doesNotMatch(serverSrc, /apiBase\s*:/);
});

test("fetchCloudConfig does not send VANTIO_API_KEY to a caller-supplied host", async () => {
  const seen = await captureFetch(() =>
    withEnv(
      { VANTIO_API_KEY: "from-env", VANTIO_API_BASE: "https://api.vantio.ai" },
      () => fetchCloudConfig({ apiBase: "https://evil.example/steal" }),
    ),
  );
  assert.equal(seen.length, 1);
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
  assert.equal(seen[0].url.startsWith("https://api.vantio.ai/"), true);
  assert.equal(seen[0].url.includes("evil.example"), false);
});

test("fetchResidualRisk does not send VANTIO_API_KEY to a caller-supplied host", async () => {
  const seen = await captureFetch(() =>
    withEnv(
      { VANTIO_API_KEY: "from-env", VANTIO_API_BASE: "https://control.example.test" },
      () => fetchResidualRisk({ apiBase: "https://evil.example/steal" }),
    ),
  );
  assert.equal(seen.length, 1);
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
  assert.equal(seen[0].url.startsWith("https://control.example.test/"), true);
  assert.equal(seen[0].url.includes("evil.example"), false);
});

test("an unset VANTIO_API_BASE stays on the default host when a caller passes apiBase", async () => {
  const seen = await captureFetch(() =>
    withEnv({ VANTIO_API_KEY: "from-env", VANTIO_API_BASE: undefined }, () =>
      fetchCloudConfig({ apiBase: "http://127.0.0.1:9" }),
    ),
  );
  assert.equal(seen.length, 1);
  assert.equal(seen[0].url.startsWith("https://api.vantio.ai/"), true);
  assert.equal(seen[0].url.includes("127.0.0.1"), false);
});

test("registered fetch tools drop api_base before the key is sent", async () => {
  const server = createGateMcpServer();
  for (const name of ["gate_get_policy", "gate_residual_risk"]) {
    const shape = server._registeredTools[name].inputSchema.shape;
    assert.equal(Object.hasOwn(shape, "api_base"), false);
    assert.equal(Object.hasOwn(shape, "api_key"), false);
  }
  const seen = await captureFetch(() =>
    withEnv({ VANTIO_API_KEY: "from-env", VANTIO_API_BASE: "https://api.vantio.ai" }, () =>
      server._registeredTools.gate_get_policy.handler({
        api_base: "https://evil.example/steal",
      }),
    ),
  );
  assert.equal(seen.length, 1);
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
  assert.equal(seen[0].url.startsWith("https://api.vantio.ai/"), true);
  assert.equal(seen[0].url.includes("evil.example"), false);
});

test("a blank VANTIO_API_BASE stays on the default host when a caller passes apiBase", async () => {
  const seen = await captureFetch(() =>
    withEnv({ VANTIO_API_KEY: "from-env", VANTIO_API_BASE: "  " }, () =>
      fetchResidualRisk("https://evil.example"),
    ),
  );
  assert.equal(seen.length, 1);
  assert.equal(seen[0].opts.headers["x-vantio-identity"], "from-env");
  assert.equal(seen[0].url.startsWith("https://api.vantio.ai/api/v1/residual-risk"), true);
  assert.equal(seen[0].url.includes("evil.example"), false);
});
