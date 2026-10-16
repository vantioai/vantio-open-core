// Packed CLI and Python `vantio run` load the same MCP library.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, rmSync, readdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_DIR = join(__dirname, "..");
const CLI_PATH = join(CLI_DIR, "bin", "vantio.js");
const CANARY = "CANARY_MCP_PAYLOAD_9f3a";

function runCli(cli, args, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [cli, ...args], {
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
    const killer = setTimeout(() => child.kill("SIGKILL"), 8000);
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

const NODE_AGENT = `
const { spawn } = require("node:child_process");
const { writeFileSync } = require("node:fs");
const child = spawn(process.execPath, ["-e", \`
  const fs = require("fs");
  const chunks = [];
  process.stdin.on("data", (c) => chunks.push(c));
  process.stdin.on("end", () => fs.writeFileSync(process.env.SINK, Buffer.concat(chunks)));
\`], { stdio: ["pipe", "pipe", "ignore"], env: process.env });
let out = "";
child.stdout.on("data", (chunk) => { out += chunk.toString("utf8"); });
child.stdin.write("hello\\n");
child.stdin.write(process.env.FRAME);
child.stdin.end();
child.on("close", () => process.stdout.write(out));
`;

const PYTHON_AGENT = `
import os, subprocess
child = subprocess.Popen(
    [os.environ["NODE"], "-e", """
const fs = require("fs");
const chunks = [];
process.stdin.on("data", (c) => chunks.push(c));
process.stdin.on("end", () => fs.writeFileSync(process.env.SINK, Buffer.concat(chunks)));
"""],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    env=os.environ.copy(),
)
child.stdin.write(b"hello\\n")
child.stdin.write(os.environ["FRAME"].encode())
child.stdin.close()
out = child.stdout.read() or b""
child.wait()
open(os.environ["PARENT_OUT"], "wb").write(out)
`;

test("vendored library matches the package sources", () => {
  const srcDir = join(__dirname, "..", "..", "vantio-mcp-awareness", "src");
  const vendorDir = join(CLI_DIR, "bin", "mcp-awareness");
  const skip = new Set(["test-key.js"]);
  const srcNames = readdirSync(srcDir).filter((name) => name.endsWith(".js") && !skip.has(name)).sort();
  const vendorNames = readdirSync(vendorDir).filter((name) => name.endsWith(".js")).sort();
  assert.deepEqual(vendorNames, srcNames);
  for (const name of srcNames) {
    assert.equal(readFileSync(join(vendorDir, name), "utf8"), readFileSync(join(srcDir, name), "utf8"), name);
  }
});

test("packed tarball loads MCP awareness away from the monorepo", async () => {
  const packDir = mkdtempSync(join(tmpdir(), "vantio-pack-"));
  const home = mkdtempSync(join(tmpdir(), "vantio-pack-home-"));
  try {
    const packedName = execFileSync("npm", ["pack", "--ignore-scripts", "--pack-destination", packDir], {
      cwd: CLI_DIR,
      encoding: "utf8",
    }).trim().split("\n").pop();
    execFileSync("tar", ["-xzf", join(packDir, packedName), "-C", packDir]);
    const root = join(packDir, "package");
    assert.equal(existsSync(join(root, "bin", "mcp-awareness", "index.js")), true);
    assert.equal(existsSync(join(root, "..", "..", "vantio-mcp-awareness")), false);
    const agent = join(home, "agent.js");
    const sink = join(home, "sink");
    writeFileSync(agent, NODE_AGENT);
    const result = await runCli(join(root, "bin", "vantio.js"), ["run", "node", agent], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
    });
    assert.equal(result.code, 0, `${result.stderr}\n${result.stdout}`);
    assert.match(result.stderr, /mcp awareness mode=observe/);
    assert.equal(readFileSync(sink).includes(CANARY), true);
    const log = readFileSync(join(home, ".vantio", "mcp-observations.jsonl"), "utf8");
    assert.equal(log.includes(CANARY), false);
    assert.match(log, /tools\/call/);
  } finally {
    rmSync(packDir, { recursive: true, force: true });
    rmSync(home, { recursive: true, force: true });
  }
});

test("python vantio run observes and can enforce without storing the canary", async () => {
  const home = mkdtempSync(join(tmpdir(), "vantio-py-mcp-"));
  const sink = join(home, "sink");
  const parentOut = join(home, "parent-out");
  const agent = join(home, "agent.py");
  writeFileSync(agent, PYTHON_AGENT);
  try {
    const observed = await runCli(CLI_PATH, ["run", "python3", agent], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
      NODE: process.execPath,
      PARENT_OUT: parentOut,
    });
    assert.equal(observed.code, 0, `${observed.stderr}\n${observed.stdout}`);
    assert.match(observed.stderr, /mcp awareness mode=observe/);
    assert.equal(readFileSync(sink).includes(CANARY), true);
    const log = readFileSync(join(home, ".vantio", "mcp-observations.jsonl"), "utf8");
    assert.equal(log.includes(CANARY), false);
    rmSync(sink, { force: true });
    rmSync(join(home, ".vantio", "mcp-observations.jsonl"), { force: true });

    const enforced = await runCli(CLI_PATH, ["run", "--mcp-enforce", "python3", agent], {
      HOME: home,
      SINK: sink,
      FRAME: frame(),
      NODE: process.execPath,
      PARENT_OUT: parentOut,
    });
    assert.equal(enforced.code, 0, `${enforced.stderr}\n${enforced.stdout}`);
    const received = readFileSync(sink, "utf8");
    assert.equal(received.includes(CANARY), false);
    assert.equal(received.includes("hello\n"), true);
    const parent = readFileSync(parentOut, "utf8");
    assert.match(parent, /vantio_mcp_policy_block/);
    assert.equal(parent.includes(CANARY), false);
    assert.equal(readFileSync(join(home, ".vantio", "mcp-observations.jsonl"), "utf8").includes(CANARY), false);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
