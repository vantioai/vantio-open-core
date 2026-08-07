import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { withVantio, reportAnomaly, fetchPolicy } from "../src/index.ts";

describe("reportAnomaly()", () => {
  let server: http.Server;
  let baseUrl: string;
  let requests: Array<{ headers: http.IncomingHttpHeaders; body: unknown }>;
  let warnCalls: unknown[][];
  let originalWarn: typeof console.warn;

  beforeEach(async () => {
    requests = [];
    server = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        requests.push({ headers: req.headers, body: body ? JSON.parse(body) : null });
        if (req.url?.startsWith("/fail")) {
          res.writeHead(500).end();
          return;
        }
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      });
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const addr = server.address();
    baseUrl = typeof addr === "object" && addr ? `http://127.0.0.1:${addr.port}` : "";

    originalWarn = console.warn;
    warnCalls = [];
    console.warn = (...args: unknown[]) => { warnCalls.push(args); };
  });

  afterEach(async () => {
    console.warn = originalWarn;
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test("warns and skips when called outside a withVantio() frame", async () => {
    await reportAnomaly({ target_host: "api.openai.com" });
    assert.equal(requests.length, 0);
    assert.ok(warnCalls.some((c) => String(c[0]).includes("outside a withVantio")));
  });

  test("no-ops when no ingestUrl is configured (local-only mode)", async () => {
    await withVantio(async () => {
      await reportAnomaly({ target_host: "api.openai.com" });
    });
    assert.equal(requests.length, 0);
  });

  test("an env-derived ingestUrl alone does not activate cloud ingest (Tier 1 guard)", async () => {
    const saved = process.env.VANTIO_INGEST_URL;
    const savedCloud = process.env.VANTIO_CLOUD_INGEST;
    process.env.VANTIO_INGEST_URL = baseUrl;
    delete process.env.VANTIO_CLOUD_INGEST;
    try {
      await withVantio(async () => {
        await reportAnomaly({ target_host: "api.openai.com" });
      });
      assert.equal(requests.length, 0, "must not phone home just because VANTIO_INGEST_URL happens to be set");
    } finally {
      if (saved === undefined) delete process.env.VANTIO_INGEST_URL; else process.env.VANTIO_INGEST_URL = saved;
      if (savedCloud === undefined) delete process.env.VANTIO_CLOUD_INGEST; else process.env.VANTIO_CLOUD_INGEST = savedCloud;
    }
  });

  test("an explicitly supplied ingestUrl is sufficient opt-in (bypasses the env gate)", async () => {
    await withVantio(async () => {
      await reportAnomaly(
        { target_host: "api.openai.com", pid: 123, bytes_severed: 42, action_taken: "BLOCKED_HOST" },
        { ingestUrl: baseUrl, identity: "vk_test_key", auditMode: true }
      );
    }, { traceId: "trace-abc" });

    assert.equal(requests.length, 1);
    assert.equal(requests[0].headers["x-vantio-identity"], "vk_test_key");
    const body = requests[0].body as Record<string, unknown>;
    assert.equal(body.traceId, "trace-abc");
    assert.equal(body.auditMode, true);
    assert.deepEqual(body.eventPayload, {
      target_host: "api.openai.com",
      pid: 123,
      bytes_severed: 42,
      action_taken: "BLOCKED_HOST",
    });
  });

  test("warns (non-fatal) on a non-2xx ingest response", async () => {
    await withVantio(async () => {
      await reportAnomaly({ target_host: "x" }, { ingestUrl: `${baseUrl}/fail` });
    });
    assert.ok(warnCalls.some((c) => String(c[0]).includes("HTTP 500")));
  });

  test("warns (non-fatal), never throws, on a network failure", async () => {
    await assert.doesNotReject(
      withVantio(async () => {
        await reportAnomaly({ target_host: "x" }, { ingestUrl: "http://127.0.0.1:1" });
      })
    );
    assert.ok(warnCalls.some((c) => String(c[0]).includes("ingest request failed")));
  });
});

describe("fetchPolicy()", () => {
  let server: http.Server;
  let baseUrl: string;
  let responder: (req: http.IncomingMessage, res: http.ServerResponse) => void;

  beforeEach(async () => {
    responder = (_req, res) => res.writeHead(500).end();
    server = http.createServer((req, res) => responder(req, res));
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const addr = server.address();
    baseUrl = typeof addr === "object" && addr ? `http://127.0.0.1:${addr.port}` : "";
  });

  afterEach(async () => {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  });

  test("returns the normalized cloud policy on a 200 with a policy body", async () => {
    let seenHeader: string | undefined;
    responder = (req, res) => {
      seenHeader = req.headers["x-vantio-identity"] as string | undefined;
      const payload = JSON.stringify({ policy: { enforce: true, blocked_hosts: ["evil.com"] } });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(payload);
    };
    const policy = await fetchPolicy("vk_test_key", { ingestUrl: baseUrl });
    assert.equal(seenHeader, "vk_test_key");
    assert.equal(policy.enforce, true);
    assert.deepEqual(policy.blocked_hosts, ["evil.com"]);
    // Untouched fields still come from the default, proving normalizePolicy ran.
    assert.equal(policy.spend_cap_usd, 0);
  });

  test("fails open to DEFAULT_POLICY on a non-2xx response", async () => {
    responder = (_req, res) => res.writeHead(403).end();
    const policy = await fetchPolicy("vk_test_key", { ingestUrl: baseUrl });
    assert.equal(policy.enforce, false);
  });

  test("fails open to DEFAULT_POLICY on a malformed body (no policy key)", async () => {
    responder = (_req, res) => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ unexpected: true }));
    };
    const policy = await fetchPolicy("vk_test_key", { ingestUrl: baseUrl });
    assert.equal(policy.enforce, false);
  });

  test("fails open to DEFAULT_POLICY on a network failure", async () => {
    const policy = await fetchPolicy("vk_test_key", { ingestUrl: "http://127.0.0.1:1" });
    assert.equal(policy.enforce, false);
    assert.deepEqual(policy.pii_types, ["ssn", "email", "credit_card", "phone"]);
  });

  test("respects a caller-supplied timeout", async () => {
    responder = () => {
      /* never respond — force the timeout path */
    };
    const start = Date.now();
    const policy = await fetchPolicy("vk_test_key", { ingestUrl: baseUrl, timeoutMs: 200 });
    const elapsed = Date.now() - start;
    assert.equal(policy.enforce, false);
    assert.ok(elapsed < 2000, `expected the 200ms timeout to fire quickly, took ${elapsed}ms`);
  });
});
