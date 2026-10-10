"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { execFileSync } = require("node:child_process");
const crypto = require("node:crypto");
const { attestObservation, canonicalEventBytes, createExporter } = require("../src/exporter.cjs");
const { PRODUCT_OTLP_EXPORT_AUTHORIZED, verifyExternalSourceSignature } = require("../src/source-signature.cjs");
const { startFromConfig } = require("../src/index.cjs");
const { loadConfig } = require("../src/config.cjs");
const { project } = require("../src/privacy.cjs");
const { acceptsVersion, SCHEMA_VERSION } = require("../src/schema.cjs");
const { tracesJson, tracesProto } = require("../src/otlp.cjs");

const DIGEST = `sha256:${"ab".repeat(32)}`;
const TRACE = "11".repeat(16);
const SPAN = "22".repeat(8);
const SPAN_B = "33".repeat(8);

function observation(extra = {}) {
  return {
    kind: "optics.observation",
    trace_id: TRACE,
    span_id: SPAN,
    destination_host: "api.openai.com",
    destination_port: 443,
    pid: 42,
    executable: "node",
    lineage: [{ pid: 1, executable: "init" }, { pid: 42, executable: "node" }],
    request_bytes: 12,
    response_bytes: null,
    duration_ms: 5,
    http_status: 204,
    optics_status: "SUCCESS",
    application_status: "SUCCESS",
    workload_id: "workload-a",
    coverage_state: "OBSERVED",
    path: "/v1/chat/completions?CANARY-QUERYSTRING=1",
    prompt: "CANARY-PROMPTTEXT",
    completion: "CANARY-COMPLETION",
    headers: { authorization: "CANARY-HEADERVALUE" },
    body: "CANARY-BODYTEXT",
    ...extra,
  };
}

function offer(exporter, event, token = exporter.token) {
  const attested = attestObservation(event);
  if (!attested.ok) throw new Error(attested.reason || "attest failed");
  return exporter.offer(event, token);
}

