"use strict";

const assert = require("node:assert/strict");
const http = require("node:http");
const test = require("node:test");

const api = require("../../packages/optics-otel-i3/src/index.cjs");
const { assertNoLeak, goodRecord } = require("./helpers.cjs");

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}

function closeServer(server) {
  if (typeof server.closeAllConnections === "function") server.closeAllConnections();
  return new Promise((resolve) => server.close(() => resolve()));
}

test("the built-in client posts JSON to the customer traces path", async () => {
  const prompt = "http-body-must-not-contain-this-prompt";
  const seen = [];
  const server = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      seen.push({
        url: req.url,
        headers: req.headers,
        body: Buffer.concat(chunks).toString("utf8"),
      });
      res.writeHead(200, { "content-type": "application/json" });
      res.end("{}");
    });
  });
  const port = await listen(server);
  try {
    const result = await api.exportOpticsRecords([
      goodRecord({ prompt }),
      goodRecord({ span_id: "0000000000000002" }),
    ], {
      enabled: true,
      adapter: "otlp_traces",
      endpoint: "http://127.0.0.1:" + port + "/v1/traces",
      max_retries: 0,
    });
    assert.equal(result.exported, true);
    assert.equal(result.delivery.endpoint_origin, "http://127.0.0.1:" + port);
    assert.equal(result.delivery.path, "/v1/traces");
    assert.equal(seen.length, 1);
    assert.equal(seen[0].url, "/v1/traces");
    assert.equal(seen[0].headers["content-type"], "application/json");
    assert.equal(seen[0].headers.authorization, undefined);
    assert.equal(seen[0].headers.cookie, undefined);
    assert.equal(Number(seen[0].headers["content-length"]), Buffer.byteLength(seen[0].body));
    assert.equal(result.bytes_sent, Buffer.byteLength(seen[0].body));
    const parsed = JSON.parse(seen[0].body);
    assert.equal(parsed.resourceSpans[0].scopeSpans[0].spans.length, 1);
    assert.equal(parsed.resourceSpans[0].scopeSpans[0].spans[0].spanId, "0000000000000002");
    assert.equal(seen[0].body.includes(prompt), false);
    assertNoLeak(assert, result, [prompt]);
  } finally {
    await closeServer(server);
  }
});

test("redirects are not followed", async () => {
  let followed = 0;
  const sink = http.createServer((req, res) => {
    followed += 1;
    res.end("no");
  });
  const sinkPort = await listen(sink);
  const redirector = http.createServer((req, res) => {
    res.writeHead(302, { Location: "http://127.0.0.1:" + sinkPort + "/steal" });
    res.end();
  });
  const port = await listen(redirector);
  try {
    const result = await api.exportOpticsRecords([goodRecord()], {
      enabled: true,
      adapter: "otlp_traces",
      endpoint: "http://127.0.0.1:" + port,
      max_retries: 4,
    });
    assert.equal(result.reason, "EXPORTER_REJECTED");
    assert.equal(result.delivery.attempts, 1);
    assert.equal(result.exported, false);
    assert.equal(followed, 0);
  } finally {
    await closeServer(redirector);
    await closeServer(sink);
  }
});

test("a closed port is exporter unavailable and a stall stops at the timeout", async () => {
  const closed = http.createServer();
  const closedPort = await listen(closed);
  await closeServer(closed);
  const refused = await api.exportOpticsRecords([goodRecord()], {
    enabled: true,
    adapter: "otlp_traces",
    endpoint: "http://127.0.0.1:" + closedPort + "/v1/traces",
    max_retries: 0,
    timeout_ms: 200,
  });
  assert.equal(refused.reason, "EXPORTER_UNAVAILABLE");
  assert.equal(refused.delivery.attempts, 1);
  assert.equal(refused.bytes_sent, 0);
  assert.equal(refused.authority[0].operational, true);

  const stalled = http.createServer(() => {});
  const stalledPort = await listen(stalled);
  try {
    const timed = await api.exportOpticsRecords([goodRecord()], {
      enabled: true,
      adapter: "otlp_traces",
      endpoint: "http://127.0.0.1:" + stalledPort + "/v1/traces",
      max_retries: 0,
      timeout_ms: 50,
    });
    assert.equal(timed.reason, "EXPORTER_UNAVAILABLE");
    assert.equal(timed.delivery.attempts, 1);
    assert.deepEqual(timed.authority, refused.authority);
  } finally {
    await closeServer(stalled);
  }
});
