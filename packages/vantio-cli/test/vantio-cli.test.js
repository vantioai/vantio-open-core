// Black-box tests for bin/vantio.js — spawns the real CLI entrypoint exactly
// as a user would invoke it, with HOME redirected to a throwaway temp dir so
// `vantio login`/`logout`/`whoami` never touch a real ~/.vantio.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, rmSync, readFileSync, statSync, mkdirSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");

function scratchRoot() {
  for (const d of [process.env.TMPDIR, tmpdir(), "/tmp"]) {
    if (d && existsSync(d)) return d;
  }
  return "/tmp";
}

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
    assert.match(stdout, /Vantio AI — process supervisor/);
    assert.match(stdout, /vantio login/);
    assert.match(stdout, /vantio discover/);
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
    assert.match(stderr, /Vantio AI — process supervisor/);
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

  test("discover rejects an invalid --since value", async () => {
    const { code, stderr } = await runCli(["discover", "--since=3w"]);
    assert.equal(code, 1);
    assert.match(stderr, /invalid --since value/);
  });

  test("discover --help prints help without requiring a key", async () => {
    const { code, stdout } = await runCli(["discover", "--help"]);
    assert.equal(code, 0);
    assert.match(stdout, /local wrap history, or paid control-plane discover/);
    assert.match(stdout, /not a fleet inventory/);
  });

  test("discover with no stored key tells the user to log in first", async () => {
    const homeDir = mkdtempSync(join(scratchRoot(), "vantio-test-"));
    try {
      const { code, stdout } = await runCli(["discover"], { HOME: homeDir });
      assert.equal(code, 1);
      assert.match(stdout, /Run `vantio login` first/);
    } finally {
      rmSync(homeDir, { recursive: true, force: true });
    }
  });
});

