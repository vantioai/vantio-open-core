// Optics P0: a distinctive prompt marker must never land in the local run log.
import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdtempSync, rmSync, readdirSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const INTERCEPTOR = join(__dirname, "..", "bin", "interceptor.cjs");

function scratchRoot() {
  for (const d of [process.env.TMPDIR, tmpdir(), "/tmp"]) {
    if (d && existsSync(d)) return d;
  }
  return "/tmp";
}

function runAgent(env, script) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, ["--require", INTERCEPTOR, "-e", script], {
      env: { PATH: process.env.PATH, ...env },
      stdio: ["ignore", "pipe", "pipe"],
      cwd: join(__dirname, ".."),
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (c) => { stdout += c; });
    child.stderr.on("data", (c) => { stderr += c; });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

describe("Optics privacy — prompt marker never stored", () => {
  let server;
  let home;
  let targetUrl;
  let received = "";

  beforeEach(async () => {
    home = mkdtempSync(join(scratchRoot(), "vantio-privacy-"));
    received = "";
    server = http.createServer((req, res) => {
      const chunks = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        received = Buffer.concat(chunks).toString("utf8");
        const payload = JSON.stringify({ id: "chatcmpl-p0", choices: [{ message: { content: "ok" } }] });
        res.writeHead(200, { "content-type": "application/json" });
        res.end(payload);
      });
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    targetUrl = `http://127.0.0.1:${port}/v1/chat/completions`;
  });

  afterEach(async () => {
    await new Promise((resolve) => server.close(resolve));
    rmSync(home, { recursive: true, force: true });
  });

  test("unique prompt marker reaches the target and is absent from ~/.vantio/runs", async () => {
    const marker = "OPTICS_P0_MARKER_" + randomUUID().replace(/-/g, "");
    const script = `
      fetch(process.env.TARGET_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ prompt: process.env.MARKER, messages: [{ role: "user", content: process.env.MARKER }] }),
      }).then(async (r) => {
        process.stdout.write(JSON.stringify({ status: r.status }) + "\\n");
      });
    `;
    const { code } = await runAgent(
      {
        TARGET_URL: targetUrl,
        MARKER: marker,
        VANTIO_HOME: home,
        VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
        HOME: home,
      },
      script,
    );
    assert.equal(code, 0);
    assert.match(received, new RegExp(marker));
    const runs = join(home, "runs");
    const files = readdirSync(runs).filter((f) => f.endsWith(".json"));
    assert.ok(files.length >= 1, "wrap must write a run log");
    for (const f of files) {
      const blob = readFileSync(join(runs, f), "utf8");
      assert.doesNotMatch(blob, new RegExp(marker));
      const log = JSON.parse(blob);
      assert.equal(log.vantio_run_log, "1");
      for (const call of log.calls || []) {
        assert.equal(Object.prototype.hasOwnProperty.call(call, "prompt"), false);
        assert.equal(Object.prototype.hasOwnProperty.call(call, "messages"), false);
        assert.equal(Object.prototype.hasOwnProperty.call(call, "body"), false);
        assert.equal(Object.prototype.hasOwnProperty.call(call, "completion"), false);
      }
    }
  });
});
