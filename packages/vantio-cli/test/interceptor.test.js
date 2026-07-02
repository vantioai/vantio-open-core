// Integration tests for bin/interceptor.cjs, run exactly the way it runs in
// production: as a --require hook in a fresh child Node process. This is
// deliberately black-box (no refactoring of the security-critical redaction/
// enforcement logic to make it more "testable") — it drives the real file
// through a local mock control-plane + target server and asserts on what
// actually crossed the wire.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
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
      { env: { PATH: process.env.PATH, ...env }, stdio: ["ignore", "pipe", "pipe"] }
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

describe("interceptor.cjs (integration)", () => {
  let server, baseUrl, targetUrl, configPolicy, configTier, requests;

  beforeEach(async () => {
    requests = { config: [], ingest: [], target: [] };
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
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    baseUrl = `http://127.0.0.1:${server.address().port}`;
    targetUrl = `${baseUrl}/v1/target`;
  });

  afterEach(async () => {
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
});
