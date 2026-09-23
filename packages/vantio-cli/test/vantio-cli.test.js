// Black-box tests for bin/vantio.js — spawns the real CLI entrypoint exactly
// as a user would invoke it, with HOME redirected to a throwaway temp dir so
// HOME is redirected to a throwaway temp dir so tests never touch a real ~/.vantio.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, rmSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");

function runCli(args, env = {}, input = null) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI_PATH, ...args], {
      env: { PATH: process.env.PATH, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => (stdout += c));
    child.stderr.on("data", (c) => (stderr += c));
    child.on("close", (code) => resolve({ code, stdout, stderr }));
    if (input !== null) child.stdin.write(input);
    child.stdin.end();
  });
}

describe("vantio CLI — basic dispatch", () => {
  test("no command prints usage and exits 0", async () => {
    const { code, stdout } = await runCli([]);
    assert.equal(code, 0);
    assert.match(stdout, /Vantio Optics \| Free Observability for AI Agents/);
    assert.doesNotMatch(stdout, /login|whoami|logout/i);
    assert.match(stdout, /vantio discover/);
  });

  test("--audit flag is not advertised in primary help (METADATA_ONLY)", async () => {
    const { code, stdout } = await runCli([]);
    assert.equal(code, 0);
    assert.doesNotMatch(stdout, /--audit/, "--audit must not appear in public help text");
  });

  test("--audit flag is not advertised in run --help error (METADATA_ONLY)", async () => {
    const { code, stderr } = await runCli(["run"]);
    assert.equal(code, 1);
    assert.doesNotMatch(stderr, /--audit/, "--audit must not appear in run usage error");
  });

  test("--version prints the version from package.json", async () => {
    const { code, stdout } = await runCli(["--version"]);
    assert.equal(code, 0);
    const pkg = JSON.parse(readFileSync(join(__dirname, "..", "package.json"), "utf8"));
    assert.equal(stdout.trim(), pkg.version);
  });

  test("unknown command exits 1 and prints usage to stderr", async () => {
    const { code, stderr } = await runCli(["frobnicate"]);
    assert.equal(code, 1);
    assert.match(stderr, /unknown command 'frobnicate'/);
    assert.match(stderr, /Vantio Optics \| Free Observability for AI Agents/);
  });

  test("run with no program exits 1", async () => {
    const { code, stderr } = await runCli(["run"]);
    assert.equal(code, 1);
    assert.match(stderr, /no program specified/);
  });

  test("run actually spawns the given program and forwards its exit code", async () => {
    const { code, stdout } = await runCli(["run", "node", "-e", "console.log('hello-from-child'); process.exit(7)"]);
    assert.equal(code, 7);
    assert.match(stdout, /hello-from-child/);
  });

  test("run writes a run log even when the child makes zero LLM calls", async () => {
    const homeDir = mkdtempSync(join(tmpdir(), "vantio-test-zero-"));
    try {
      const { code } = await runCli(
        ["run", "node", "-e", "process.exit(0)"],
        { HOME: homeDir },
      );
      assert.equal(code, 0);
      const runsDir = join(homeDir, ".vantio", "runs");
      const logs = readdirSync(runsDir).filter((f) => f.endsWith(".json"));
      assert.equal(logs.length, 1, "expected exactly one run log for a zero-call run");
      const log = JSON.parse(readFileSync(join(runsDir, logs[0]), "utf8"));
      assert.equal(log.vantio_run_log, "1");
      assert.equal(log.summary.total_calls, 0);
      assert.ok(Array.isArray(log.calls) && log.calls.length === 0);
    } finally {
      rmSync(homeDir, { recursive: true, force: true });
    }
  });

  test("discover rejects an invalid --since value", async () => {
    const { code, stderr } = await runCli(["discover", "--since=3w"]);
    assert.equal(code, 1);
    assert.match(stderr, /invalid --since value/);
  });

  test("discover --help prints help without requiring a key", async () => {
    const { code, stdout } = await runCli(["discover", "--help"]);
    assert.equal(code, 0);
    assert.match(stdout, /vantio discover.*AI-agent call history/s);
  });

  test("discover with no config stays local and does not ask for a login", async () => {
    const homeDir = mkdtempSync(join(tmpdir(), "vantio-test-"));
    try {
      const { code, stdout, stderr } = await runCli(["discover"], { HOME: homeDir });
      assert.equal(code, 0);
      assert.match(stdout, /local run history/);
      assert.doesNotMatch(`${stdout}\n${stderr}`, /login|whoami|dashboard|pricing/i);
    } finally {
      rmSync(homeDir, { recursive: true, force: true });
    }
  });
});

describe("vantio run python wrap", () => {
  test("injects python-wrap onto PYTHONPATH for python3", async () => {
    const { code, stdout, stderr } = await runCli([
      "run",
      "python3",
      "-c",
      "import sys; print('WRAP_OK' if any('python-wrap' in p for p in sys.path) else 'WRAP_MISSING')",
    ]);
    if (code === 127 || /failed to start/.test(stderr)) {
      return; // python3 not on PATH in this environment
    }
    assert.equal(code, 0);
    assert.match(stdout, /WRAP_OK/);
  });
});
