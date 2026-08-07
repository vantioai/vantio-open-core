// Black-box tests for bin/vantio.js — spawns the real CLI entrypoint exactly
// as a user would invoke it, with HOME redirected to a throwaway temp dir so
// `vantio login`/`logout`/`whoami` never touch a real ~/.vantio.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, rmSync, readFileSync, statSync } from "node:fs";
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
    assert.match(stdout, /Shadow AI Attack Surface Discovery/);
  });

  test("discover with no stored key tells the user to log in first", async () => {
    const homeDir = mkdtempSync(join(tmpdir(), "vantio-test-"));
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
    homeDir = mkdtempSync(join(tmpdir(), "vantio-test-"));
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
