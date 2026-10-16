// Q13: `vantio run` loads in-process MCP awareness by default.
// Observe forwards the original bytes and does not store payload text.
// Enforce is opt-in and withholds inside the same process.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = join(__dirname, "..", "bin", "vantio.js");
const REGISTER_PATH = join(__dirname, "..", "bin", "mcp-awareness-register.js");
const CANARY = "CANARY_MCP_PAYLOAD_9f3a";

function runCli(args, env = {}, timeoutMs = 8000) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI_PATH, ...args], {
      env: { PATH: process.env.PATH, ...env },
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
    const killer = setTimeout(() => {
      child.kill("SIGKILL");
    }, timeoutMs);
    child.on("close", (code) => {
      clearTimeout(killer);
      resolve({ code, stdout, stderr });
    });
  });
}

function frame() {
  return `${JSON.stringify({
    jsonrpc: "2.0",
    id: 7,
    method: "tools/call",
    params: { name: "write_file", arguments: { path: CANARY } },
  })}\n`;
}

function writeAgent(home, source) {
  const path = join(home, "agent.js");
  writeFileSync(path, source);
  return path;
}

const STDIO_AGENT = `
const { spawn } = require("node:child_process");
const { writeFileSync } = require("node:fs");
const child = spawn(process.execPath, ["-e", \`
  const fs = require("fs");
  const chunks = [];
  process.stdin.on("data", (c) => chunks.push(c));
  process.stdin.on("end", () => {
    fs.writeFileSync(process.env.SINK, Buffer.concat(chunks));
  });
\`], { stdio: ["pipe", "pipe", "ignore"], env: { ...process.env, SINK: process.env.SINK } });
let out = "";
child.stdout.on("data", (chunk) => { out += chunk.toString("utf8"); });
child.stdin.write("hello\\n");
child.stdin.write(process.env.FRAME);
child.stdin.end();
child.on("close", () => {
  process.stdout.write(JSON.stringify({ out }));
});
`;

const HTTP_AGENT = `
const http = require("node:http");
const { writeFileSync } = require("node:fs");
const server = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    writeFileSync(process.env.HTTP_SINK, Buffer.concat(chunks));
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ jsonrpc: "2.0", id: 3, result: { ok: true } }));
  });
});
server.listen(0, "127.0.0.1", async () => {
  const port = server.address().port;
  const body = JSON.stringify({
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: { name: "write_file", arguments: { path: process.env.CANARY } },
  });
  const plain = await fetch("http://127.0.0.1:" + port + "/health", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ hello: "plain" }),
  });
  const mcp = await fetch("http://127.0.0.1:" + port + "/mcp", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  const text = await mcp.text();
  process.stdout.write(JSON.stringify({ plain: plain.status, status: mcp.status, text }));
  server.close();
});
`;

function readLog(home) {
  const path = join(home, ".vantio", "mcp-observations.jsonl");
  if (!existsSync(path)) return "";
  return readFileSync(path, "utf8");
}

test("register source does not listen or spawn a proxy", () => {
  const source = readFileSync(REGISTER_PATH, "utf8");
  assert.equal(source.includes("createServer"), false);
  assert.equal(source.includes(".listen("), false);
  assert.equal(source.includes("net.connect"), false);
  assert.equal(source.includes("http.request"), false);
  assert.match(source, /not Phantom Engine/);
});

