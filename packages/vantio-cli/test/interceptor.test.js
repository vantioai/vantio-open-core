// Integration tests for bin/interceptor.cjs, run exactly the way it runs in
// production: as a --require hook in a fresh child Node process. This is
// deliberately black-box (no refactoring of the security-critical redaction/
// enforcement logic to make it more "testable") — it drives the real file
// through a local mock control-plane + target server and asserts on what
// actually crossed the wire.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import http2 from "node:http2";
import net from "node:net";
import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INTERCEPTOR_PATH = join(__dirname, "..", "bin", "interceptor.cjs");

// Runs `node --require interceptor.cjs -e <agentScript>` in a fresh process
// with the given env layered over a minimal base. Resolves with
// { code, stdout, stderr } — never rejects on a non-zero exit so callers can
// assert on failure paths too.
function runAgent(env, agentScript) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ["--require", INTERCEPTOR_PATH, "-e", agentScript],
      { env: { PATH: process.env.PATH, ...env }, stdio: ["ignore", "pipe", "pipe"], cwd: join(__dirname, "..") }
    );
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

// The agent script fetches TARGET_URL (env) once and prints the outcome as a
// single JSON line on stdout so the test can assert on it.
const FETCH_ONCE_SCRIPT = `
(async () => {
  const res = await fetch(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
  });
  const text = await res.text();
  process.stdout.write(JSON.stringify({ status: res.status, body: text }) + "\\n");
})();
`;

// Agents that `import { fetch } from "undici"` never hit globalThis.fetch.
const UNDICI_FETCH_ONCE_SCRIPT = `
(async () => {
  const { fetch: undiciFetch } = require("undici");
  const res = await undiciFetch(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
  });
  const text = await res.text();
  process.stdout.write(JSON.stringify({ status: res.status, body: text }) + "\\n");
})();
`;

const UNDICI_REQUEST_ONCE_SCRIPT = `
(async () => {
  const { request } = require("undici");
  const { statusCode, body } = await request(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
  });
  const text = await body.text();
  process.stdout.write(JSON.stringify({ status: statusCode, body: text }) + "\\n");
})();
`;

const UNDICI_CLIENT_ONCE_SCRIPT = `
(async () => {
  const { Client } = require("undici");
  const u = new URL(process.env.TARGET_URL);
  const client = new Client(u.origin);
  try {
    const { statusCode, body } = await client.request({
      path: u.pathname,
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
    });
    const text = await body.text();
    process.stdout.write(JSON.stringify({ status: statusCode, body: text }) + "\\n");
  } finally {
    await client.close();
  }
})();
`;

const UNDICI_STREAM_ONCE_SCRIPT = `
(async () => {
  const { stream } = require("undici");
  const { Writable } = require("node:stream");
  const chunks = [];
  let status = 0;
  await stream(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
  }, ({ statusCode }) => {
    status = statusCode;
    return new Writable({
      write(chunk, enc, cb) { chunks.push(Buffer.from(chunk)); cb(); },
    });
  });
  process.stdout.write(JSON.stringify({ status, body: Buffer.concat(chunks).toString() }) + "\\n");
})();
`;

const UNDICI_DISPATCH_ONCE_SCRIPT = `
(async () => {
  const { Client } = require("undici");
  const u = new URL(process.env.TARGET_URL);
  const client = new Client(u.origin);
  try {
    const result = await new Promise((resolve, reject) => {
      const chunks = [];
      let statusCode = 0;
      const ok = client.dispatch({
        path: u.pathname + u.search,
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
      }, {
        onConnect() {},
        onError(err) { reject(err); },
        onHeaders(status) { statusCode = status; return true; },
        onData(chunk) { chunks.push(Buffer.from(chunk)); return true; },
        onComplete() { resolve({ status: statusCode, body: Buffer.concat(chunks).toString() }); },
      });
      if (!ok) reject(new Error("dispatch returned false"));
    });
    process.stdout.write(JSON.stringify(result) + "\\n");
  } finally {
    await client.close();
  }
})();
`;

const UNDICI_PIPELINE_ONCE_SCRIPT = `
(async () => {
  const { Client } = require("undici");
  const { Writable } = require("node:stream");
  const u = new URL(process.env.TARGET_URL);
  const client = new Client(u.origin);
  try {
    const chunks = [];
    const result = await new Promise((resolve, reject) => {
      let status = 0;
      const duplex = client.pipeline({
        path: u.pathname + u.search,
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }),
      }, ({ statusCode, body }) => {
        status = statusCode;
        return body;
      });
      duplex.on("error", reject);
      duplex.end();
      const sink = new Writable({
        write(chunk, enc, cb) { chunks.push(Buffer.from(chunk)); cb(); },
      });
      sink.on("finish", () => resolve({ status, body: Buffer.concat(chunks).toString() }));
      sink.on("error", reject);
      duplex.pipe(sink);
    });
    process.stdout.write(JSON.stringify(result) + "\\n");
  } finally {
    await client.close();
  }
})();
`;

const UNDICI_CONNECT_ONCE_SCRIPT = `
(async () => {
  const { connect } = require("undici");
  try {
    const data = await connect(process.env.TARGET_URL);
    if (data && data.socket) data.socket.destroy();
    process.stdout.write(JSON.stringify({ status: data && data.statusCode, error: null }) + "\\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({
      status: 0,
      error: err && err.code ? String(err.code) : "Error",
      body: err && err.message ? String(err.message) : "",
    }) + "\\n");
  }
})();
`;

const UNDICI_UPGRADE_ONCE_SCRIPT = `
(async () => {
  const { upgrade } = require("undici");
  try {
    const data = await upgrade(process.env.TARGET_URL, { protocol: "Websocket" });
    if (data && data.socket) data.socket.destroy();
    process.stdout.write(JSON.stringify({ status: 101, error: null }) + "\\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({
      status: 0,
      error: err && err.code ? String(err.code) : "Error",
      body: err && err.message ? String(err.message) : "",
    }) + "\\n");
  }
})();
`;

