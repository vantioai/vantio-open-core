// Stage 1 Optics CX: status/outcome split, demo, status, exits, tail, unstable JSON.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, chmodSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";

const require = createRequire(import.meta.url);
const optics = require("../bin/optics-cx.cjs");

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");
const ENFORCEMENT = /BLOCKED|REDACTED|DRY_RUN/;
const STACK = /node:util|ERR_PARSE_ARGS|\n    at /;

function runCli(args, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI_PATH, ...args], {
      env: { PATH: process.env.PATH, HOME: env.HOME, VANTIO_TELEMETRY_DISABLED: "1", ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function writeRun(home, traceId, calls) {
  const dir = join(home, ".vantio", "runs");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const log = {
    vantio_run_log: "1",
    trace_id: traceId,
    cli_version: "0.3.24",
    started_at: "2026-09-26T00:00:00.000Z",
    generated_at: "2026-09-26T00:00:01.000Z",
    calls,
    summary: { total_calls: calls.length, total_bytes: 0, hosts: [] },
  };
  writeFileSync(join(dir, `${traceId}.json`), JSON.stringify(log));
  return join(dir, `${traceId}.json`);
}

function call(status, ok) {
  return {
    hostname: "api.openai.com",
    provider: "openai",
    method: "POST",
    path: "/v1/chat/completions",
    action: "OBSERVED",
    status,
    ok,
    bytes: 8,
    ts: "2026-09-26T00:00:00.000Z",
  };
}

describe("application status ignores stored ok", () => {
  test("HTTP codes map without reading ok", () => {
    assert.equal(optics.applicationStatusFromHttp(200), "SUCCESS");
    assert.equal(optics.applicationStatusFromHttp(401), "APPLICATION_ERROR");
    assert.equal(optics.applicationStatusFromHttp(403), "APPLICATION_ERROR");
    assert.equal(optics.applicationStatusFromHttp(429), "APPLICATION_ERROR");
    assert.equal(optics.applicationStatusFromHttp(500), "APPLICATION_ERROR");
    assert.equal(optics.applicationStatusFromHttp(null), "UNAVAILABLE");
    const lying = optics.displayCall({ status: 500, ok: true, hostname: "api.openai.com" });
    assert.equal(lying.applicationStatus, "APPLICATION_ERROR");
    assert.equal(lying.opticsStatus, "SUCCESS");
    const healthy = optics.displayCall({ status: 200, ok: false });
    assert.equal(healthy.applicationStatus, "SUCCESS");
    assert.equal(optics.rollupCalls([{ status: 200 }, { status: 500 }]).applicationStatus, "PARTIAL");
    assert.equal(optics.humanStatus("SUCCESS"), "Successful");
    assert.equal(optics.humanStatus("APPLICATION_ERROR"), "Application error");
  });
});

describe("vantio demo", () => {
  test("human output is a fixed 200 with both statuses Successful and no content", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-demo-"));
    try {
      const { code, stdout, stderr } = await runCli(["demo"], { HOME: home });
      assert.equal(code, 0, stderr);
      assert.match(stdout, /Vantio Optics \| Free Observability for AI Agents/);
      assert.match(stdout, /POST \/v1\/chat\/completions/);
      assert.match(stdout, /http_status: 200/);
      assert.match(stdout, /Optics status: Successful/);
      assert.match(stdout, /Application outcome: Successful/);
      assert.match(stdout, /duration_ms: 0/);
      assert.match(stdout, /Prompts and completions are never stored/);
      assert.doesNotMatch(stdout, ENFORCEMENT);
      assert.doesNotMatch(stdout, /"content"|sk-|hello world/i);
      assert.doesNotMatch(stderr, ENFORCEMENT);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("demo --json uses unstable schema and SUCCESS tokens", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-demo-json-"));
    try {
      const { code, stdout } = await runCli(["demo", "--json"], { HOME: home });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.schema_status, "unstable-pre-1.0");
      assert.equal(body.method, "POST");
      assert.equal(body.path, "/v1/chat/completions");
      assert.equal(body.httpStatus, 200);
      assert.equal(body.opticsStatus, "SUCCESS");
      assert.equal(body.applicationStatus, "SUCCESS");
      assert.equal(body.duration_ms, 0);
      assert.equal(body.network, "none");
      assert.equal(body.content, null);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("demo performs no network syscalls", () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-demo-strace-"));
    const trace = join(home, "strace.txt");
    try {
      const res = spawnSync("strace", [
        "-f", "-e", "trace=network", "-o", trace,
        process.execPath, CLI_PATH, "demo",
      ], {
        env: { PATH: process.env.PATH, HOME: home, VANTIO_TELEMETRY_DISABLED: "1" },
        encoding: "utf8",
      });
      assert.equal(res.error && res.error.code, undefined, "strace must be installed");
      const text = readFileSync(trace, "utf8");
      assert.equal(res.status, 0, `${res.stderr}\n${text}`);
      assert.doesNotMatch(text, /\b(connect|sendto|sendmsg|recvfrom|recvmsg|getaddrinfo|socket)\(/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});

describe("vantio status", () => {
  test("default path reports install data and does not check the registry", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-status-"));
    const bin = join(home, "bin");
    mkdirSync(bin);
    const npmLog = join(home, "npm-invocations");
    writeFileSync(join(bin, "npm"), `#!/bin/sh\necho called >> "${npmLog}"\necho 9.9.9\n`);
    chmodSync(join(bin, "npm"), 0o755);
    try {
      const { code, stdout, stderr } = await runCli(["status", "--json"], {
        HOME: home,
        PATH: `${bin}:${process.env.PATH}`,
      });
      assert.equal(code, 0, stderr);
      const body = JSON.parse(stdout);
      assert.equal(body.schema_status, "unstable-pre-1.0");
      assert.equal(body.install.version, "0.3.24");
      assert.equal(body.registry.checked, false);
      assert.equal(body.registry.opticsStatus, "NOT_OBSERVED");
      assert.equal(body.telemetry.posture, "disabled");
      assert.equal(body.first_run_since_install, true);
      assert.ok(body.sdks.some((sdk) => sdk.opticsStatus === "UNSUPPORTED"));
      assert.ok(body.vocabulary.includes("PARTIAL"));
      assert.ok(body.vocabulary.includes("OPTICS_ERROR"));
      assert.doesNotMatch(stdout, ENFORCEMENT);
      assert.equal(existsSync(npmLog), false);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("status default performs no network syscalls", () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-status-strace-"));
    const trace = join(home, "strace.txt");
    try {
      const res = spawnSync("strace", [
        "-f", "-e", "trace=network", "-o", trace,
        process.execPath, CLI_PATH, "status",
      ], {
        env: { PATH: process.env.PATH, HOME: home, VANTIO_TELEMETRY_DISABLED: "1" },
        encoding: "utf8",
      });
      const text = readFileSync(trace, "utf8");
      assert.equal(res.status, 0, `${res.stderr}\n${text}`);
      assert.doesNotMatch(text, /\b(connect|sendto|sendmsg|recvfrom|recvmsg|getaddrinfo|socket)\(/);
      assert.match(res.stdout, /not checked/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("--check-registry is opt-in and uses npm", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-status-reg-"));
    const bin = join(home, "bin");
    mkdirSync(bin);
    const npmLog = join(home, "npm-invocations");
    writeFileSync(join(bin, "npm"), `#!/bin/sh\necho called >> "${npmLog}"\necho 0.3.24\n`);
    chmodSync(join(bin, "npm"), 0o755);
    try {
      const { code, stdout } = await runCli(["status", "--check-registry", "--json"], {
        HOME: home,
        PATH: `${bin}:${process.env.PATH}`,
      });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.registry.checked, true);
      assert.equal(body.registry.version, "0.3.24");
      assert.equal(body.registry.opticsStatus, "SUCCESS");
      assert.match(readFileSync(npmLog, "utf8"), /called/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});

describe("stored HTTP fixtures", () => {
  const cases = [
    ["success", 200, true, "SUCCESS", "Successful"],
    ["401", 401, true, "APPLICATION_ERROR", "Application error"],
    ["403", 403, false, "APPLICATION_ERROR", "Application error"],
    ["429", 429, true, "APPLICATION_ERROR", "Application error"],
    ["500", 500, true, "APPLICATION_ERROR", "Application error"],
    ["offline", null, true, "UNAVAILABLE", "Unavailable"],
  ];

  for (const [name, status, ok, token, label] of cases) {
    test(`prove and search show ${name} as ${token} even when ok=${ok}`, async () => {
      const home = mkdtempSync(join(tmpdir(), "vantio-fix-"));
      try {
        writeRun(home, `0x${name}fixture`, [call(status, ok)]);
        const proved = await runCli(["prove", "--run", `0x${name}fixture`, "--json"], { HOME: home });
        assert.equal(proved.code, 0, proved.stderr);
        const body = JSON.parse(proved.stdout);
        assert.equal(body.schema_status, "unstable-pre-1.0");
        assert.equal(body.calls[0].opticsStatus, "SUCCESS");
        assert.equal(body.calls[0].applicationStatus, token);
        assert.equal(body.calls[0].httpStatus, status);
        assert.equal(body.calls[0].ok, undefined);
        const md = await runCli(["prove", "--run", `0x${name}fixture`, "--format=md"], { HOME: home });
        assert.equal(md.code, 0, md.stderr);
        assert.match(md.stdout, /Optics status/);
        assert.match(md.stdout, /Application outcome/);
        assert.match(md.stdout, new RegExp(label));
        assert.doesNotMatch(md.stdout, ENFORCEMENT);
        const searched = await runCli(["search", "--run", `0x${name}fixture`, "openai", "--json"], { HOME: home });
        assert.equal(searched.code, 0, searched.stderr);
        const found = JSON.parse(searched.stdout);
        assert.equal(found.schema_status, "unstable-pre-1.0");
        assert.equal(found.calls[0].applicationStatus, token);
      } finally {
        rmSync(home, { recursive: true, force: true });
      }
    });
  }
});

describe("empty results and usage errors", () => {
  test("a named run that does not exist is an empty result", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-empty-"));
    try {
      for (const args of [
        ["prove", "--run=missing"],
        ["search", "--run=missing", "openai"],
        ["tail", "--run=missing"],
        ["diff", "missing-a", "missing-b"],
        ["discover"],
      ]) {
        const result = await runCli(args, { HOME: home });
        assert.equal(result.code, 0, `${args.join(" ")} ${result.stderr}`);
      }
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("a corrupt run file is exit 1 without a stack", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-corrupt-"));
    const dir = join(home, ".vantio", "runs");
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "0xbroken.json"), "{");
    try {
      for (const args of [
        ["prove", "--run=0xbroken"],
        ["search", "openai"],
        ["tail"],
        ["discover"],
        ["diff", "0xbroken", "0xbroken"],
      ]) {
        const result = await runCli(args, { HOME: home });
        assert.equal(result.code, 1, args.join(" "));
        assert.doesNotMatch(`${result.stdout}\n${result.stderr}`, STACK);
      }
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("ordinary mistakes do not print a Node stack", async () => {
    for (const args of [
      ["prove", "--bogus"],
      ["tail", "--bogus"],
      ["discover", "--bogus"],
      ["search", "--bogus"],
      ["diff", "--bogus"],
    ]) {
      const result = await runCli(args);
      assert.equal(result.code, 1, args.join(" "));
      assert.equal(result.stdout, "");
      assert.doesNotMatch(result.stderr, STACK);
    }
  });
});

describe("tail lines and follow", () => {
  test("-n 0 shows zero calls and --all shows every call", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-tail-n-"));
    try {
      writeRun(home, "0xtailall", [
        call(200, true),
        call(500, true),
        { ...call(401, true), path: "/v1/embeddings" },
      ]);
      const zero = await runCli(["tail", "-n", "0"], { HOME: home });
      assert.equal(zero.code, 0, zero.stderr);
      assert.match(zero.stdout, /showing 0 of 3/);
      assert.doesNotMatch(zero.stdout, /embeddings/);
      const all = await runCli(["tail", "--all"], { HOME: home });
      assert.equal(all.code, 0, all.stderr);
      assert.match(all.stdout, /showing 3 of 3/);
      assert.match(all.stdout, /embeddings/);
      assert.match(all.stdout, /Application error/);
      assert.doesNotMatch(all.stdout, ENFORCEMENT);
      const both = await runCli(["tail", "--all", "-n", "1"], { HOME: home });
      assert.equal(both.code, 1);
      assert.match(both.stderr, /either --all or --lines/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("--json --follow is a hard usage error", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-tail-follow-"));
    try {
      writeRun(home, "0xtailfollow", [call(200, true)]);
      const result = await runCli(["tail", "--json", "--follow"], { HOME: home });
      assert.equal(result.code, 1);
      assert.equal(result.stdout, "");
      assert.match(result.stderr, /--json and --follow cannot be used together/);
      assert.doesNotMatch(result.stderr, STACK);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});

describe("unstable json schema_status", () => {
  test("discover, diff, and run include schema_status", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-schema-"));
    try {
      writeRun(home, "0xschemaa", [call(200, true)]);
      writeRun(home, "0xschemab", [call(500, true)]);
      const discovered = await runCli(["discover", "--json", "--since=30d"], { HOME: home });
      assert.equal(discovered.code, 0, discovered.stderr);
      assert.equal(JSON.parse(discovered.stdout).schema_status, "unstable-pre-1.0");
      const diff = await runCli(["diff", "0xschemaa", "0xschemab", "--json"], { HOME: home });
      assert.equal(diff.code, 0, diff.stderr);
      assert.equal(JSON.parse(diff.stdout).schema_status, "unstable-pre-1.0");
      const run = await runCli(["run", "--json", process.execPath, "-e", "process.exit(0)"], { HOME: home });
      assert.equal(run.code, 0, run.stderr);
      const line = run.stdout.trim().split("\n").filter(Boolean).pop();
      const body = JSON.parse(line);
      assert.equal(body.schema_status, "unstable-pre-1.0");
      assert.equal(body.command, "run");
      assert.equal(body.exit_code, 0);
      assert.equal(body.opticsStatus, "SUCCESS");
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});