function listen(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

function otlpOk(res) {
  const body = Buffer.from("{}");
  res.writeHead(200, {
    "content-type": "application/json",
    "content-length": String(body.length),
  });
  res.end(body);
}

test("schema version is additive within major 1", () => {
  assert.equal(SCHEMA_VERSION, "1.0.0");
  assert.equal(acceptsVersion("1.0.0"), true);
  assert.equal(acceptsVersion("1.2.9"), true);
  assert.equal(acceptsVersion("2.0.0"), false);
  assert.equal(acceptsVersion("0.9.0"), false);
});

test("privacy projection drops prompts, bodies, headers, and query strings", () => {
  const projected = project(observation());
  assert.equal(projected.ok, true);
  const blob = JSON.stringify(projected.event);
  for (const canary of ["CANARY-PROMPTTEXT", "CANARY-COMPLETION", "CANARY-HEADERVALUE", "CANARY-BODYTEXT", "CANARY-QUERYSTRING"]) {
    assert.equal(blob.includes(canary), false, canary);
  }
  assert.equal(projected.event.path, "/v1/chat/completions");
  assert.equal(projected.event.response_bytes, null);
  assert.equal(projected.event.destination_host, "api.openai.com");
  assert.equal(projected.event.pid, 42);
});

test("phantom and enterprise events require a policy digest", () => {
  const missing = project({ ...observation(), kind: "phantom.decision", decision: "BLOCK" });
  assert.equal(missing.ok, false);
  const block = project({ ...observation(), kind: "phantom.decision", decision: "BLOCK", policy_digest: DIGEST, span_id: SPAN_B });
  assert.equal(block.ok, true);
  assert.equal(block.event.policy_digest, DIGEST);
  assert.equal(block.event.decision, "BLOCK");
  const evidence = project({ ...observation(), kind: "enterprise.evidence", policy_digest: DIGEST });
  assert.equal(evidence.ok, true);
});

test("otlp json carries schema version and shared trace context", () => {
  const events = [
    project(observation()).event,
    project({ ...observation(), kind: "phantom.decision", decision: "ALLOW", policy_digest: DIGEST, span_id: SPAN_B }).event,
  ];
  const body = JSON.stringify(tracesJson(events, 1000n));
  assert.match(body, /1\.0\.0/);
  assert.match(body, new RegExp(TRACE));
  assert.match(body, /phantom.decision/);
  assert.match(body, new RegExp(DIGEST));
  assert.equal(body.includes("CANARY-PROMPTTEXT"), false);
  const proto = tracesProto(events, 1000n);
  assert.ok(proto.includes(Buffer.from(TRACE, "hex")));
});

test("forged events are rejected and a down receiver does not throw", async () => {
  const config = {
    enabled: true,
    endpoint: "http://127.0.0.1:1",
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 5000,
    maxQueue: 3,
    timeoutMs: 100,
    jsonlPath: null,
    jsonlMaxBytes: 4096,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  };
  const exporter = createExporter(config);
  const forged = exporter.offer(observation(), "not-the-token");
  assert.equal(forged.accepted, false);
  assert.equal(forged.reason, "UNATTESTED");
  const unsigned = exporter.offer(observation(), exporter.token);
  assert.equal(unsigned.accepted, false);
  assert.equal(unsigned.reason, "UNATTESTED");
  const started = process.hrtime.bigint();
  const firstEvent = observation();
  assert.equal(attestObservation(firstEvent).ok, true);
  const first = exporter.offer(firstEvent, exporter.token);
  const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
  assert.equal(first.accepted, true);
  assert.ok(elapsedMs < 50, `offer took ${elapsedMs}ms`);
  offer(exporter, observation());
  offer(exporter, observation());
  const dropped = offer(exporter, observation());
  assert.equal(dropped.reason, "DROPPED");
  await exporter.flush();
  const status = exporter.status();
  assert.equal(status.queued <= 3, true);
  assert.equal(status.health, "down");
  assert.equal(status.rejected, 2);
  exporter.stop();
});

test("only the first config claim can send", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vantio-attest-"));
  const file = path.join(dir, "export.json");
  fs.writeFileSync(file, JSON.stringify({
    enabled: true,
    endpoint: "http://127.0.0.1:9",
    protocol: "otlp-http-json",
    allow_insecure_localhost: true,
    max_delay_ms: 5000,
  }));
  const started = startFromConfig(file);
  assert.equal(started.offer(observation()).accepted, true);
  const second = startFromConfig(file);
  assert.equal(second.offer(observation()).accepted, false);
  assert.equal(second.offer(observation()).reason, "UNATTESTED");
  started.stop();
});

test("a slow 500 receiver does not hang the caller", async () => {
  const server = await listen((_req, res) => {
    setTimeout(() => res.writeHead(500).end("no"), 5000);
  });
  const port = server.address().port;
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 8,
    maxDelayMs: 10,
    maxQueue: 8,
    timeoutMs: 80,
    jsonlPath: null,
    jsonlMaxBytes: 4096,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const started = Date.now();
  assert.equal(offer(exporter, observation()).accepted, true);
  await exporter.flush();
  assert.ok(Date.now() - started < 2000);
  assert.equal(exporter.status().health, "down");
  exporter.stop();
  server.close();
});

