// Account retirement. Public surfaces stay local. Synthetic
// values only — never a real credential.
import { test, describe } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");
const INTERCEPTOR_PATH = join(__dirname, "..", "bin", "interceptor.cjs");
const README_PATH = join(__dirname, "..", "README.md");
const PKG_PATH = join(__dirname, "..", "package.json");

const ACCOUNT_PROMISE = /vantio login|vantio whoami|vantio logout|\btrial key\b|dashboard sync|Stripe|Checkout|\/api\/v1\/config|\/api\/v1\/ingest|VANTIO_API_KEY|Free \/ Pro|Shadow AI|Sight Loop|\beBPF\b/i;
const LADDER = /\bPro\b|\bEnterprise\b|Free plan|\/pricing/;
const HIDDEN_COMMAND = /\blogin\b|\bwhoami\b|\blogout\b/i;

function runCli(args, env = {}) {
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
    child.stdin.end();
  });
}

function runNode(script, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ["-e", script], {
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

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

describe("public surfaces do not advertise accounts", () => {
  test("primary help is the approved identity and has no account commands", async () => {
    const { code, stdout } = await runCli([]);
    assert.equal(code, 0);
    assert.match(stdout, /Vantio Optics \| Free Observability for AI Agents/);
    assert.match(stdout, /Free, local-first observability for supported AI-agent traffic\. Prompts and completions are never stored\./);
    assert.doesNotMatch(stdout, ACCOUNT_PROMISE);
    assert.doesNotMatch(stdout, LADDER);
    assert.doesNotMatch(stdout, HIDDEN_COMMAND);
  });

  test("command help and usage errors do not promote accounts", async () => {
    const cases = [
      ["discover", "--help"],
      ["prove", "--help"],
      ["search", "--help"],
      ["tail", "--help"],
      ["diff", "--help"],
      ["run"],
      ["run", "--help"],
      ["search"],
      ["frobnicate"],
    ];
    for (const args of cases) {
      const { stdout, stderr } = await runCli(args);
      const text = `${stdout}\n${stderr}`;
      assert.doesNotMatch(text, ACCOUNT_PROMISE, args.join(" "));
      assert.doesNotMatch(text, LADDER, args.join(" "));
      assert.doesNotMatch(text, HIDDEN_COMMAND, args.join(" "));
    }
    for (const cmd of ["login", "whoami"]) {
      const { code, stderr, stdout } = await runCli([cmd]);
      assert.equal(code, 1);
      assert.match(stderr, new RegExp(`unknown command '${cmd}'`));
      const usage = stderr.replace(`unknown command '${cmd}'`, "");
      assert.doesNotMatch(`${stdout}\n${usage}`, HIDDEN_COMMAND);
    }
  });

  test("README and package metadata do not promise accounts, billing, or the missing config route", () => {
    const readme = readFileSync(README_PATH, "utf8");
    const pkg = JSON.parse(readFileSync(PKG_PATH, "utf8"));
    assert.equal(pkg.version, "0.3.23");
    assert.equal(pkg.license, "MIT");
    assert.ok(pkg.files.includes("README.md"));
    assert.ok(pkg.files.includes("LICENSE"));
    const rootLicense = readFileSync(join(__dirname, "..", "..", "..", "LICENSE"));
    const packedLicense = readFileSync(join(__dirname, "..", "LICENSE"));
    assert.deepEqual(packedLicense, rootLicense);
    assert.equal(packedLicense.includes("Copyright (c) 2026 Vantio AI, Inc."), true);
    assert.match(pkg.description, /Vantio Optics \| Free Observability for AI Agents/);
    assert.match(pkg.description, /Free, local-first observability for supported AI-agent traffic\. Prompts and completions are never stored\./);
    assert.doesNotMatch(readme, ACCOUNT_PROMISE);
    assert.doesNotMatch(pkg.description, ACCOUNT_PROMISE);
    assert.doesNotMatch(JSON.stringify(pkg.keywords), ACCOUNT_PROMISE);
    const cli = readFileSync(CLI_PATH, "utf8");
    assert.doesNotMatch(cli, /\/api\/v1\/config/);
    assert.doesNotMatch(cli, /\/api\/v1\/ingest/);
    assert.doesNotMatch(cli, /\/api\/v1\/discover/);
  });
});

describe("retired commands and stored config", () => {
  test("login and whoami are not dispatched and do not contact a server", async () => {
    const hits = [];
    const server = await listen((req, res) => {
      hits.push(req.url);
      res.writeHead(200, { "content-type": "application/json" });
      res.end("{}");
    });
    const home = mkdtempSync(join(tmpdir(), "vantio-retired-"));
    const base = `http://127.0.0.1:${server.address().port}`;
    try {
      for (const cmd of ["login", "whoami"]) {
        const { code, stderr } = await runCli([cmd, "vk_synthetic_not_a_real_key"], {
          HOME: home,
          VANTIO_INGEST_URL: base,
        });
        assert.equal(code, 1, cmd);
        assert.match(stderr, new RegExp(`unknown command '${cmd}'`));
      }
      assert.equal(hits.length, 0);
    } finally {
      await new Promise((resolve) => server.close(resolve));
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("logout deletes a legacy config locally and does not call the network or print the key", async () => {
    const hits = [];
    const server = await listen((req, res) => {
      hits.push(req.url);
      res.writeHead(200).end();
    });
    const home = mkdtempSync(join(tmpdir(), "vantio-logout-"));
    const cfg = join(home, ".vantio", "config.json");
    const canary = "vk_synthetic_canary_do_not_print";
    try {
      mkdirSync(join(home, ".vantio"), { recursive: true });
      writeFileSync(cfg, JSON.stringify({ apiKey: canary, ingestUrl: `http://127.0.0.1:${server.address().port}` }));
      const { code, stdout, stderr } = await runCli(["logout"], {
        HOME: home,
        VANTIO_INGEST_URL: `http://127.0.0.1:${server.address().port}`,
      });
      assert.equal(code, 0);
      assert.match(stdout, /Vantio Optics \| Free Observability for AI Agents/);
      assert.doesNotMatch(`${stdout}\n${stderr}`, /key|credential|login|dashboard|pricing/i);
      assert.doesNotMatch(`${stdout}\n${stderr}`, new RegExp(canary));
      assert.throws(() => readFileSync(cfg));
      assert.equal(hits.length, 0);
      const again = await runCli(["logout"], { HOME: home });
      assert.equal(again.code, 0);
      assert.match(again.stdout, /Prompts and completions are never stored/);
    } finally {
      await new Promise((resolve) => server.close(resolve));
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("ordinary run ignores a legacy config and does not call config or ingest", async () => {
    const hits = [];
    const server = await listen((req, res) => {
      hits.push(req.url || "");
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ policy: { enforce: true }, tier: "ENTERPRISE" }));
    });
    const home = mkdtempSync(join(tmpdir(), "vantio-legacy-"));
    const canary = "vk_synthetic_legacy_canary";
    try {
      mkdirSync(join(home, ".vantio"), { recursive: true });
      writeFileSync(
        join(home, ".vantio", "config.json"),
        JSON.stringify({ apiKey: canary, ingestUrl: `http://127.0.0.1:${server.address().port}` }),
      );
      const { code, stdout, stderr } = await runCli(
        ["run", "node", "-e", "process.stdout.write(process.env.VANTIO_API_KEY || 'NO_KEY')"],
        { HOME: home },
      );
      assert.equal(code, 0);
      assert.match(stdout, /NO_KEY/);
      assert.doesNotMatch(`${stdout}\n${stderr}`, new RegExp(canary));
      assert.equal(hits.length, 0);
    } finally {
      await new Promise((resolve) => server.close(resolve));
      rmSync(home, { recursive: true, force: true });
    }
  });
});

describe("local observe does not use the public cloud routes", () => {
  const probe = `
    const urls = [];
    globalThis.fetch = async (url) => {
      urls.push(String(url));
      return new Response("ok", { status: 200, headers: { "content-type": "text/plain", "content-length": "2" } });
    };
    require(process.env.INTERCEPTOR_PATH);
    fetch("https://api.openai.com/v1/chat/completions", { method: "POST", body: JSON.stringify({ prompt: process.env.CANARY || "x" }) })
      .then(() => new Promise((r) => setTimeout(r, 30)))
      .then(() => { process.stdout.write(urls.join("\\n")); });
  `;

  test("no key: an observed call does not request config or ingest", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-observe-"));
    try {
      const { code, stdout } = await runNode(probe, {
        HOME: home,
        INTERCEPTOR_PATH,
        VANTIO_HOME: join(home, ".vantio"),
        CANARY: "synthetic-canary-prompt-value",
      });
      assert.equal(code, 0);
      assert.match(stdout, /api\.openai\.com/);
      assert.doesNotMatch(stdout, /\/api\/v1\/config/);
      assert.doesNotMatch(stdout, /\/api\/v1\/ingest/);
      assert.doesNotMatch(stdout, /synthetic-canary-prompt-value/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("a key pointed at the public host still does not request config or ingest", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-public-key-"));
    try {
      const { code, stdout } = await runNode(probe, {
        HOME: home,
        INTERCEPTOR_PATH,
        VANTIO_HOME: join(home, ".vantio"),
        VANTIO_API_KEY: "vk_synthetic_public_host",
        VANTIO_INGEST_URL: "https://vantio.ai",
      });
      assert.equal(code, 0);
      assert.doesNotMatch(stdout, /\/api\/v1\/config/);
      assert.doesNotMatch(stdout, /\/api\/v1\/ingest/);
      assert.doesNotMatch(stdout, /vk_synthetic_public_host/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("telemetry opt-in does not use config or ingest", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-telemetry-"));
    try {
      const { code, stdout } = await runNode(probe, {
        HOME: home,
        INTERCEPTOR_PATH,
        VANTIO_HOME: join(home, ".vantio"),
        VANTIO_TELEMETRY: "1",
        VANTIO_INGEST_URL: "https://vantio.ai",
      });
      assert.equal(code, 0);
      assert.match(stdout, /\/api\/v1\/telemetry/);
      assert.doesNotMatch(stdout, /\/api\/v1\/config/);
      assert.doesNotMatch(stdout, /\/api\/v1\/ingest/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("telemetry stays off unless explicitly enabled", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-telemetry-off-"));
    try {
      const { code, stdout } = await runNode(probe, {
        HOME: home,
        INTERCEPTOR_PATH,
        VANTIO_HOME: join(home, ".vantio"),
      });
      assert.equal(code, 0);
      assert.doesNotMatch(stdout, /\/api\/v1\/telemetry/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("an explicit non-public control plane can still load policy", async () => {
    const hits = [];
    const server = await listen((req, res) => {
      hits.push(req.url || "");
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ policy: { enforce: false }, tier: "ENTERPRISE" }));
    });
    const port = server.address().port;
    const script = `
      globalThis.fetch = async (url) => {
        process.stdout.write(String(url) + "\\n");
        return new Response(JSON.stringify({ policy: { enforce: false }, tier: "ENTERPRISE" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      };
      require(process.env.INTERCEPTOR_PATH);
      setTimeout(() => process.exit(0), 40);
    `;
    try {
      const { code, stdout } = await runNode(script, {
        INTERCEPTOR_PATH,
        VANTIO_API_KEY: "vk_synthetic_control_plane",
        VANTIO_INGEST_URL: `http://127.0.0.1:${port}`,
      });
      assert.equal(code, 0);
      assert.match(stdout, new RegExp(`http://127\\.0\\.0\\.1:${port}/api/v1/config`));
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
    assert.equal(hits.length, 0, "the mock fetch must not fall through to the live socket");
  });
});

describe("local proof still works with no config", () => {
  test("zero-call run and proof do not mention accounts or the canary", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-proof-"));
    const canary = "synthetic-canary-should-not-appear";
    try {
      const run = await runCli(
        ["run", "node", "-e", "process.exit(0)"],
        { HOME: home, CANARY: canary },
      );
      assert.equal(run.code, 0);
      const proved = await runCli(["prove", "--format=html", "--out", join(home, "proof.html")], { HOME: home });
      assert.equal(proved.code, 0);
      const html = readFileSync(join(home, "proof.html"), "utf8");
      assert.match(html, /Vantio Optics \| Free Observability for AI Agents/);
      assert.match(html, /No calls recorded in this run log/);
      assert.doesNotMatch(html, ACCOUNT_PROMISE);
      assert.doesNotMatch(html, LADDER);
      assert.doesNotMatch(html, new RegExp(canary));
      assert.doesNotMatch(`${run.stdout}\n${run.stderr}\n${proved.stdout}\n${proved.stderr}`, new RegExp(canary));
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("proof shows recorded HTTP status for a non-2xx call", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-status-"));
    const logPath = join(home, "run.json");
    writeFileSync(logPath, JSON.stringify({
      vantio_run_log: "1",
      trace_id: "0xstatus",
      cli_version: "0.3.23",
      calls: [{ hostname: "api.openai.com", action: "OBSERVED", status: 503, bytes: 12, ts: "2026-09-23T00:00:00.000Z" }],
      summary: { total_calls: 1, total_bytes: 12, hosts: ["api.openai.com"] },
    }));
    try {
      const html = await runCli(["prove", "--from", logPath, "--format=html", "--out", join(home, "p.html")], { HOME: home });
      assert.equal(html.code, 0);
      const body = readFileSync(join(home, "p.html"), "utf8");
      assert.match(body, />503</);
      assert.match(body, /OBSERVED/);
      const md = await runCli(["prove", "--from", logPath, "--format=md"], { HOME: home });
      assert.equal(md.code, 0);
      assert.match(md.stdout, /503/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
});
