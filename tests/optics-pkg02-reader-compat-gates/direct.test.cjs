"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { displayCall } = require("../../packages/vantio-cli/bin/optics-cx.cjs");
const { CLASSIFICATION_READY, GATE_IDS, evaluateEntryGates } = require("../../packages/optics-reader-compat-gates/src/index.cjs");
const { futureRecord, writeCorpus } = require("./samples.cjs");

const ROOT = path.resolve(__dirname, "../..");
const CLI = path.join(ROOT, "packages/vantio-cli/bin/vantio.js");
const PYTHON_SDK = path.join(ROOT, "packages/vantio-agent-sdk-py");

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function runCli(home) {
  return spawnSync(process.execPath, [CLI, "run", "node", "-e", "process.exit(0)"], {
    cwd: home,
    encoding: "utf8",
    env: Object.assign({}, process.env, {
      HOME: home,
      VANTIO_HOME: path.join(home, ".vantio"),
    }),
  });
}

function onlyRunFile(home) {
  const runs = path.join(home, ".vantio", "runs");
  const files = fs.readdirSync(runs).filter((name) => name.endsWith(".json"));
  assert.equal(files.length, 1);
  return path.join(runs, files[0]);
}

function runPython(home) {
  const script = [
    "import asyncio, threading",
    "from http.server import BaseHTTPRequestHandler, HTTPServer",
    "import urllib.request",
    "from vantio import shield",
    "class Handler(BaseHTTPRequestHandler):",
    "    def do_GET(self):",
    "        body = b'{}'",
    "        self.send_response(200)",
    "        self.send_header('Content-Type', 'application/json')",
    "        self.send_header('Content-Length', str(len(body)))",
    "        self.end_headers()",
    "        self.wfile.write(body)",
    "    def log_message(self, fmt, *args):",
    "        return",
    "server = HTTPServer(('127.0.0.1', 0), Handler)",
    "port = server.server_address[1]",
    "thread = threading.Thread(target=server.serve_forever, daemon=True)",
    "thread.start()",
    "async def main():",
    "    async with shield(trace_id='pkg02-gates-py310'):",
    "        urllib.request.urlopen('http://127.0.0.1:%d/' % port, timeout=5)",
    "try:",
    "    asyncio.run(main())",
    "finally:",
    "    server.shutdown()",
  ].join("\n");
  return spawnSync("python3", ["-c", script], {
    cwd: home,
    encoding: "utf8",
    env: Object.assign({}, process.env, {
      HOME: home,
      PYTHONPATH: PYTHON_SDK,
      VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
      VANTIO_HOME: path.join(home, ".vantio"),
    }),
  });
}

function failedGates(report) {
  return report.gates.filter((gate) => gate.passed !== true).map((gate) => ({
    failures: gate.failures,
    id: gate.id,
  }));
}

test("entry gates pass on frozen CLI, frozen Python, and future records in one directory", () => {
  const cliHome = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-cli-"));
  const pythonHome = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-py-"));
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "pkg02-gates-dir-"));
  try {
    const cliRun = runCli(cliHome);
    assert.equal(cliRun.status, 0, cliRun.stderr || cliRun.stdout);
    const cliFile = onlyRunFile(cliHome);
    const cliBytes = fs.readFileSync(cliFile);
    const cliHash = sha256(cliBytes);
    const cliParsed = JSON.parse(cliBytes.toString("utf8"));
    assert.equal(cliParsed.cli_version, "0.3.24");
    assert.equal(cliParsed.schema_version, 2);

    const pythonRun = runPython(pythonHome);
    assert.equal(pythonRun.status, 0, pythonRun.stderr || pythonRun.stdout);
    const pythonFile = path.join(pythonHome, ".vantio", "runs", "pkg02-gates-py310.json");
    assert.equal(fs.existsSync(pythonFile), true);
    const pythonBytes = fs.readFileSync(pythonFile);
    const pythonHash = sha256(pythonBytes);
    const pythonParsed = JSON.parse(pythonBytes.toString("utf8"));
    assert.equal(pythonParsed.runtime, "python");
    assert.equal(pythonParsed.vantio_run_log, "1");
    assert.equal(pythonParsed.calls[0].opticsStatus, "SUCCESS");

    const corpus = writeCorpus(directory, {
      legacy_cli: cliBytes,
      legacy_python: pythonBytes,
    });
    const namesBefore = fs.readdirSync(directory).sort();
    const futureOnDisk = JSON.parse(fs.readFileSync(path.join(directory, "future-canonical.json"), "utf8"));
    assert.deepEqual(futureOnDisk, futureRecord());
    const frozen = displayCall(futureOnDisk);
    assert.equal(frozen.opticsStatus, "SUCCESS");
    const report = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: frozen,
    });
    assert.deepEqual(failedGates(report), []);
    assert.equal(report.producer_classification, CLASSIFICATION_READY);
    assert.equal(report.producer_ready_for_council, true);
    assert.equal(report.council_verdict, null);
    assert.equal(report.units_d_e, "NOT_AUTHORIZED");
    assert.equal(report.activates_unit_d, false);
    assert.equal(report.activates_unit_e, false);
    assert.equal(report.writer_activated, false);
    assert.equal(report.write_back, false);
    assert.equal(report.bytes_rewritten, false);
    assert.equal(report.directory_unchanged, true);
    assert.deepEqual(report.gates.map((gate) => gate.id), GATE_IDS);
    assert.deepEqual(fs.readdirSync(directory).sort(), namesBefore);
    assert.equal(sha256(fs.readFileSync(cliFile)), cliHash);
    assert.equal(sha256(fs.readFileSync(pythonFile)), pythonHash);
    assert.equal(fs.existsSync(path.join(directory, corpus.absentName)), false);
    const again = evaluateEntryGates({
      absentName: corpus.absentName,
      directory,
      entries: corpus.entries,
      frozenDisplay: frozen,
    });
    assert.equal(again.producer_classification, report.producer_classification);
    assert.deepEqual(again.gates.map((gate) => gate.passed), report.gates.map((gate) => gate.passed));
    assert.equal(sha256(fs.readFileSync(cliFile)), cliHash);
    assert.equal(sha256(fs.readFileSync(pythonFile)), pythonHash);
  } finally {
    fs.rmSync(cliHome, { recursive: true, force: true });
    fs.rmSync(pythonHome, { recursive: true, force: true });
    fs.rmSync(directory, { recursive: true, force: true });
  }
});