test("misconfigured TLS fails and does not fall back to plaintext", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vantio-tls-"));
  const key = path.join(dir, "key.pem");
  const cert = path.join(dir, "cert.pem");
  execFileSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-keyout", key, "-out", cert, "-days", "1", "-nodes", "-subj", "/CN=localhost"], { stdio: "ignore" });
  const server = https.createServer({ key: fs.readFileSync(key), cert: fs.readFileSync(cert) }, (_req, res) => {
    res.writeHead(200);
    res.end("ok");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  let plain = 0;
  const plainServer = net.createServer(() => {
    plain += 1;
  });
  await new Promise((resolve) => plainServer.listen(port + 1, "127.0.0.1", resolve));
  const exporter = createExporter({
    enabled: true,
    endpoint: `https://127.0.0.1:${port}/v1/traces`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 4,
    maxDelayMs: 10,
    maxQueue: 4,
    timeoutMs: 400,
    caFile: path.join(dir, "missing-ca.pem"),
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
  });
  offer(exporter, observation());
  await exporter.flush();
  assert.equal(exporter.status().health, "down");
  assert.equal(plain, 0);
  exporter.stop();
  server.close();
  plainServer.close();
});

test("a recovered receiver drains the queued events", async () => {
  const received = [];
  let accept = false;
  const server = await listen((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      if (!accept) {
        res.writeHead(500).end("down");
        return;
      }
      received.push(Buffer.concat(chunks).toString("utf8"));
      otlpOk(res);
    });
  });
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${server.address().port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 60000,
    maxQueue: 4,
    timeoutMs: 300,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const queued = observation({ workload_id: "queued-drain-marker", span_id: SPAN_B });
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  await exporter.flush();
  assert.equal(exporter.status().sent, 0);
  assert.equal(exporter.status().queued, 3);
  assert.equal(exporter.status().health, "down");
  accept = true;
  await exporter.flush({ drain: true, timeoutMs: 3000 });
  assert.equal(exporter.status().queued, 0);
  assert.equal(exporter.status().sent, 3);
  assert.equal(exporter.status().health, "healthy");
  const blob = received.join("\n");
  assert.equal(blob.includes("queued-drain-marker"), true);
  assert.equal(blob.includes("not-the-queued-event"), false);
  exporter.stop();
  server.close();
});

test("suspend holds the queue until the receiver is ready", async () => {
  const received = [];
  let accept = false;
  const server = await listen((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      if (!accept) {
        res.writeHead(500).end("down");
        return;
      }
      received.push(Buffer.concat(chunks).toString("utf8"));
      otlpOk(res);
    });
  });
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${server.address().port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 20,
    maxQueue: 4,
    timeoutMs: 200,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const queued = observation({ workload_id: "held-queue-marker", span_id: SPAN_B });
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  await exporter.flush();
  assert.equal(exporter.status().queued, 2);
  exporter.suspend();
  accept = true;
  await new Promise((resolve) => setTimeout(resolve, 80));
  assert.equal(exporter.status().sent, 0);
  assert.equal(exporter.status().queued, 2);
  exporter.resume();
  await exporter.flush({ drain: true, timeoutMs: 2000 });
  assert.equal(exporter.status().queued, 0);
  assert.equal(exporter.status().sent, 2);
  assert.equal(received.join("").includes("held-queue-marker"), true);
  exporter.stop();
  server.close();
});

