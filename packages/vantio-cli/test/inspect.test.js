// Tests for vantio search / tail / diff — local run-log inspect (Free Optics).
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");

function runCli(args, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI_PATH, ...args], {
      env: { PATH: process.env.PATH, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function writeRun(home, traceId, calls, overrides = {}) {
  const dir = join(home, ".vantio", "runs");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const hosts = [...new Set(calls.map((c) => c.hostname).filter(Boolean))];
  const by_host = {};
  for (const c of calls) {
    const h = c.hostname || "unknown";
    by_host[h] = by_host[h] || { calls: 0, bytes: 0 };
    by_host[h].calls += 1;
    by_host[h].bytes += c.bytes || 0;
  }
  const log = {
    vantio_run_log: "1",
    schema_version: 2,
    plane: "optics",
    workflow: "sight_loop",
    trace_id: traceId,
    started_at: overrides.started_at || "2026-08-15T12:00:00.000Z",
    generated_at: overrides.generated_at || "2026-08-15T12:01:00.000Z",
    calls,
    summary: {
      total_calls: calls.length,
      total_bytes: calls.reduce((a, c) => a + (c.bytes || 0), 0),
      hosts,
      by_host,
    },
  };
  writeFileSync(join(dir, `${traceId}.json`), JSON.stringify(log, null, 2));
}

describe("vantio inspect — search / tail / diff", () => {
  let homeDir;

  beforeEach(() => {
    homeDir = mkdtempSync(join(tmpdir(), "vantio-inspect-"));
    writeRun(homeDir, "0xaaa111inspect01", [
      {
        hostname: "api.openai.com",
        provider: "openai",
        method: "POST",
        path: "/v1/chat/completions",
        action: "OBSERVED",
        bytes: 1200,
        ts: "2026-08-15T12:00:10.000Z",
      },
      {
        hostname: "api.anthropic.com",
        provider: "anthropic",
        method: "POST",
        path: "/v1/messages",
        action: "OBSERVED",
        bytes: 800,
        ts: "2026-08-15T12:00:20.000Z",
      },
    ]);
    writeRun(homeDir, "0xbbb222inspect02", [
      {
        hostname: "api.openai.com",
        provider: "openai",
        method: "POST",
        path: "/v1/chat/completions",
        action: "OBSERVED",
        bytes: 1500,
        ts: "2026-08-15T13:00:10.000Z",
      },
      {
        hostname: "api.openai.com",
        provider: "openai",
        method: "POST",
        path: "/v1/embeddings",
        action: "OBSERVED",
        bytes: 400,
        ts: "2026-08-15T13:00:15.000Z",
      },
      {
        hostname: "generativelanguage.googleapis.com",
        provider: "google",
        method: "POST",
        path: "/v1beta/models",
        action: "OBSERVED",
        bytes: 600,
        ts: "2026-08-15T13:00:30.000Z",
      },
    ], {
      started_at: "2026-08-15T13:00:00.000Z",
      generated_at: "2026-08-15T13:01:00.000Z",
    });
  });

  afterEach(() => {
    rmSync(homeDir, { recursive: true, force: true });
  });

  test("search --help and top-level usage list inspect commands", async () => {
    const help = await runCli(["search", "--help"], { HOME: homeDir });
    assert.equal(help.code, 0);
    assert.match(help.stdout, /vantio search/);
    assert.match(help.stdout, /--host=/);

    const usage = await runCli([], { HOME: homeDir });
    assert.equal(usage.code, 0);
    assert.match(usage.stdout, /vantio search/);
    assert.match(usage.stdout, /vantio tail/);
    assert.match(usage.stdout, /vantio diff/);
  });

  test("search finds calls by free text and --host", async () => {
    const byText = await runCli(["search", "anthropic", "--json"], { HOME: homeDir });
    assert.equal(byText.code, 0);
    const textJson = JSON.parse(byText.stdout);
    assert.equal(textJson.matches, 1);
    assert.equal(textJson.calls[0].hostname, "api.anthropic.com");

    const byHost = await runCli(["search", "--host=openai", "--json"], { HOME: homeDir });
    assert.equal(byHost.code, 0);
    const hostJson = JSON.parse(byHost.stdout);
    assert.equal(hostJson.matches, 3);
  });

  test("tail shows latest calls from the most recent run", async () => {
    const { code, stdout, stderr } = await runCli(["tail", "-n", "2", "--json"], { HOME: homeDir });
    assert.equal(code, 0);
    assert.match(stderr, /0xbbb222inspect02/);
    const body = JSON.parse(stdout);
    assert.equal(body.trace_id, "0xbbb222inspect02");
    assert.equal(body.shown, 2);
    assert.equal(body.total_calls, 3);
  });

  test("diff reports hosts added/removed and call deltas", async () => {
    const { code, stdout } = await runCli(
      ["diff", "0xaaa111", "0xbbb222", "--json"],
      { HOME: homeDir },
    );
    assert.equal(code, 0);
    const body = JSON.parse(stdout);
    assert.equal(body.a.trace_id, "0xaaa111inspect01");
    assert.equal(body.b.trace_id, "0xbbb222inspect02");
    assert.equal(body.delta_calls, 1);
    assert.ok(body.hosts_added.includes("generativelanguage.googleapis.com"));
    assert.ok(body.hosts_removed.includes("api.anthropic.com"));
    const openai = body.hosts_changed.find((h) => h.host === "api.openai.com");
    assert.ok(openai);
    assert.equal(openai.delta_calls, 1);
  });

  test("tail --help and diff --help print without needing runs", async () => {
    const empty = mkdtempSync(join(tmpdir(), "vantio-inspect-empty-"));
    try {
      const t = await runCli(["tail", "--help"], { HOME: empty });
      assert.equal(t.code, 0);
      assert.match(t.stdout, /vantio tail/);
      const d = await runCli(["diff", "--help"], { HOME: empty });
      assert.equal(d.code, 0);
      assert.match(d.stdout, /vantio diff/);
    } finally {
      rmSync(empty, { recursive: true, force: true });
    }
  });
});
