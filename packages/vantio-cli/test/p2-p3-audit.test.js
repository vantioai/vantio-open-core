import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseIngestUrl } from "../bin/ingest-url.cjs";

const root = dirname(fileURLToPath(import.meta.url));
const cli = join(root, "..", "bin", "vantio.js");
const interceptor = join(root, "..", "bin", "interceptor.cjs");

test("a bad VANTIO_INGEST_URL is not treated as the public host", () => {
  const parsed = parseIngestUrl("not a url");
  assert.equal(parsed.ok, false);
  assert.equal(parseIngestUrl("ftp://files.example/x").ok, false);
  assert.equal(parseIngestUrl("https://vantio.ai").publicHost, true);
  assert.equal(parseIngestUrl("http://127.0.0.1:9").publicHost, false);
});

test("a bad ingest URL with an API key fails closed out loud", async () => {
  const script = `
    const http = require("node:http");
    const srv = http.createServer((req, res) => {
      res.writeHead(200, { "content-type": "application/json" });
      res.end('{"ok":true}');
    });
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      fetch("http://127.0.0.1:" + port + "/v1/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: '{"n":1}',
      }).then(async (res) => {
        const body = await res.text();
        process.stdout.write(JSON.stringify({ status: res.status, body }));
        srv.close();
      }).catch((err) => {
        process.stdout.write(JSON.stringify({ error: err.message }));
        srv.close();
      });
    });
  `;
  const child = spawn(process.execPath, ["-e", script], {
    env: {
      PATH: process.env.PATH,
      NODE_OPTIONS: `--require ${interceptor}`,
      VANTIO_INGEST_URL: "not a url",
      VANTIO_API_KEY: "vk_test_dummy",
      VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (c) => (stdout += c));
  child.stderr.on("data", (c) => (stderr += c));
  const code = await new Promise((resolve) => child.on("close", resolve));
  assert.equal(code, 0);
  assert.match(stderr, /VANTIO_INGEST_URL/);
  assert.match(stderr, /fails closed|ENFORCEMENT_CLOSED/i);
  const body = JSON.parse(stdout.trim().split("\n").pop());
  assert.equal(body.status, 403);
  assert.match(body.body, /enforcement_closed/);
});

test("CLI readers use VANTIO_HOME", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-home-"));
  const other = mkdtempSync(join(tmpdir(), "vantio-other-"));
  const runs = join(home, "runs");
  mkdirSync(runs, { recursive: true });
  writeFileSync(join(runs, "trace-home.json"), JSON.stringify({
    vantio_run_log: "1",
    trace_id: "trace-home-only",
    generated_at: "2026-09-29T00:00:00.000Z",
    calls: [{ hostname: "api.openai.com", action: "OBSERVED", bytes: 3 }],
  }));
  const child = spawn(process.execPath, [cli, "prove", "--list"], {
    env: { PATH: process.env.PATH, HOME: other, VANTIO_HOME: home },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let stdout = "";
  child.stdout.on("data", (c) => (stdout += c));
  const code = await new Promise((resolve) => child.on("close", resolve));
  rmSync(home, { recursive: true, force: true });
  rmSync(other, { recursive: true, force: true });
  assert.equal(code, 0);
  assert.match(stdout, /trace-home-only/);
});