test("resume delivers the held queue without another offer", async () => {
  const received = [];
  const server = await listen((req, res) => {
    req.resume();
    received.push("hit");
    otlpOk(res);
  });
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${server.address().port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 30,
    maxQueue: 4,
    timeoutMs: 300,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const queued = observation({ workload_id: "resume-marker", span_id: SPAN_B });
  exporter.suspend();
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  await new Promise((resolve) => setTimeout(resolve, 80));
  assert.equal(exporter.status().sent, 0);
  assert.equal(exporter.status().queued, 2);
  exporter.resume();
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.equal(exporter.status().queued, 0);
  assert.equal(exporter.status().sent, 2);
  assert.equal(received.length >= 1, true);
  exporter.stop();
  server.close();
});

test("suspend stops later batches of an in-flight pump", async () => {
  let hits = 0;
  const server = await listen((req, res) => {
    req.resume();
    hits += 1;
    setTimeout(() => {
      otlpOk(res);
    }, 120);
  });
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${server.address().port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 1,
    maxDelayMs: 60000,
    maxQueue: 4,
    timeoutMs: 1000,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const queued = observation({ workload_id: "batch-hold", span_id: SPAN_B });
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  assert.equal(offer(exporter, queued).accepted, true);
  await new Promise((resolve) => setTimeout(resolve, 30));
  exporter.suspend();
  await new Promise((resolve) => setTimeout(resolve, 400));
  assert.ok(hits > 0 && hits <= 2, `hits ${hits}`);
  assert.equal(exporter.status().sent, 1);
  assert.equal(exporter.status().queued, 2);
  exporter.stop();
  server.close();
});

test("failed grpc attempts release their sessions", async () => {
  const exporter = createExporter({
    enabled: true,
    endpoint: "http://127.0.0.1:1",
    protocol: "otlp-grpc",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 20,
    maxQueue: 2,
    timeoutMs: 100,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  const before = process.getActiveResourcesInfo().filter((row) => row.type === "TCPSocketWrap" || row.type === "HTTP2SESSION").length;
  for (let i = 0; i < 20; i += 1) {
    offer(exporter, observation({ span_id: SPAN_B }));
    await exporter.flush();
  }
  exporter.stop();
  await new Promise((resolve) => setTimeout(resolve, 50));
  const after = process.getActiveResourcesInfo().filter((row) => row.type === "TCPSocketWrap" || row.type === "HTTP2SESSION").length;
  assert.equal(exporter.status().health, "down");
  assert.equal(exporter.status().sent, 0);
  assert.ok(after <= before + 2, `sockets before ${before} after ${after}`);
});

test("sustained in-process projection stays bounded", () => {
  const before = process.memoryUsage();
  const started = process.hrtime.bigint();
  let ok = 0;
  for (let i = 0; i < 20000; i += 1) {
    const projected = project(observation({ span_id: SPAN }));
    if (projected.ok) ok += 1;
  }
  const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
  const after = process.memoryUsage();
  const rssDelta = after.rss - before.rss;
  assert.equal(ok, 20000);
  assert.ok(rssDelta < 64 * 1024 * 1024, `rss delta ${rssDelta}`);
  process.stdout.write(`THROUGHPUT projections=20000 elapsed_ms=${elapsedMs.toFixed(1)} rss_delta_bytes=${rssDelta}\n`);
});

test("inline headers and remote plaintext are refused", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vantio-cfg-"));
  const file = path.join(dir, "export.json");
  fs.writeFileSync(file, JSON.stringify({ enabled: true, endpoint: "http://example.com:4318", headers: { authorization: "secret" } }));
  assert.throws(() => loadConfig(file), /inline headers/);
  fs.writeFileSync(file, JSON.stringify({ enabled: true, endpoint: "http://example.com:4318" }));
  const refused = loadConfig(file);
  assert.equal(refused.enabled, false);
  assert.equal(refused.reason, "PLAINTEXT_REFUSED");
});

test("jsonl, syslog, and webhook share the schema and stay bounded", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vantio-siem-"));
  const jsonl = path.join(dir, "events.jsonl");
  const syslog = await new Promise((resolve) => {
    const socket = net.createServer((conn) => conn.on("data", () => {}));
    socket.listen(0, "127.0.0.1", () => resolve(socket));
  });
  const seen = [];
  const webhook = await listen((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      seen.push(Buffer.concat(chunks).toString("utf8"));
      res.writeHead(200);
      res.end("ok");
    });
  });
  const httpReceiver = await listen((req, res) => {
    req.resume();
    otlpOk(res);
  });
  const exporter = createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${httpReceiver.address().port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "gzip",
    maxBatch: 10,
    maxDelayMs: 10,
    maxQueue: 10,
    timeoutMs: 500,
    jsonlPath: jsonl,
    jsonlMaxBytes: 4096,
    syslog: `tcp://127.0.0.1:${syslog.address().port}`,
    webhook: `http://127.0.0.1:${webhook.address().port}/hook`,
    allowInsecureLocalhost: true,
  });
  offer(exporter, observation());
  offer(exporter, { ...observation(), kind: "enterprise.evidence", policy_digest: DIGEST, span_id: SPAN_B });
  await exporter.flush();
  const file = fs.readFileSync(jsonl, "utf8");
  assert.match(file, /"schema_version":"1\.0\.0"/);
  assert.match(file, new RegExp(DIGEST));
  assert.equal(file.includes("CANARY-PROMPTTEXT"), false);
  assert.equal(seen.length >= 1, true);
  assert.equal(seen.join("").includes("CANARY-BODYTEXT"), false);
  assert.equal(exporter.status().health, "healthy");
  exporter.stop();
  httpReceiver.close();
  webhook.close();
  syslog.close();
});