describe("vantio CLI — login / whoami / logout (against a mock control plane)", () => {
  let server, baseUrl, homeDir, tenantTier, configPolicy;

  beforeEach(async () => {
    tenantTier = "ENTERPRISE";
    configPolicy = { enforce: false, redact_pii: false, pii_types: [], allowed_hosts: [], blocked_hosts: [], max_request_bytes: 0, spend_cap_usd: 0 };
    server = http.createServer((req, res) => {
      if (req.url.startsWith("/api/v1/config")) {
        const identity = req.headers["x-vantio-identity"];
        if (identity === "vk_bad_key") {
          res.writeHead(401, { "content-type": "application/json" });
          res.end(JSON.stringify({ error: "Invalid API key." }));
          return;
        }
        const payload = JSON.stringify({ policy: configPolicy, tier: tenantTier });
        res.writeHead(200, { "content-type": "application/json", "content-length": Buffer.byteLength(payload) });
        res.end(payload);
        return;
      }
      res.writeHead(404).end();
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    baseUrl = `http://127.0.0.1:${server.address().port}`;
    homeDir = mkdtempSync(join(scratchRoot(), "vantio-test-"));
  });

  afterEach(async () => {
    await new Promise((resolve) => server.close(resolve));
    rmSync(homeDir, { recursive: true, force: true });
  });

  test("login with a valid paid key saves config with 0600 permissions and no upgrade nudge", async () => {
    const { code, stdout } = await runCli(
      ["login", "vk_good_key"],
      { HOME: homeDir, VANTIO_INGEST_URL: baseUrl }
    );
    assert.equal(code, 0);
    assert.match(stdout, /Connected to Vantio/);
    assert.doesNotMatch(stdout, /Free plan/);

    const cfgPath = join(homeDir, ".vantio", "config.json");
    const saved = JSON.parse(readFileSync(cfgPath, "utf8"));
    assert.equal(saved.apiKey, "vk_good_key");
    assert.equal(saved.ingestUrl, baseUrl);

    const mode = statSync(cfgPath).mode & 0o777;
    assert.equal(mode, 0o600);
  });

  test("login with a free-tier key succeeds but honestly warns about dashboard sync", async () => {
    tenantTier = "FREE";
    const { code, stdout } = await runCli(
      ["login", "vk_free_key"],
      { HOME: homeDir, VANTIO_INGEST_URL: baseUrl }
    );
    assert.equal(code, 0);
    assert.match(stdout, /Connected to Vantio/);
    assert.match(stdout, /Free plan/);
    assert.match(stdout, /vantio\.ai\/pricing/);
  });

  test("login with an invalid key exits 1 and does not save anything", async () => {
    const { code, stderr } = await runCli(
      ["login", "vk_bad_key"],
      { HOME: homeDir, VANTIO_INGEST_URL: baseUrl }
    );
    assert.equal(code, 1);
    assert.match(stderr, /rejected/);
    assert.throws(() => readFileSync(join(homeDir, ".vantio", "config.json")));
  });

  test("login with no key and no TTY input exits 1", async () => {
    const { code, stderr } = await runCli(["login"], { HOME: homeDir, VANTIO_INGEST_URL: baseUrl });
    assert.equal(code, 1);
    assert.match(stderr, /no API key provided/);
  });

  test("whoami reflects the saved key's tier and masks the key", async () => {
    await runCli(["login", "vk_paid_1234567890"], { HOME: homeDir, VANTIO_INGEST_URL: baseUrl });
    const { code, stdout } = await runCli(["whoami"], { HOME: homeDir });
    assert.equal(code, 0);
    assert.match(stdout, /connected/);
    assert.doesNotMatch(stdout, /vk_paid_1234567890/);
    assert.match(stdout, /vk_pai…7890/);
  });

  test("whoami with no stored key says so", async () => {
    const { code, stdout } = await runCli(["whoami"], { HOME: homeDir });
    assert.equal(code, 0);
    assert.match(stdout, /Not logged in/);
  });

  test("logout removes the stored key", async () => {
    await runCli(["login", "vk_good_key"], { HOME: homeDir, VANTIO_INGEST_URL: baseUrl });
    const { code, stdout } = await runCli(["logout"], { HOME: homeDir });
    assert.equal(code, 0);
    assert.match(stdout, /Logged out/);
    assert.throws(() => readFileSync(join(homeDir, ".vantio", "config.json")));
  });

  test("logout with nothing stored says so instead of erroring", async () => {
    const { code, stdout } = await runCli(["logout"], { HOME: homeDir });
    assert.equal(code, 0);
    assert.match(stdout, /No stored credentials/);
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

describe("vantio coverage / doctor / leave (Optics P0)", () => {
  test("coverage --help and top-level usage list the new commands", async () => {
    const help = await runCli(["coverage", "--help"]);
    assert.equal(help.code, 0);
    assert.match(help.stdout, /this machine/i);
    assert.match(help.stdout, /never fleet/i);
    const usage = await runCli([]);
    assert.equal(usage.code, 0);
    assert.match(usage.stdout, /vantio coverage/);
    assert.match(usage.stdout, /vantio doctor/);
    assert.match(usage.stdout, /vantio leave/);
  });

  test("coverage --json on an empty home is idle, not 100% covered", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-coverage-idle-"));
    try {
      const { code, stdout } = await runCli(["coverage", "--json"], { HOME: home, VANTIO_HOME: join(home, ".vantio") });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.coverage_state, "idle");
      assert.equal(body.this_machine_only, true);
      assert.equal(body.not_fleet, true);
      assert.equal(body.not_universal_discovery, true);
      assert.ok(Array.isArray(body.unsupported_paths));
      assert.ok(body.unsupported_paths.length >= 4);
      assert.doesNotMatch(stdout, /100%/);
      assert.match(JSON.stringify(body.unsupported_paths), /sdk_skip|curl|browser/i);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("coverage --json names attached after a local wrap log exists", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-coverage-live-"));
    try {
      const vantioHome = join(home, ".vantio");
      const runs = join(vantioHome, "runs");
      mkdirSync(runs, { recursive: true, mode: 0o700 });
      writeFileSync(join(runs, "0xopticsp0cover01.json"), JSON.stringify({
        vantio_run_log: "1",
        schema_version: 2,
        trace_id: "0xopticsp0cover01",
        generated_at: new Date().toISOString(),
        calls: [{ hostname: "api.openai.com", action: "OBSERVED", bytes: 12 }],
        summary: { total_calls: 1, degraded: false },
      }, null, 2));
      const { code, stdout } = await runCli(["coverage", "--json"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.coverage_state, "attached");
      assert.ok(body.hosts.includes("api.openai.com"));
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("coverage --json names degraded when a wrap log is incomplete", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-coverage-degraded-"));
    try {
      const vantioHome = join(home, ".vantio");
      const runs = join(vantioHome, "runs");
      mkdirSync(runs, { recursive: true, mode: 0o700 });
      writeFileSync(join(runs, "0xopticsp0degraded.json"), JSON.stringify({
        vantio_run_log: "1",
        schema_version: 2,
        trace_id: "0xopticsp0degraded",
        generated_at: new Date().toISOString(),
        calls: [{ hostname: "api.openai.com", action: "ENFORCEMENT_GAP", gap_type: "unscanned_body", observation_incomplete: "unscanned_body" }],
        summary: { total_calls: 1, degraded: true },
      }, null, 2));
      const { code, stdout } = await runCli(["coverage", "--json"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.coverage_state, "degraded");
      assert.equal(body.degraded, true);
      assert.ok(Array.isArray(body.unsupported_paths) && body.unsupported_paths.length >= 4);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("doctor --json does not invent OBSERVED and names the Python SDK miss", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-doctor-"));
    try {
      const { code, stdout } = await runCli(["doctor", "--json"], { HOME: home, VANTIO_HOME: join(home, ".vantio") });
      assert.equal(code, 0);
      const body = JSON.parse(stdout);
      assert.equal(body.interceptor_present, true);
      assert.equal(body.note.includes("does not emit OBSERVED") || body.note.includes("does not start a generator"), true);
      assert.ok(["importable", "missing"].includes(body.python_sdk));
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("leave refuses delete without --yes and deletes metadata with --yes", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-leave-"));
    try {
      const vantioHome = join(home, ".vantio");
      const runs = join(vantioHome, "runs");
      mkdirSync(runs, { recursive: true });
      writeFileSync(join(runs, "keep.json"), "{\"vantio_run_log\":\"1\",\"calls\":[]}\n");
      const refused = await runCli(["leave", "--delete-local-metadata"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(refused.code, 1);
      assert.match(refused.stderr, /--yes/);
      const ok = await runCli(["leave", "--delete-local-metadata", "--yes"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(ok.code, 0);
      assert.match(ok.stdout, /not a prompt warehouse|Prompts were not stored/i);
      assert.equal(existsSync(runs), false);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("discover --local empty copy does not claim fleet coverage", async () => {
    const home = mkdtempSync(join(scratchRoot(), "vantio-discover-local-"));
    try {
      const { code, stdout } = await runCli(["discover", "--local"], { HOME: home, VANTIO_HOME: join(home, ".vantio") });
      assert.equal(code, 0);
      assert.match(stdout, /this machine/i);
      assert.doesNotMatch(stdout, /kernel-level shadow AI/i);
      assert.doesNotMatch(stdout, /eBPF/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});
