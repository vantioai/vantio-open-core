"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const api = require("../../packages/vantio-cli-pkg02/src/index.cjs");
const support = require("./support.cjs");

const CANARY = "SECRET_PROMPT_CANARY";

function assertCommon(document) {
  assert.equal(document.record_type, "run_envelope");
  assert.equal(document.schema_version, 0);
  assert.equal(document.schema_status, "unstable-pre-1.0");
  assert.equal(document.compatibility.legacy_schema_version, 2);
  assert.equal(document.schema_version === 2, false);
  assert.equal(document.producer, "node_interceptor");
  assert.equal(document.cli_or_sdk_version, api.FUTURE_CLI_VERSION);
  assert.equal(document.evidence_origin, "LOCAL_OBSERVATION");
  assert.equal(document.diagnostics.unicode_profile_id, "PKG01-UCD-16.0.0");
  assert.equal(document.activates_unit_e, false);
  assert.equal(document.shipped_product, false);
  support.assertNoOpticsSuccess(assert, document);
  const keys = support.prohibitedKeys(document, []);
  for (const banned of support.BANNED) assert.equal(keys.includes(banned), false, banned);
  const machine = os.hostname();
  if (machine && machine.length > 4 && machine !== "localhost") {
    assert.equal(JSON.stringify(document).includes(machine), false);
  }
  assert.equal(JSON.stringify(document).includes(CANARY), false);
}

test("one in-scope call writes OBSERVED and keeps the prompt out of the file", () => {
  const home = support.homeDir("unit-d-inscope-");
  const script = `
    const http = require("node:http");
    const server = http.createServer((req, res) => {
      const body = Buffer.from("{}");
      res.writeHead(200, { "Content-Type": "application/json", "Content-Length": String(body.length) });
      res.end(body);
    });
    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      const response = await fetch("http://127.0.0.1:" + port + "/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: ${JSON.stringify(CANARY)},
      });
      await response.arrayBuffer();
      server.close();
    });
  `;
  try {
    const child = support.runFuture(home, script);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assertCommon(document);
    assert.equal(document.optics_status, "OBSERVED");
    assert.equal(document.run_id.startsWith("0x"), true);
    assert.equal(Object.prototype.hasOwnProperty.call(document, "trace_id"), false);
    assert.equal(document.events.length, 1);
    const event = document.events[0];
    assert.equal(event.record_type, "observation_event");
    assert.equal(event.schema_version, 0);
    assert.equal(event.optics_status, "OBSERVED");
    assert.equal(event.application_status, "SUCCESS");
    assert.equal(event.http_status, 200);
    assert.equal(event.response_bytes, 2);
    assert.equal(event.action, "OBSERVED");
    assert.equal(event.issue_location, "NONE");
    assert.equal(event.evidence_origin, "LOCAL_OBSERVATION");
    assert.equal(event.producer, "node_interceptor");
    assert.equal(event.cli_or_sdk_version, api.FUTURE_CLI_VERSION);
    const explained = api.explainCanonical(document);
    assert.equal(explained.classification, "FULL");
    assert.equal(explained.optics_status, "OBSERVED");
    assert.equal(explained.activates_unit_e, false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("an empty wrap writes NOT_OBSERVED and does not invent SUCCESS", () => {
  const home = support.homeDir("unit-d-empty-");
  try {
    const child = support.runFuture(home, "process.exit(0);\n");
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assertCommon(document);
    assert.equal(document.optics_status, "NOT_OBSERVED");
    assert.equal(document.call_count, 0);
    assert.deepEqual(document.events, []);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a missing content-length omits response_bytes", () => {
  const home = support.homeDir("unit-d-length-");
  const script = `
    const http = require("node:http");
    const server = http.createServer((req, res) => {
      res.writeHead(200, { "Content-Type": "application/json", "Transfer-Encoding": "chunked" });
      res.end("{}");
    });
    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      const response = await fetch("http://127.0.0.1:" + port + "/v1/chat/completions");
      await response.arrayBuffer();
      server.close();
    });
  `;
  try {
    const child = support.runFuture(home, script);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assertCommon(document);
    const event = document.events[0];
    assert.equal(event.optics_status, "OBSERVED");
    assert.equal(event.http_status, 200);
    assert.equal(support.hasOwn(event, "response_bytes"), false);
    assert.equal(JSON.stringify(event).includes("response_bytes"), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("HTTP 500 stays OBSERVED with PROVIDER_INTERACTION and not optics SUCCESS", () => {
  const home = support.homeDir("unit-d-500-");
  const script = `
    const http = require("node:http");
    const server = http.createServer((req, res) => {
      const body = Buffer.from("{}");
      res.writeHead(500, { "Content-Type": "application/json", "Content-Length": String(body.length) });
      res.end(body);
    });
    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      const response = await fetch("http://127.0.0.1:" + port + "/v1/chat/completions");
      await response.arrayBuffer();
      server.close();
    });
  `;
  try {
    const child = support.runFuture(home, script);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assertCommon(document);
    const event = document.events[0];
    assert.equal(event.optics_status, "OBSERVED");
    assert.equal(event.http_status, 500);
    assert.equal(event.application_status, "APPLICATION_ERROR");
    assert.equal(event.issue_location, "PROVIDER_INTERACTION");
    assert.equal(event.response_bytes, 2);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a network error is OBSERVED at NETWORK and omits response_bytes", () => {
  const home = support.homeDir("unit-d-net-");
  const script = `
    const http = require("node:http");
    const server = http.createServer((req, res) => res.end("nope"));
    server.listen(0, "127.0.0.1", async () => {
      const port = server.address().port;
      server.close(() => {
        fetch("http://127.0.0.1:" + port + "/").then(() => process.exit(1)).catch(() => process.exit(0));
      });
    });
  `;
  try {
    const child = support.runFuture(home, script);
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const document = support.readJson(support.runFiles(home)[0]);
    assertCommon(document);
    const event = document.events[0];
    assert.equal(event.optics_status, "OBSERVED");
    assert.equal(event.failure_kind, "network");
    assert.equal(event.issue_location, "NETWORK");
    assert.equal(event.application_status, "UNAVAILABLE");
    assert.equal(support.hasOwn(event, "http_status"), false);
    assert.equal(support.hasOwn(event, "response_bytes"), false);
    assert.equal(event.action, "OBSERVED");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});

test("a custom VANTIO_HOME still receives the canonical writer", () => {
  const home = support.homeDir("unit-d-custom-");
  const vantioHome = path.join(home, "custom-home");
  try {
    const child = support.runFuture(home, "process.exit(0);\n", { VANTIO_HOME: vantioHome });
    assert.equal(child.status, 0, child.stderr || child.stdout);
    const runs = path.join(vantioHome, "runs");
    const files = fs.readdirSync(runs).filter((name) => name.endsWith(".json"));
    assert.equal(files.length, 1);
    const document = JSON.parse(fs.readFileSync(path.join(runs, files[0]), "utf8"));
    assert.equal(document.record_type, "run_envelope");
    assert.equal(document.schema_version, 0);
    assert.equal(document.optics_status, "NOT_OBSERVED");
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