describe("interceptor.cjs (integration)", { timeout: 60000 }, () => {
  let server, baseUrl, targetUrl, configPolicy, configTier, requests;

  beforeEach(async () => {
    requests = { config: [], ingest: [], target: [], wsFrames: [] };
    configPolicy = { enforce: false, redact_pii: false, pii_types: [], allowed_hosts: [], blocked_hosts: [], max_request_bytes: 0, spend_cap_usd: 0 };
    configTier = "ENTERPRISE";

    server = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        if (req.url.startsWith("/api/v1/config")) {
          requests.config.push({ headers: req.headers });
          const payload = JSON.stringify({ policy: configPolicy, tier: configTier });
          res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(payload) });
          res.end(payload);
          return;
        }
        if (req.url === "/api/v1/ingest") {
          requests.ingest.push({ headers: req.headers, body: body ? JSON.parse(body) : null });
          const payload = JSON.stringify({ status: 0 });
          res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(payload) });
          res.end(payload);
          return;
        }
        if (req.url === "/v1/target") {
          requests.target.push({ headers: req.headers, body });
          const payload = JSON.stringify({ reply: "ok" });
          res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(payload) });
          res.end(payload);
          return;
        }
        res.writeHead(404).end();
      });
    });
    server.on("connect", (req, socket) => {
      requests.target.push({ method: "CONNECT", url: req.url, body: "" });
      socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
      socket.destroy();
    });
    server.on("upgrade", (req, socket) => {
      requests.target.push({ method: "UPGRADE", url: req.url, headers: req.headers, body: "" });
      if (req.url && String(req.url).startsWith("/v1/ws")) {
        const key = req.headers["sec-websocket-key"];
        if (key) {
          const accept = createHash("sha1")
            .update(String(key) + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11")
            .digest("base64");
          socket.write(
            "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: "
            + accept + "\r\n\r\n"
          );
        } else {
          socket.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n");
        }
        const idle = setTimeout(() => { try { socket.destroy(); } catch { /* ignore */ } }, 300);
        socket.on("data", (c) => {
          requests.wsFrames.push(Buffer.from(c));
          clearTimeout(idle);
          try { socket.destroy(); } catch { /* ignore */ }
        });
        socket.on("close", () => clearTimeout(idle));
        return;
      }
      socket.write("HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n");
      socket.destroy();
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    baseUrl = `http://127.0.0.1:${server.address().port}`;
    targetUrl = `${baseUrl}/v1/target`;
  });

  afterEach(async () => {
    if (typeof server.closeAllConnections === "function") server.closeAllConnections();
    await new Promise((resolve) => server.close(resolve));
  });

  // NOTE: the "observed" logging branch only fires for a host in the
  // hardcoded LLM_HOSTS set (real internet hostnames like api.openai.com),
  // which can't be safely redirected to a local mock server without fragile
  // DNS-level mocking. What IS fully verifiable without that: free mode never
  // even fetches a policy (policyReady short-circuits), and an out-of-scope
  // host (our local mock, matching neither LLM_HOSTS nor any policy list)
  // always passes straight through untouched and is never reported.
  test("FREE_MODE (no API key): never fetches policy, passes through untouched, never reports", async () => {
    const { code, stdout } = await runAgent({ TARGET_URL: targetUrl }, FETCH_ONCE_SCRIPT);
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200);

    assert.equal(requests.config.length, 0, "FREE_MODE must never fetch a cloud policy");
    assert.equal(requests.target.length, 1);
    assert.match(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.equal(requests.ingest.length, 0);
  });

  test("PAID_MODE, enforce=false: call allowed through, ingest records action ALLOWED", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200);

    assert.equal(requests.target.length, 1);
    assert.equal(requests.ingest.length, 1);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "ALLOWED");
    assert.notEqual(
      requests.ingest[0].body.eventPayload.mediation,
      "node_curl",
      "fetch must stay a single ingest event, not a node_curl wrap"
    );
    assert.notEqual(
      requests.ingest[0].body.eventPayload.mediation,
      "node_wget",
      "fetch must stay a single ingest event, not a node_wget wrap"
    );
    assert.notEqual(
      requests.ingest[0].body.eventPayload.mediation,
      "node_ws",
      "fetch must stay a single ingest event, not a node_ws wrap"
    );
    assert.ok(
      requests.ingest[0].body.eventPayload.bytes_observed != null,
      "ingest must set bytes_observed so Mission Control KPIs roll up wrap events"
    );
  });

  test("PAID_MODE, redact_pii=true: email stripped before the call leaves the process", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.redact_pii = true;
    configPolicy.pii_types = ["email"];
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);

    assert.equal(requests.target.length, 1);
    assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "REDACTED");
  });

  test("PAID_MODE, enforce=true + blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);

    assert.equal(requests.target.length, 0, "the blocked host must never receive the request");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("authenticated but FREE tier: never calls ingest even though a policy is present (regression guard)", async () => {
    // Regression test for the silent-403 bug: a key that authenticates fine
    // but belongs to a non-paid tenant must never be treated as cloud-sync
    // eligible, no matter what the (fail-open) policy body contains.
    configTier = "FREE";
    configPolicy.allowed_hosts = ["127.0.0.1"];
    const { code, stderr } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl, VANTIO_SUMMARY: "1" },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);

    assert.equal(requests.target.length, 1, "the call itself must still go through");
    assert.equal(requests.ingest.length, 0, "a free-tier key must never reach /api/v1/ingest");
    assert.match(stderr, /Free plan.*observed locally only/);
    assert.doesNotMatch(stderr, /Events routed to your Vantio dashboard/);
  });

  test("authenticated, but host out of scope: passes through untouched and is never reported", async () => {
    // 127.0.0.1 is neither a known LLM host nor named in the (default) policy
    // — even though a real key is present and the policy IS fetched, scope
    // must still gate everything else. Unrelated traffic (a DB call, an
    // internal service, etc.) must never be redacted, blocked, or reported.
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    assert.equal(requests.config.length, 1, "paid mode fetches the policy once to determine scope");
    assert.equal(requests.target.length, 1);
    assert.match(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.equal(requests.ingest.length, 0);
  });

  test("PAID_MODE, enforce=true + max_request_bytes: oversized request is blocked", async () => {
    configPolicy.enforce = true;
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.max_request_bytes = 10; // tiny cap — FETCH_ONCE_SCRIPT body >> 10 bytes
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403, "oversized request must be blocked with 403");
    assert.match(result.body, /request_too_large/);

    assert.equal(requests.target.length, 0, "blocked request must never reach the target");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_SIZE");
  });

  test("PAID_MODE, enforce=true + spend_cap_usd: second call blocked after cap exceeded", async () => {
    // Set an impossibly small cap so it's exceeded by any call.
    // The mock server responds with a content-length so spend accounting is synchronous.
    configPolicy.enforce = true;
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.spend_cap_usd = 0.000001; // sub-micro cap: any response exceeds it

    // Two sequential fetches in the same process — first succeeds, second is blocked.
    const TWO_CALLS_SCRIPT = `
(async () => {
  const r1 = await fetch(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ msg: "first call" }),
  });
  const t1 = await r1.text();
  const r2 = await fetch(process.env.TARGET_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ msg: "second call" }),
  });
  const t2 = await r2.text();
  process.stdout.write(JSON.stringify({ s1: r1.status, s2: r2.status, b2: t2 }) + "\\n");
})();
`;
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      TWO_CALLS_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.s1, 200, "first call must succeed");
    assert.equal(result.s2, 403, "second call must be blocked once spend cap is reached");
    assert.match(result.b2, /spend_cap_reached/);

    const spendBlocks = requests.ingest.filter(
      (r) => r.body?.eventPayload?.action_taken === "BLOCKED_SPEND"
    );
    assert.equal(spendBlocks.length, 1, "exactly one BLOCKED_SPEND event must be reported");
  });

  test("PAID_MODE, dry_run=true + blocked_hosts: call is allowed through and DRY_RUN event reported", async () => {
    // dry_run=true + enforce=true: the interceptor must LOG the would-be block
    // and report a DRY_RUN_BLOCKED_HOST event, but NOT return a 403.
    configPolicy.enforce = true;
    configPolicy.dry_run = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout, stderr } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    // Call must go through (no 403) because dry_run=true
    assert.equal(result.status, 200, "dry_run must not block the call");
    assert.equal(requests.target.length, 1, "target must receive the call in dry_run mode");

    // Stderr must mention DRY_RUN
    assert.match(stderr, /DRY_RUN/);

    // Ingest must carry a DRY_RUN_BLOCKED_HOST event
    const dryRunEvents = requests.ingest.filter(
      (r) => r.body?.eventPayload?.action_taken === "DRY_RUN_BLOCKED_HOST"
    );
    assert.equal(dryRunEvents.length, 1, "exactly one DRY_RUN_BLOCKED_HOST event must be reported");
  });

  test("PAID_MODE, dry_run=true + max_request_bytes: oversized call allowed, DRY_RUN_BLOCKED_SIZE reported", async () => {
    configPolicy.enforce = true;
    configPolicy.dry_run = true;
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.max_request_bytes = 10; // smaller than FETCH_ONCE_SCRIPT body
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200, "dry_run must not block oversized request");

    const sizeEvents = requests.ingest.filter(
      (r) => r.body?.eventPayload?.action_taken === "DRY_RUN_BLOCKED_SIZE"
    );
    assert.equal(sizeEvents.length, 1, "exactly one DRY_RUN_BLOCKED_SIZE event must be reported");
  });

  const HTTP_GET_SCRIPT = `
const http = require("http");
function go() {
  http.get(process.env.TARGET_URL, (res) => {
    let body = "";
    res.on("data", (c) => { body += c; });
    res.on("end", () => {
      process.stdout.write(JSON.stringify({ status: res.statusCode, body }) + "\\n");
    });
  }).on("error", (err) => {
    process.stdout.write(JSON.stringify({ error: err.code || err.message }) + "\\n");
  });
}
// Paid mode loads policy over fetch (async). request() is sync — wait so
// last-known policy is the cloud one, same as a live agent after startup.
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  test("FREE_MODE Node http.get to extra LLM host: OBSERVED, target reached, never ingest", async () => {
    const { code, stdout, stderr } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1" },
      HTTP_GET_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200);
    assert.equal(requests.target.length, 1, "observe must not block http.get");
    assert.equal(requests.ingest.length, 0, "free mode must never ingest");
    assert.match(stderr, /OBSERVED/);
  });

  test("PAID_MODE Node http.get + blocked_hosts: target never reached, BLOCKED_HOST ingest", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      HTTP_GET_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.error, "VANTIO_GATE_BLOCKED");
    assert.equal(requests.target.length, 0, "blocked http.get must never reach the target");
    assert.equal(requests.ingest.length, 1, "http.get must not also ingest a raw net.connect event");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_http");
  });

  test("PAID_MODE Node http.get out of scope: passes through, never reported", async () => {
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      HTTP_GET_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200);
    assert.equal(requests.target.length, 1);
    assert.equal(requests.ingest.length, 0);
  });

  test("PAID_MODE dry_run + Node http.get blocked_hosts: call goes through, DRY_RUN reported", async () => {
    configPolicy.enforce = true;
    configPolicy.dry_run = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout, stderr } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      HTTP_GET_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 200);
    assert.equal(requests.target.length, 1);
    assert.match(stderr, /DRY_RUN/);
    const dry = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "DRY_RUN_BLOCKED_HOST");
    assert.equal(dry.length, 1);
  });

  const CLIENT_REQUEST_SCRIPT = `
