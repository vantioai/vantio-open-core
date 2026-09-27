"use strict";

const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { readRunFile, explainFixture } = require("../../packages/optics-record-reader/src/explain.cjs");
const fixtures = require("../../packages/optics-record-vocabulary/fixtures/conformance-fixtures.json");

const ROOT = path.resolve(__dirname, "../..");
const CLI = path.join(ROOT, "packages/vantio-cli/bin/vantio.js");
const PYTHON_SDK = path.join(ROOT, "packages/vantio-agent-sdk-py");

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function opticsTokens(result) {
  const tokens = [result.optics_health];
  for (const line of result.display) {
    if (line.dimension === "optics_status" || line.dimension === "optics_health") tokens.push(line.token);
  }
  if (result.record && hasOwn(result.record, "optics_status")) tokens.push(result.record.optics_status);
  for (const event of result.events) {
    if (event.record && hasOwn(event.record, "optics_status")) tokens.push(event.record.optics_status);
  }
  return tokens;
}

function assertNoOpticsSuccess(result) {
  assert.equal(result.optics_displayed_as_success, false);
  assert.equal(opticsTokens(result).includes("SUCCESS"), false);
  assert.equal(result.explanation_text.includes("optics_status=SUCCESS"), false);
  assert.equal(result.explanation_text.includes("optics_health=SUCCESS"), false);
  assert.equal(result.write_back, false);
  assert.equal(result.input_bytes_identical, true);
  assert.equal(result.writer_activated, false);
  assert.equal(result.units_d_e, "NOT_AUTHORIZED");
}

