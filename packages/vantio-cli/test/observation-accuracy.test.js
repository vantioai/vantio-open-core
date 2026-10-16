// One test per remaining observation-accuracy item closed in CLI 0.3.25.
import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const interceptor = join(root, "bin", "interceptor.cjs");
const cli = join(root, "bin", "vantio.js");
const { guessProvider } = require(join(root, "bin", "llm-hosts.cjs"));
const optics = require(join(root, "bin", "optics-cx.cjs"));

function runNode(script, env) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ["--require", interceptor, "-e", script], {
      env: { PATH: process.env.PATH, VANTIO_TELEMETRY_DISABLED: "1", ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    const killer = setTimeout(() => child.kill("SIGKILL"), 8000);
    child.on("close", (code) => {
      clearTimeout(killer);
      resolve({ code, stdout, stderr });
    });
  });
}

function runCli(args, env) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [cli, ...args], {
      env: { PATH: process.env.PATH, VANTIO_TELEMETRY_DISABLED: "1", ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

test("a missing response size stays null and is not stored as zero", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-bytes-"));
  const server = await listen((_req, res) => {
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("hi");
  });
  try {
    const port = server.address().port;
    const result = await runNode(
      `fetch(process.env.TARGET_URL).then((res) => res.text()).then(() => {});`,
      {
        TARGET_URL: `http://127.0.0.1:${port}/v1/chat`,
        VANTIO_HOME: home,
        VANTIO_TRACE_ID: "bytes-absent",
        VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
      },
    );
    assert.equal(result.code, 0, result.stderr);
    const log = JSON.parse(readFileSync(join(home, "runs", "bytes-absent.json"), "utf8"));
    assert.equal(log.calls.length, 1);
    assert.equal(log.calls[0].bytes, null);
    assert.equal(log.calls[0].status, 200);
    assert.equal(log.summary.total_bytes, null);
    assert.equal(log.summary.bytes_complete, false);
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("a pre-response connect does not store success or a zero byte count", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-ok-"));
  try {
    const result = await runNode(
      `const socket = require("node:net").connect(1, "127.0.0.1"); socket.on("error", () => socket.destroy()); socket.on("connect", () => socket.end()); setTimeout(() => process.exit(0), 300);`,
      {
        VANTIO_HOME: home,
        VANTIO_TRACE_ID: "pre-response",
        VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
      },
    );
    assert.equal(result.code, 0, result.stderr);
    const log = JSON.parse(readFileSync(join(home, "runs", "pre-response.json"), "utf8"));
    const call = log.calls.find((item) => item.method === "CONNECT");
    assert.ok(call);
    assert.equal(call.ok, null);
    assert.equal(call.status, null);
    assert.equal(call.bytes, null);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("http.request stores the response status instead of a pre-response success", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-http-"));
  const server = await listen((_req, res) => {
    res.writeHead(503, { "content-type": "text/plain", "content-length": "2" });
    res.end("no");
  });
  try {
    const port = server.address().port;
    const result = await runNode(
      `require("node:http").get(process.env.TARGET_URL, (res) => { res.resume(); });`,
      {
        TARGET_URL: `http://127.0.0.1:${port}/v1/chat`,
        VANTIO_HOME: home,
        VANTIO_TRACE_ID: "http-status",
        VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
      },
    );
    assert.equal(result.code, 0, result.stderr);
    const log = JSON.parse(readFileSync(join(home, "runs", "http-status.json"), "utf8"));
    assert.equal(log.calls[0].status, 503);
    assert.equal(log.calls[0].ok, false);
    assert.equal(log.calls[0].bytes, 2);
  } finally {
    server.close();
    rmSync(home, { recursive: true, force: true });
  }
});

test("CLI readers use VANTIO_HOME", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-home-"));
  const ignored = mkdtempSync(join(tmpdir(), "vantio-ignored-"));
  const dir = join(home, "runs");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "home-trace.json"),
    JSON.stringify({
      vantio_run_log: "1",
      trace_id: "home-trace",
      calls: [{ hostname: "api.openai.com", action: "OBSERVED", status: 200, bytes: 4 }],
      summary: { total_calls: 1, total_bytes: 4, bytes_complete: true },
    }),
  );
  try {
    const found = await runCli(["prove", "--run", "home-trace", "--json"], {
      HOME: ignored,
      VANTIO_HOME: home,
    });
    assert.equal(found.code, 0, found.stderr);
    assert.equal(JSON.parse(found.stdout).trace_id, "home-trace");
    const missed = await runCli(["prove", "--run", "home-trace", "--json"], {
      HOME: ignored,
      VANTIO_HOME: "",
    });
    assert.equal(missed.code, 0, missed.stderr);
    assert.match(missed.stdout, /No run log matched/);
    assert.doesNotMatch(missed.stdout, /api\.openai\.com/);
  } finally {
    rmSync(home, { recursive: true, force: true });
    rmSync(ignored, { recursive: true, force: true });
  }
});

test("run lookup matches a file-name prefix and prefers an exact id", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-prefix-"));
  const dir = join(home, ".vantio", "runs");
  mkdirSync(dir, { recursive: true });
  const body = (id) =>
    JSON.stringify({
      vantio_run_log: "1",
      trace_id: id,
      calls: [{ hostname: "api.openai.com", action: "OBSERVED", status: 200, bytes: 1 }],
      summary: { total_calls: 1, total_bytes: 1, bytes_complete: true },
    });
  writeFileSync(join(dir, "xabc.json"), body("xabc"));
  writeFileSync(join(dir, "abcdef.json"), body("abcdef"));
  try {
    const prefixed = await runCli(["prove", "--run", "abc", "--json"], { HOME: home });
    assert.equal(prefixed.code, 0, prefixed.stderr);
    assert.equal(JSON.parse(prefixed.stdout).trace_id, "abcdef");
    writeFileSync(join(dir, "abc.json"), body("abc"));
    const exact = await runCli(["prove", "--run", "abc", "--json"], { HOME: home });
    assert.equal(exact.code, 0, exact.stderr);
    assert.equal(JSON.parse(exact.stdout).trace_id, "abc");
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("observed outcome keeps the machine token and names the HTTP result", () => {
  assert.equal(optics.applicationStatusFromHttp(401), "APPLICATION_ERROR");
  assert.equal(optics.observedOutcomeLabel(401), "Provider authentication failed");
  assert.equal(optics.observedOutcomeLabel(500), "Provider service error");
  assert.equal(optics.observedOutcomeLabel(null), "Provider outcome unavailable");
  const view = optics.displayCall({ status: 401, ok: true, bytes: null });
  assert.equal(view.applicationStatus, "APPLICATION_ERROR");
  assert.equal(view.applicationOutcomeLabel, "Provider authentication failed");
  assert.equal(view.bytes, null);
  assert.equal(optics.sumMeasuredBytes([{ bytes: null }, { bytes: 3 }]).total, null);
  assert.equal(optics.sumMeasuredBytes([{ bytes: 0 }]).total, 0);
});

test("provider labels follow the catalog and do not use a substring guess", () => {
  assert.equal(guessProvider("api.openai.com"), "openai");
  assert.equal(guessProvider("eastus.api.openai.com"), "openai");
  assert.equal(guessProvider("notopenai.example"), "other");
  assert.equal(guessProvider("www.googleapis.com"), "other");
  assert.equal(guessProvider("bedrock-runtime.us-east-1.amazonaws.com"), "bedrock");
});

test("shipped CLI sources omit the retired product name and retired prices", () => {
  const files = ["bin/interceptor.cjs", "bin/vantio.js", "bin/optics-cx.cjs", "README.md"];
  for (const rel of files) {
    const text = readFileSync(join(root, rel), "utf8");
    assert.equal(/\bGate\b/.test(text), false, rel);
    for (const price of ["$499", "$799", "$600", "14-day"]) {
      assert.equal(text.includes(price), false, `${rel} ${price}`);
    }
  }
});