const http = require("http");
function go() {
  const u = new URL(process.env.TARGET_URL);
  const req = new http.ClientRequest({
    protocol: u.protocol,
    hostname: u.hostname,
    port: u.port,
    path: u.pathname,
    method: "GET",
  });
  req.on("response", (res) => {
    let body = "";
    res.on("data", (c) => { body += c; });
    res.on("end", () => {
      process.stdout.write(JSON.stringify({ status: res.statusCode, body }) + "\\n");
    });
  });
  req.on("error", (err) => {
    process.stdout.write(JSON.stringify({ error: err.code || err.message }) + "\\n");
  });
  req.end();
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  test("PAID_MODE Node http.ClientRequest + blocked_hosts: target never reached", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      CLIENT_REQUEST_SCRIPT
    );
    assert.equal(code, 0, stdout);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.error, "VANTIO_GATE_BLOCKED");
    assert.equal(requests.target.length, 0, "blocked ClientRequest must never reach the target");
    assert.equal(requests.ingest.length, 1, "ClientRequest must not also ingest a raw net.connect event");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_http");
  });

  test("FREE_MODE fetch to 127.0.0.1:11434 is OBSERVED as local Ollama without EXTRA_LLM_HOSTS", async () => {
    let ollamaServer;
    try {
      ollamaServer = http.createServer((req, res) => {
        res.writeHead(200, { "content-type": "application/json" });
        res.end(JSON.stringify({ reply: "ok" }));
      });
      await new Promise((resolve, reject) => {
        ollamaServer.once("error", reject);
        ollamaServer.listen(11434, "127.0.0.1", resolve);
      });
    } catch {
      return; // port busy — catalog unit test still covers the matcher
    }
    try {
      const { code, stderr } = await runAgent(
        { TARGET_URL: "http://127.0.0.1:11434/v1/target" },
        FETCH_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      assert.match(stderr, /OBSERVED|Outbound LLM call intercepted/);
    } finally {
      await new Promise((resolve) => ollamaServer.close(resolve));
    }
  });

  test("PAID_MODE Node http.get + spend_cap: second call BLOCKED_SPEND", async () => {
    configPolicy.enforce = true;
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.spend_cap_usd = 0.000001;
    const TWO_HTTP_SCRIPT = `
const http = require("http");
function one(url) {
  return new Promise((resolve) => {
    http.get(url, (res) => {
      let body = "";
      res.on("data", (c) => { body += c; });
      res.on("end", () => resolve({ status: res.statusCode, body }));
    }).on("error", (err) => resolve({ error: err.code || err.message }));
  });
}
(async () => {
  await new Promise((r) => setTimeout(r, 200));
  const a = await one(process.env.TARGET_URL);
  const b = await one(process.env.TARGET_URL);
  process.stdout.write(JSON.stringify({ a, b }) + "\\n");
})();
`;
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      TWO_HTTP_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.a.status, 200, "first http.get must succeed");
    assert.equal(result.b.error, "VANTIO_GATE_BLOCKED");
    const spend = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SPEND");
    assert.equal(spend.length, 1);
  });

  test("PAID_MODE, undici.fetch redact_pii: email stripped before the call leaves", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.redact_pii = true;
    configPolicy.pii_types = ["email"];
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    assert.equal(requests.target.length, 1);
    assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "REDACTED");
  });

  test("PAID_MODE, undici.fetch blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_FETCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "undici.fetch must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.request redact_pii: email stripped before the call leaves", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.redact_pii = true;
    configPolicy.pii_types = ["email"];
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_REQUEST_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    assert.equal(requests.target.length, 1);
    assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "REDACTED");
  });

  test("PAID_MODE, undici.request blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_REQUEST_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "undici.request must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.Client.request redact_pii: email stripped before the call leaves", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.redact_pii = true;
    configPolicy.pii_types = ["email"];
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_CLIENT_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    assert.equal(requests.target.length, 1);
    assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "REDACTED");
  });

  test("PAID_MODE, undici.Client.request blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_CLIENT_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "Client.request must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.stream redact_pii: email stripped before the call leaves", async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.redact_pii = true;
    configPolicy.pii_types = ["email"];
    const { code } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_STREAM_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    assert.equal(requests.target.length, 1);
    assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
    assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "REDACTED");
  });

  test("PAID_MODE, undici.stream blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_STREAM_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "undici.stream must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.Client.dispatch blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_DISPATCH_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "Client.dispatch must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.Client.pipeline blocked_hosts: request never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_PIPELINE_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.status, 403);
    assert.match(result.body, /blocked_by_vantio/);
    assert.equal(requests.target.length, 0, "Client.pipeline must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.connect blocked_hosts: CONNECT never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_CONNECT_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.error, "VANTIO_GATE_BLOCKED");
    assert.equal(requests.target.length, 0, "undici.connect must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  test("PAID_MODE, undici.upgrade blocked_hosts: upgrade never reaches the target", async () => {
    configPolicy.enforce = true;
    configPolicy.blocked_hosts = ["127.0.0.1"];
    const { code, stdout } = await runAgent(
      { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_UPGRADE_ONCE_SCRIPT
    );
    assert.equal(code, 0);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.error, "VANTIO_GATE_BLOCKED");
    assert.equal(requests.target.length, 0, "undici.upgrade must not bypass destination blocking");
    assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
  });

  const UNDICI_WS_WRITE_SCRIPT = `
(async () => {
  const { upgrade } = require("undici");
  try {
    const data = await upgrade(process.env.WS_URL, { protocol: "Websocket" });
    await new Promise((resolve, reject) => {
      const sock = data && data.socket;
      if (!sock) return reject(new Error("no_socket"));
      sock.once("error", reject);
      sock.write("hello-ws", (err) => err ? reject(err) : resolve());
    });
    try { data.socket.destroy(); } catch {}
    await new Promise((r) => setTimeout(r, 150));
    process.stdout.write(JSON.stringify({ ok: true }) + "\\n");
    process.exit(0);
  } catch (err) {
    process.stdout.write(JSON.stringify({
      ok: false,
      error: err && err.code ? String(err.code) : "Error",
      body: err && err.message ? String(err.message) : "",
    }) + "\\n");
    await new Promise((r) => setTimeout(r, 150));
    process.exit(0);
  }
})();
`;

  test("PAID_MODE, undici.upgrade write: ingest undici_ws ALLOWED with bytes_observed", { timeout: 15000 }, async () => {
    configPolicy.allowed_hosts = ["127.0.0.1"];
    const wsUrl = `${baseUrl}/v1/ws`;
    const { code, stdout } = await runAgent(
      { WS_URL: wsUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_WS_WRITE_SCRIPT
    );
    assert.equal(code, 0, stdout);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.ok, true);
    const frames = requests.wsFrames.map((b) => b.toString()).join("");
    assert.match(frames, /hello-ws/);
    const wsEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "undici_ws");
    assert.equal(wsEvents.length, 1);
    assert.equal(wsEvents[0].body.eventPayload.action_taken, "ALLOWED");
    assert.equal(wsEvents[0].body.eventPayload.bytes_observed, Buffer.byteLength("hello-ws"));
  });

  test("PAID_MODE, undici.upgrade write over max_request_bytes: BLOCKED_SIZE, payload never lands", { timeout: 15000 }, async () => {
    configPolicy.enforce = true;
    configPolicy.allowed_hosts = ["127.0.0.1"];
    configPolicy.max_request_bytes = 4;
    const wsUrl = `${baseUrl}/v1/ws`;
    const { code, stdout } = await runAgent(
      { WS_URL: wsUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
      UNDICI_WS_WRITE_SCRIPT
    );
    assert.equal(code, 0, stdout);
    const result = JSON.parse(stdout.trim().split("\n").pop());
    assert.equal(result.error, "VANTIO_GATE_BLOCKED");
    const frames = requests.wsFrames.map((b) => b.toString()).join("");
    assert.equal(frames.includes("hello-ws"), false, "oversized tunnel write must not reach the target");
    const deadline = Date.now() + 1000;
    let sizeEvents = [];
    while (Date.now() < deadline) {
      sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
      if (sizeEvents.length >= 1) break;
      await new Promise((r) => setTimeout(r, 50));
    }
    assert.ok(sizeEvents.length >= 1);
    assert.equal(sizeEvents[0].body.eventPayload.mediation, "undici_ws");
  });

  const HTTP2_ONCE_SCRIPT = `
const http2 = require("http2");
function go() {
  const u = new URL(process.env.H2_URL);
  const client = http2.connect(u.origin);
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    try { client.close(); } catch {}
  };
  client.on("error", (err) => out({ error: err && err.code ? String(err.code) : String(err && err.message || "Error") }));
  const req = client.request({
    ":method": "POST",
    ":path": "/v1/target",
    ":scheme": "http",
    ":authority": u.host,
    "content-type": "application/json",
  });
  let status = 0;
  let body = "";
  req.setEncoding("utf8");
  req.on("response", (headers) => { status = headers[":status"] || 0; });
  req.on("data", (c) => { body += c; });
  req.on("end", () => out({ status, body }));
  req.on("error", (err) => out({ error: err && err.code ? String(err.code) : String(err && err.message || "Error") }));
  req.end(JSON.stringify({ email: "shouldnotleak@example.com", msg: "hi" }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  describe("Node http2.connect / session.request", () => {
    let h2Server;
    let h2Url;

    beforeEach(async () => {
      h2Server = http2.createServer();
      h2Server.on("stream", (stream, headers) => {
        const chunks = [];
        stream.on("data", (c) => chunks.push(Buffer.from(c)));
        stream.on("end", () => {
          requests.target.push({
            headers,
            body: Buffer.concat(chunks).toString("utf8"),
          });
          const payload = JSON.stringify({ reply: "ok" });
          stream.respond({
            ":status": 200,
            "content-type": "application/json",
            "content-length": Buffer.byteLength(payload),
          });
          stream.end(payload);
        });
      });
      await new Promise((resolve) => h2Server.listen(0, "127.0.0.1", resolve));
      h2Url = `http://127.0.0.1:${h2Server.address().port}/v1/target`;
    });

    afterEach(async () => {
      await new Promise((resolve) => h2Server.close(resolve));
    });

    test("PAID_MODE, http2.request redact_pii: email stripped before the call leaves", async () => {
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.redact_pii = true;
      configPolicy.pii_types = ["email"];
      const { code } = await runAgent(
        { H2_URL: h2Url, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        HTTP2_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      assert.equal(requests.target.length, 1);
      assert.doesNotMatch(requests.target[0].body, /shouldnotleak@example\.com/);
      assert.match(requests.target[0].body, /\[VANTIO_REDACTED:EMAIL\]/);
      const redacted = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "REDACTED");
      assert.equal(redacted.length, 1);
    });

    test("PAID_MODE, http2.connect blocked_hosts: session never reaches the target", async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { H2_URL: h2Url, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        HTTP2_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "http2.connect must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    });
  });

  const NET_ONCE_SCRIPT = `
const net = require("net");
function go() {
  const u = new URL(process.env.TCP_URL);
  const sock = net.connect({ host: u.hostname, port: Number(u.port) }, () => {
    process.stdout.write(JSON.stringify({ connected: true }) + "\\n");
    sock.end();
  });
  sock.on("error", (err) => {
    process.stdout.write(JSON.stringify({ error: err && err.code ? String(err.code) : String(err && err.message || "Error") }) + "\\n");
  });
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const TLS_ONCE_SCRIPT = `
const tls = require("tls");
function go() {
  const u = new URL(process.env.TCP_URL);
  const sock = tls.connect({
    host: u.hostname,
    port: Number(u.port),
    servername: u.hostname,
    rejectUnauthorized: false,
  }, () => {
    process.stdout.write(JSON.stringify({ connected: true }) + "\\n");
    sock.end();
  });
  sock.on("error", (err) => {
    process.stdout.write(JSON.stringify({ error: err && err.code ? String(err.code) : String(err && err.message || "Error") }) + "\\n");
  });
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  describe("Node net.connect / tls.connect", () => {
    let tcpServer;
    let tcpUrl;
    let tcpHits;

    beforeEach(async () => {
      tcpHits = 0;
      tcpServer = net.createServer((sock) => {
        tcpHits += 1;
        sock.end();
      });
      await new Promise((resolve) => tcpServer.listen(0, "127.0.0.1", resolve));
      tcpUrl = `http://127.0.0.1:${tcpServer.address().port}/`;
    });

    afterEach(async () => {
      await new Promise((resolve) => tcpServer.close(resolve));
    });

    test("PAID_MODE, net.connect blocked_hosts: TCP never opens", async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TCP_URL: tcpUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        NET_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(tcpHits, 0, "raw net.connect must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
      assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_net");
    });

    test("PAID_MODE, tls.connect blocked_hosts: TCP never opens", async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TCP_URL: tcpUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        TLS_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(tcpHits, 0, "tls.connect must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
      assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_net");
    });

    test("PAID_MODE, net.connect allowed_hosts: ingest ALLOWED once", async () => {
      configPolicy.allowed_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TCP_URL: tcpUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        NET_ONCE_SCRIPT
      );
      assert.equal(code, 0);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.connected, true);
      assert.equal(tcpHits, 1);
      const allowed = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "ALLOWED");
      assert.ok(allowed.length >= 1);
      assert.equal(allowed[0].body.eventPayload.mediation, "node_net");
      assert.ok(allowed[0].body.eventPayload.bytes_observed != null);
    });
  });

  const HAS_CURL = (() => {
    try {
      return spawnSync("curl", ["--version"], { encoding: "utf8", timeout: 3000 }).status === 0;
    } catch {
      return false;
    }
  })();

  const HAS_TIMEOUT = (() => {
    try {
      return spawnSync("timeout", ["--version"], { encoding: "utf8", timeout: 3000 }).status === 0;
    } catch {
      return false;
    }
  })();

  const CURL_SPAWN_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const child = spawn("curl", [
    "-sS", "--max-time", "2", "-X", "POST", "-d", "hello-curl",
    process.env.TARGET_URL,
  ], { stdio: ["ignore", "pipe", "pipe"] });
  let body = "";
  if (child.stdout) child.stdout.on("data", (c) => { body += c; });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code, body }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const CURL_SH_C_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const url = process.env.TARGET_URL;
  const child = spawn("sh", ["-c", "curl -sS --max-time 2 " + JSON.stringify(url)], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const CURL_POST_FILE_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const child = spawn("curl", [
    "-sS", "--max-time", "2", "-X", "POST", "-d", "@" + process.env.POST_FILE,
    process.env.TARGET_URL,
  ], { stdio: ["ignore", "pipe", "pipe"] });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const CURL_TIMEOUT_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const child = spawn("timeout", ["5", "curl", "-sS", "--max-time", "2", process.env.TARGET_URL], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const CURL_K_SCRIPT = `
const { spawn } = require("child_process");
const { writeFileSync } = require("fs");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  writeFileSync(process.env.CURL_CONFIG, "url = " + process.env.TARGET_URL + "\\n");
  const child = spawn("curl", ["-sS", "--max-time", "2", "-K", process.env.CURL_CONFIG], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  describe("Node-spawned curl", () => {
    test("PAID_MODE, spawn curl blocked_hosts: curl never starts", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        CURL_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "blocked curl must never hit the target");
      const curlEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "node_curl");
      assert.ok(curlEvents.length >= 1);
      assert.equal(curlEvents[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    });

    test("PAID_MODE, spawn curl allowed_hosts: ingest node_curl ALLOWED", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      configPolicy.allowed_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        CURL_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.ok, true);
      assert.equal(requests.target.length, 1);
      assert.match(requests.target[0].body, /hello-curl/);
      const curlEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "node_curl");
      assert.equal(curlEvents.length, 1);
      assert.equal(curlEvents[0].body.eventPayload.action_taken, "ALLOWED");
      assert.equal(curlEvents[0].body.eventPayload.bytes_observed, Buffer.byteLength("hello-curl"));
    });

    test("PAID_MODE, sh -c curl blocked_hosts: curl never starts", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        CURL_SH_C_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "sh -c curl must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
      assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_curl");
    });

    test("PAID_MODE, spawn curl -d over max_request_bytes: BLOCKED_SIZE, never hits target", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.max_request_bytes = 4;
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        CURL_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "oversized curl body must not reach the target");
      const deadline = Date.now() + 1000;
      let sizeEvents = [];
      while (Date.now() < deadline) {
        sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
        if (sizeEvents.length >= 1) break;
        await new Promise((r) => setTimeout(r, 50));
      }
      assert.ok(sizeEvents.length >= 1);
      assert.equal(sizeEvents[0].body.eventPayload.mediation, "node_curl");
    });

    test("PAID_MODE, spawn curl -d @file over max_request_bytes: BLOCKED_SIZE, never hits target", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      const dir = mkdtempSync(join(tmpdir(), "vantio-curl-post-file-"));
      const postFile = join(dir, "body.txt");
      writeFileSync(postFile, "hello-post-file");
      configPolicy.enforce = true;
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.max_request_bytes = 4;
      try {
        const { code, stdout } = await runAgent(
          {
            TARGET_URL: targetUrl,
            POST_FILE: postFile,
            VANTIO_API_KEY: "vk_test_dummy",
            VANTIO_INGEST_URL: baseUrl,
          },
          CURL_POST_FILE_SCRIPT
        );
        assert.equal(code, 0, stdout);
        const result = JSON.parse(stdout.trim().split("\n").pop());
        assert.equal(result.error, "VANTIO_GATE_BLOCKED");
        assert.equal(requests.target.length, 0, "oversized curl @file body must not reach the target");
        const deadline = Date.now() + 1000;
        let sizeEvents = [];
        while (Date.now() < deadline) {
          sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
          if (sizeEvents.length >= 1) break;
          await new Promise((r) => setTimeout(r, 50));
        }
        assert.ok(sizeEvents.length >= 1);
        assert.equal(sizeEvents[0].body.eventPayload.mediation, "node_curl");
        assert.equal(sizeEvents[0].body.eventPayload.bytes_observed, Buffer.byteLength("hello-post-file"));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });

    test("PAID_MODE, timeout curl blocked_hosts: curl never starts", { skip: !HAS_CURL || !HAS_TIMEOUT, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        CURL_TIMEOUT_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "timeout curl must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
      assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_curl");
    });

    test("PAID_MODE, curl -K url= blocked_hosts: curl never starts", { skip: !HAS_CURL, timeout: 15000 }, async () => {
      const dir = mkdtempSync(join(tmpdir(), "vantio-curl-k-"));
      const cfg = join(dir, "curl.conf");
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      try {
        const { code, stdout } = await runAgent(
          {
            TARGET_URL: targetUrl,
            CURL_CONFIG: cfg,
            VANTIO_API_KEY: "vk_test_dummy",
            VANTIO_INGEST_URL: baseUrl,
          },
          CURL_K_SCRIPT
        );
        assert.equal(code, 0, stdout);
        const result = JSON.parse(stdout.trim().split("\n").pop());
        assert.equal(result.error, "VANTIO_GATE_BLOCKED");
        assert.equal(requests.target.length, 0, "curl -K must not bypass destination blocking");
        assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
        assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_curl");
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  const HAS_WGET = (() => {
    try {
      return spawnSync("wget", ["--version"], { encoding: "utf8", timeout: 3000 }).status === 0;
    } catch {
      return false;
    }
  })();

  const WGET_SPAWN_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const child = spawn("wget", [
    "-q", "-O", "-", "--timeout=2", "--tries=1",
    "--post-data=hello-wget",
    process.env.TARGET_URL,
  ], { stdio: ["ignore", "pipe", "pipe"] });
  let body = "";
  if (child.stdout) child.stdout.on("data", (c) => { body += c; });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code, body }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const WGET_POST_FILE_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const child = spawn("wget", [
    "-q", "-O", "-", "--timeout=2", "--tries=1",
    "--post-file=" + process.env.POST_FILE,
    process.env.TARGET_URL,
  ], { stdio: ["ignore", "pipe", "pipe"] });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
    body: err && err.message ? String(err.message) : "",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  const WGET_SH_C_SCRIPT = `
const { spawn } = require("child_process");
function go() {
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
    setTimeout(() => process.exit(0), 150);
  };
  const url = process.env.TARGET_URL;
  const child = spawn("sh", ["-c", "wget -q -O - --timeout=2 --tries=1 " + JSON.stringify(url)], {
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.on("error", (err) => out({
    error: err && err.code ? String(err.code) : "Error",
  }));
  child.on("close", (code) => out({ ok: true, code }));
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  describe("Node-spawned wget", () => {
    test("PAID_MODE, spawn wget blocked_hosts: wget never starts", { skip: !HAS_WGET, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WGET_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "blocked wget must never hit the target");
      const wgetEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "node_wget");
      assert.ok(wgetEvents.length >= 1);
      assert.equal(wgetEvents[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    });

    test("PAID_MODE, spawn wget allowed_hosts: ingest node_wget ALLOWED", { skip: !HAS_WGET, timeout: 15000 }, async () => {
      configPolicy.allowed_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WGET_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.ok, true);
      assert.equal(requests.target.length, 1);
      assert.match(requests.target[0].body, /hello-wget/);
      const wgetEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "node_wget");
      assert.equal(wgetEvents.length, 1);
      assert.equal(wgetEvents[0].body.eventPayload.action_taken, "ALLOWED");
      assert.equal(wgetEvents[0].body.eventPayload.bytes_observed, Buffer.byteLength("hello-wget"));
    });

    test("PAID_MODE, sh -c wget blocked_hosts: wget never starts", { skip: !HAS_WGET, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WGET_SH_C_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "sh -c wget must not bypass destination blocking");
      assert.equal(requests.ingest[0].body.eventPayload.action_taken, "BLOCKED_HOST");
      assert.equal(requests.ingest[0].body.eventPayload.mediation, "node_wget");
    });

    test("PAID_MODE, spawn wget --post-data over max_request_bytes: BLOCKED_SIZE, never hits target", { skip: !HAS_WGET, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.max_request_bytes = 4;
      const { code, stdout } = await runAgent(
        { TARGET_URL: targetUrl, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WGET_SPAWN_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "oversized wget body must not reach the target");
      const deadline = Date.now() + 1000;
      let sizeEvents = [];
      while (Date.now() < deadline) {
        sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
        if (sizeEvents.length >= 1) break;
        await new Promise((r) => setTimeout(r, 50));
      }
      assert.ok(sizeEvents.length >= 1);
      assert.equal(sizeEvents[0].body.eventPayload.mediation, "node_wget");
    });

    test("PAID_MODE, spawn wget --post-file over max_request_bytes: BLOCKED_SIZE, never hits target", { skip: !HAS_WGET, timeout: 15000 }, async () => {
      const dir = mkdtempSync(join(tmpdir(), "vantio-wget-post-file-"));
      const postFile = join(dir, "body.txt");
      writeFileSync(postFile, "hello-post-file");
      configPolicy.enforce = true;
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.max_request_bytes = 4;
      try {
        const { code, stdout } = await runAgent(
          {
            TARGET_URL: targetUrl,
            POST_FILE: postFile,
            VANTIO_API_KEY: "vk_test_dummy",
            VANTIO_INGEST_URL: baseUrl,
          },
          WGET_POST_FILE_SCRIPT
        );
        assert.equal(code, 0, stdout);
        const result = JSON.parse(stdout.trim().split("\n").pop());
        assert.equal(result.error, "VANTIO_GATE_BLOCKED");
        assert.equal(requests.target.length, 0, "oversized wget --post-file body must not reach the target");
        const deadline = Date.now() + 1000;
        let sizeEvents = [];
        while (Date.now() < deadline) {
          sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
          if (sizeEvents.length >= 1) break;
          await new Promise((r) => setTimeout(r, 50));
        }
        assert.ok(sizeEvents.length >= 1);
        assert.equal(sizeEvents[0].body.eventPayload.mediation, "node_wget");
        assert.equal(sizeEvents[0].body.eventPayload.bytes_observed, Buffer.byteLength("hello-post-file"));
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    });
  });

  const HAS_WS = (() => {
    if (typeof WebSocket === "function") return true;
    try {
      return typeof require("undici").WebSocket === "function";
    } catch {
      return false;
    }
  })();

  const WS_ONCE_SCRIPT = `
function wsCtor() {
  if (typeof WebSocket === "function") return WebSocket;
  try { return require("undici").WebSocket; } catch { return null; }
}
function go() {
  const Ctor = wsCtor();
  if (!Ctor) {
    process.stdout.write(JSON.stringify({ error: "NO_WEBSOCKET" }) + "\\n");
    return;
  }
  let done = false;
  const out = (obj) => {
    if (done) return;
    done = true;
    process.stdout.write(JSON.stringify(obj) + "\\n");
  };
  try {
    const ws = new Ctor(process.env.WS_URL);
    const timer = setTimeout(() => {
      try { ws.close(); } catch {}
      out({ error: "TIMEOUT" });
    }, 2000);
    ws.addEventListener("open", () => {
      try { ws.send("hello-ws"); } catch (err) {
        clearTimeout(timer);
        out({
          error: err && err.code ? String(err.code) : "Error",
          body: err && err.message ? String(err.message) : "",
        });
        try { ws.close(); } catch {}
        return;
      }
      clearTimeout(timer);
      try { ws.close(); } catch {}
      setTimeout(() => out({ ok: true }), 150);
    });
    ws.addEventListener("error", (ev) => {
      clearTimeout(timer);
      const err = (ev && ev.error) || ev;
      out({
        error: (err && err.code) ? String(err.code) : "Error",
        body: (err && err.message) ? String(err.message) : "",
      });
    });
  } catch (err) {
    out({
      error: err && err.code ? String(err.code) : "Error",
      body: err && err.message ? String(err.message) : "",
    });
  }
}
if (process.env.VANTIO_API_KEY) setTimeout(go, 200);
else go();
`;

  describe("Node WebSocket", () => {
    test("PAID_MODE, WebSocket blocked_hosts: handshake never starts", { skip: !HAS_WS, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.blocked_hosts = ["127.0.0.1"];
      const { code, stdout } = await runAgent(
        { WS_URL: `ws://127.0.0.1:${new URL(baseUrl).port}/v1/ws`, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WS_ONCE_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      assert.equal(requests.target.length, 0, "blocked WebSocket must never reach the target");
      const wsEvents = requests.ingest.filter((r) => r.body?.eventPayload?.mediation === "node_ws");
      assert.ok(wsEvents.length >= 1);
      assert.equal(wsEvents[0].body.eventPayload.action_taken, "BLOCKED_HOST");
    });

    test("PAID_MODE, WebSocket send over max_request_bytes: BLOCKED_SIZE", { skip: !HAS_WS, timeout: 15000 }, async () => {
      configPolicy.enforce = true;
      configPolicy.allowed_hosts = ["127.0.0.1"];
      configPolicy.max_request_bytes = 4;
      const { code, stdout } = await runAgent(
        { WS_URL: `ws://127.0.0.1:${new URL(baseUrl).port}/v1/ws`, VANTIO_API_KEY: "vk_test_dummy", VANTIO_INGEST_URL: baseUrl },
        WS_ONCE_SCRIPT
      );
      assert.equal(code, 0, stdout);
      const result = JSON.parse(stdout.trim().split("\n").pop());
      assert.equal(result.error, "VANTIO_GATE_BLOCKED");
      const deadline = Date.now() + 1000;
      let sizeEvents = [];
      while (Date.now() < deadline) {
        sizeEvents = requests.ingest.filter((r) => r.body?.eventPayload?.action_taken === "BLOCKED_SIZE");
        if (sizeEvents.length >= 1) break;
        await new Promise((r) => setTimeout(r, 50));
      }
      assert.ok(sizeEvents.length >= 1);
      assert.equal(sizeEvents[0].body.eventPayload.mediation, "node_ws");
    });
  });
});