function runCli(home, args) {
  return spawnSync(process.execPath, [CLI, ...args], {
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

test("a real CLI 0.3.24 run file stays legacy and byte-identical", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-cli-"));
  try {
    const child = runCli(home, ["run", "node", "-e", "process.exit(0)"]);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const file = onlyRunFile(home);
    const before = fs.readFileSync(file);
    const beforeHash = sha256(before);
    const explained = readRunFile(file);
    const after = fs.readFileSync(file);
    assert.equal(sha256(after), beforeHash);
    assert.equal(before.equals(after), true);
    const parsed = JSON.parse(before.toString("utf8"));
    assert.equal(parsed.cli_version, "0.3.24");
    assert.equal(parsed.schema_version, 2);
    assertNoOpticsSuccess(explained);
    assert.equal(explained.reader_origin_label, "LEGACY_UNMARKED");
    assert.equal(explained.optics_health, "NOT_OBSERVED");
    assert.equal(explained.record.optics_status, "NOT_OBSERVED");
    assert.equal(explained.record.trace_id_basis, "ASSERTED_CONTEXT");
    assert.notEqual(explained.record.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(explained.compatibility.legacy_schema_version, 2);
    assert.equal(explained.schema_version, 0);
    assert.equal(JSON.stringify(explained).includes("LOCAL_OBSERVATION"), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a real CLI 0.3.24 demo file stays simulated and byte-identical", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-demo-"));
  try {
    const child = runCli(home, ["demo"]);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const file = onlyRunFile(home);
    const before = fs.readFileSync(file);
    const explained = readRunFile(file);
    const after = fs.readFileSync(file);
    assert.equal(before.equals(after), true);
    const parsed = JSON.parse(before.toString("utf8"));
    assert.equal(parsed.cli_version, "0.3.24");
    assert.equal(parsed.calls[0].hostname, "optics-demo.invalid");
    assert.equal(parsed.calls[0].bytes, 0);
    assertNoOpticsSuccess(explained);
    assert.equal(explained.reader_origin_label, "LEGACY_UNMARKED");
    assert.equal(explained.events[0].reader_origin_label, "SIMULATED_DEMO");
    assert.equal(explained.events[0].record.evidence_origin, "SIMULATED_DEMO");
    assert.equal(explained.events[0].record.optics_status, "UNAVAILABLE");
    assert.equal(explained.events[0].record.application_status, "SUCCESS");
    assert.equal(explained.events[0].record.response_bytes, null);
    assert.equal(explained.explanation_text.includes("event[0].evidence_origin=SIMULATED_DEMO"), true);
    assert.equal(explained.explanation_text.includes("application_status=SUCCESS"), true);
    assert.equal(explained.explanation_text.includes("response_bytes=null"), true);
    assert.equal(JSON.stringify(explained).includes("LOCAL_OBSERVATION"), false);
    assert.equal(JSON.stringify(explained).includes("\"bytes\""), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a live Python 3.1.0 run file refuses stored optics SUCCESS and stays byte-identical", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-py-"));
  try {
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
      "    async with shield(trace_id='unit-f-py310'):",
      "        urllib.request.urlopen('http://127.0.0.1:%d/' % port, timeout=5)",
      "try:",
      "    asyncio.run(main())",
      "finally:",
      "    server.shutdown()",
    ].join("\n");
    const child = spawnSync("python3", ["-c", script], {
      cwd: home,
      encoding: "utf8",
      env: Object.assign({}, process.env, {
        HOME: home,
        PYTHONPATH: PYTHON_SDK,
        VANTIO_EXTRA_LLM_HOSTS: "127.0.0.1",
        VANTIO_HOME: path.join(home, ".vantio"),
      }),
    });
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const file = path.join(home, ".vantio", "runs", "unit-f-py310.json");
    assert.equal(fs.existsSync(file), true);
    const before = fs.readFileSync(file);
    const parsed = JSON.parse(before.toString("utf8"));
    assert.equal(parsed.runtime, "python");
    assert.equal(parsed.vantio_run_log, "1");
    assert.equal(parsed.calls[0].opticsStatus, "SUCCESS");
    const explained = readRunFile(file);
    const after = fs.readFileSync(file);
    assert.equal(before.equals(after), true);
    assert.equal(JSON.parse(after.toString("utf8")).calls[0].opticsStatus, "SUCCESS");
    assertNoOpticsSuccess(explained);
    assert.equal(explained.reader_origin_label, "LEGACY_UNMARKED");
    assert.equal(explained.events[0].record.optics_status, "UNAVAILABLE");
    assert.equal(explained.optimistic_default_forbidden, true);
    assert.equal(explained.optics_input_classes.includes("refused_success"), true);
    assert.equal(explained.events[0].record.application_status, "SUCCESS");
    assert.notEqual(explained.record && explained.record.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(JSON.stringify(explained).includes("LOCAL_OBSERVATION"), false);
    assert.equal(JSON.stringify(explained).includes("Developer egress data log"), false);
    assert.equal(JSON.stringify(explained).includes("SUPER_SUCCESS"), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a canonical fixture keeps explicit OBSERVED and does not invent local observation", () => {
  const fixture = fixtures.find((item) => item.id === "explicit-observed-not-default");
  const explained = explainFixture(fixture);
  assert.equal(explained.events[0].record.optics_status, "OBSERVED");
  assert.equal(explained.events[0].record.application_status, "SUCCESS");
  assert.equal(explained.optics_displayed_as_success, false);
  assert.equal(explained.optics_input_classes.includes("enum"), true);
  assert.equal(JSON.stringify(explained).includes("LOCAL_OBSERVATION"), false);

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "unit-f-canonical-"));
  const file = path.join(dir, "canonical.json");
  const body = JSON.stringify({
    calls: [fixture.input_record.call],
    vantio_run_log: "1",
  });
  fs.writeFileSync(file, body);
  try {
    const before = fs.readFileSync(file);
    const opened = readRunFile(file);
    assert.equal(fs.readFileSync(file).equals(before), true);
    assert.equal(opened.input_bytes_identical, true);
    assert.equal(opened.events[0].record.optics_status, "OBSERVED");
    assert.equal(opened.events[0].record.application_status, "SUCCESS");
    assert.equal(opened.optics_displayed_as_success, false);
    assert.equal(opened.explanation_text.includes("optics_status=OBSERVED"), true);
    assert.equal(opened.explanation_text.includes("optics_status=SUCCESS"), false);
    assert.equal(JSON.stringify(opened).includes("LOCAL_OBSERVATION"), false);
    assert.equal(opened.write_back, false);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