test("node vantio run defaults to observe and log", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-env-"));
  try {
    const result = await runCli(
      ["run", "node", "-e", "process.stdout.write([process.env.VANTIO_MCP_AWARENESS, process.env.VANTIO_MCP_MODE, process.env.VANTIO_MCP_INJECTION, process.env.VANTIO_MCP_RUG_PULL, process.env.NODE_OPTIONS].join('\\n'))"],
      { HOME: home },
    );
    assert.equal(result.code, 0, result.stderr);
    const [awareness, mode, injection, rugPull, nodeOptions] = result.stdout.split("\n");
    assert.equal(awareness, "on");
    assert.equal(mode, "observe");
    assert.equal(injection, "log");
    assert.equal(rugPull, "log");
    assert.match(nodeOptions, /mcp-awareness-register\.js/);
    assert.match(result.stderr, /mcp awareness mode=observe injection=log rug_pull=log/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("a missing library does not change the child exit", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-miss-"));
  try {
    const result = await runCli(
      ["run", "node", "-e", "process.exit(3)"],
      { HOME: home, VANTIO_MCP_LIB: join(home, "missing.js") },
    );
    assert.equal(result.code, 3, result.stderr);
    assert.equal(result.stderr.includes("mcp awareness"), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("--mcp-enforce selects enforce and off skips the register", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-flag-"));
  try {
    const enforced = await runCli(
      ["run", "--mcp-enforce", "node", "-e", "process.stdout.write(process.env.VANTIO_MCP_MODE || '')"],
      { HOME: home },
    );
    assert.equal(enforced.code, 0, enforced.stderr);
    assert.equal(enforced.stdout, "enforce");
    const off = await runCli(
      ["run", "node", "-e", "process.stdout.write((process.env.NODE_OPTIONS || '').includes('mcp-awareness-register') ? 'loaded' : 'absent')"],
      { HOME: home, VANTIO_MCP_AWARENESS: "off" },
    );
    assert.equal(off.code, 0, off.stderr);
    assert.equal(off.stdout, "absent");
    assert.equal(off.stderr.includes("mcp awareness"), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("observe forwards stdio bytes and keeps the canary out of the log", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-obs-"));
  const sink = join(home, "sink");
  try {
    const agent = writeAgent(home, STDIO_AGENT);
    const result = await runCli(["run", "node", agent], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
      CANARY,
    });
    assert.equal(result.code, 0, `${result.stderr}\n${result.stdout}`);
    const received = readFileSync(sink);
    assert.equal(received.includes(CANARY), true);
    assert.equal(received.includes("hello\n"), true);
    const log = readLog(home);
    assert.equal(log.includes(CANARY), false);
    assert.equal(`${result.stdout}\n${result.stderr}`.includes(CANARY), false);
    assert.match(log, /"method":"tools\/call"/);
    assert.match(log, /"server_unlisted"/);
    assert.equal(log.includes('"payload":true'), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("enforce opt-in withholds the tool call and still forwards a non-MCP line", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-enf-"));
  const sink = join(home, "sink");
  try {
    const agent = writeAgent(home, STDIO_AGENT);
    const result = await runCli(["run", "--mcp-enforce", "node", agent], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
      CANARY,
    });
    assert.equal(result.code, 0, `${result.stderr}\n${result.stdout}`);
    const received = readFileSync(sink, "utf8");
    assert.equal(received.includes(CANARY), false);
    assert.equal(received.includes("hello\n"), true);
    const parent = JSON.parse(result.stdout);
    assert.match(parent.out, /vantio_mcp_policy_block/);
    assert.equal(parent.out.includes(CANARY), false);
    const log = readLog(home);
    assert.equal(log.includes(CANARY), false);
    assert.match(log, /"action":"BLOCK"/);
    assert.equal(`${result.stderr}`.includes(CANARY), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("enforce withholds on stdin when there is no stdout pipe for the pair gate", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-line-"));
  const sink = join(home, "sink");
  const agent = `
const { spawn } = require("node:child_process");
const child = spawn(process.execPath, ["-e", \`
  const fs = require("fs");
  const chunks = [];
  process.stdin.on("data", (c) => chunks.push(c));
  process.stdin.on("end", () => fs.writeFileSync(process.env.SINK, Buffer.concat(chunks)));
\`], { stdio: ["pipe", "ignore", "ignore"], env: { ...process.env, SINK: process.env.SINK } });
child.stdin.write("hello\\n");
child.stdin.write(process.env.FRAME);
child.stdin.end();
child.on("close", () => process.exit(0));
`;
  try {
    const path = writeAgent(home, agent);
    const result = await runCli(["run", "--mcp-enforce", "node", path], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
    });
    assert.equal(result.code, 0, `${result.stderr}\n${result.stdout}`);
    const received = readFileSync(sink, "utf8");
    assert.equal(received.includes(CANARY), false);
    assert.equal(received.includes("hello\n"), true);
    const log = readLog(home);
    assert.equal(log.includes(CANARY), false);
    assert.match(log, /"action":"BLOCK"/);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});

test("observe lets an HTTP JSON-RPC request through and enforce does not send it", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-mcp-http-"));
  const httpSink = join(home, "http-sink");
  try {
    const agent = writeAgent(home, HTTP_AGENT);
    const observed = await runCli(["run", "node", agent], { HOME: home, HTTP_SINK: httpSink, CANARY });
    assert.equal(observed.code, 0, `${observed.stderr}\n${observed.stdout}`);
    const observedBody = JSON.parse(observed.stdout);
    assert.equal(observedBody.plain, 200);
    assert.equal(observedBody.status, 200);
    assert.match(observedBody.text, /"ok":true/);
    const httpBytes = readFileSync(httpSink, "utf8");
    assert.equal(httpBytes.includes(CANARY), true);
    assert.equal(readLog(home).includes(CANARY), false);
    rmSync(httpSink, { force: true });

    const enforced = await runCli(["run", "--mcp-enforce", "node", agent], {
      HOME: join(home, "enf"),
      HTTP_SINK: httpSink,
      CANARY,
    });
    assert.equal(enforced.code, 0, `${enforced.stderr}\n${enforced.stdout}`);
    const enforcedBody = JSON.parse(enforced.stdout);
    assert.equal(enforcedBody.plain, 200);
    assert.match(enforcedBody.text, /vantio_mcp_policy_block/);
    assert.equal(enforcedBody.text.includes(CANARY), false);
    const withheld = readFileSync(httpSink, "utf8");
    assert.equal(withheld.includes(CANARY), false);
    assert.equal(withheld.includes("plain"), true);
    assert.equal(readFileSync(join(home, "enf", ".vantio", "mcp-observations.jsonl"), "utf8").includes(CANARY), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
