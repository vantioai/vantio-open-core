import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { listRunLogs, loadRun, proveMarkdown, discoverLocal, UPGRADE_PATH } from "../src/runs.js";

test("list/load/prove/discover from fixture runs dir", () => {
  const root = mkdtempSync(join(tmpdir(), "vantio-optics-mcp-"));
  const dir = join(root, "runs");
  mkdirSync(dir, { recursive: true });

  const log = {
    vantio_run_log: "1",
    trace_id: "0xabcoptics01",
    pid: 42,
    machine: "test",
    started_at: "2026-07-17T00:00:00.000Z",
    generated_at: "2026-07-17T00:00:01.000Z",
    duration_ms: 1000,
    cli_version: "0.3.0",
    calls: [
      { hostname: "api.openai.com", action: "OBSERVED", bytes: 1200, ts: "2026-07-17T00:00:00.500Z" },
      { hostname: "api.anthropic.com", action: "OBSERVED", bytes: 800, ts: "2026-07-17T00:00:00.800Z" },
    ],
    summary: {
      total_calls: 2,
      total_bytes: 2000,
      hosts: ["api.openai.com", "api.anthropic.com"],
      redacted: 0,
      blocked: 0,
    },
  };
  writeFileSync(join(dir, "0xabcoptics01.json"), JSON.stringify(log, null, 2));

  const listed = listRunLogs(dir);
  assert.equal(listed.length, 1);
  assert.equal(listed[0].trace_id, "0xabcoptics01");

  const loaded = loadRun("0xabc", dir);
  assert.ok(loaded.log);
  assert.equal(loaded.log.trace_id, "0xabcoptics01");

  const md = proveMarkdown(loaded.log);
  assert.match(md, /Vantio Optics/);
  assert.match(md, /api\.openai\.com/);
  assert.match(md, /metadata only|No prompts or completions/i);
  assert.match(md, /Developer egress data log|Traffic metadata only/i);
  assert.doesNotMatch(md, /"role"\s*:\s*"user"|completion_tokens/);

  const hosts = discoverLocal(30 * 24 * 60 * 60 * 1000, dir);
  assert.equal(hosts.length, 2);
  assert.equal(UPGRADE_PATH.next[0].brand, "Vantio Gate");
  assert.match(UPGRADE_PATH.fence, /read-only/i);

  rmSync(root, { recursive: true, force: true });
});