function exporterFor(port, extra = {}) {
  return createExporter({
    enabled: true,
    endpoint: `http://127.0.0.1:${port}`,
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 10,
    maxDelayMs: 60000,
    maxQueue: 4,
    timeoutMs: 400,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
    ...extra,
  });
}

test("an HTML 200 is not a delivered export", async () => {
  const server = await listen((req, res) => {
    req.resume();
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end("<!doctype html><html><body>jaeger</body></html>");
  });
  const exporter = exporterFor(server.address().port);
  assert.equal(offer(exporter, observation()).accepted, true);
  await exporter.flush();
  assert.equal(exporter.status().sent, 0);
  assert.equal(exporter.status().health, "down");
  assert.equal(exporter.status().lastError, "HTTP_NOT_OTLP");
  exporter.stop();
  server.close();
});

test("a JSON 200 that is not an OTLP export response is not delivery", async () => {
  const server = await listen((req, res) => {
    req.resume();
    const body = Buffer.from(JSON.stringify({ status: "ok", cluster_name: "docker-cluster" }));
    res.writeHead(200, { "content-type": "application/json", "content-length": String(body.length) });
    res.end(body);
  });
  const exporter = exporterFor(server.address().port);
  offer(exporter, observation());
  await exporter.flush();
  assert.equal(exporter.status().sent, 0);
  assert.equal(exporter.status().lastError, "HTTP_NOT_OTLP");
  exporter.stop();
  server.close();
});

test("external signature is checked before send and does not authorize export", async () => {
  assert.equal(PRODUCT_OTLP_EXPORT_AUTHORIZED, false);
  const { publicKey, privateKey } = crypto.generateKeyPairSync("ed25519");
  const der = publicKey.export({ format: "der", type: "spki" });
  const raw = der.subarray(der.length - 32);
  const bytes = canonicalEventBytes(project(observation()).event);
  const signature = crypto.sign(null, bytes, privateKey).toString("base64");
  const wrong = crypto.sign(null, Buffer.from("other-event"), privateKey).toString("base64");
  const server = await listen((req, res) => {
    req.resume();
    otlpOk(res);
  });
  const exporter = exporterFor(server.address().port, { externalTrust: { publicKey: raw } });
  const signed = (target, sig) => {
    const event = observation();
    assert.equal(attestObservation(event).ok, true);
    return target.offer(event, target.token, sig);
  };
  const missing = signed(exporter);
  assert.equal(missing.accepted, false);
  assert.equal(missing.reason, "SIGNATURE_REQUIRED");
  const invalid = signed(exporter, wrong);
  assert.equal(invalid.accepted, false);
  assert.equal(invalid.reason, "SIGNATURE_INVALID");
  const flipped = exporterFor(server.address().port, { externalTrust: { publicKey: raw, authorized: true } });
  assert.equal(signed(flipped, signature).reason, "UNAUTHORIZED");
  assert.equal(signed(exporter, signature).accepted, true);
  await exporter.flush();
  assert.equal(exporter.status().health, "healthy");
  assert.equal(exporter.status().sent, 1);
  const verified = verifyExternalSourceSignature(bytes, signature, raw);
  assert.equal(verified.ok, true);
  assert.equal(verified.authorized, false);
  assert.equal(PRODUCT_OTLP_EXPORT_AUTHORIZED, false);
  exporter.stop();
  flipped.stop();
  server.close();
});
