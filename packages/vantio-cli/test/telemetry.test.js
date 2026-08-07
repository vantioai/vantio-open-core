import { test, describe, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

// telemetry.cjs reads VANTIO_INGEST_URL fresh on every sendTelemetry() call
// (not cached at module-load time), so a single shared import is safe here —
// each test's env var changes take effect immediately on the next call.
const { sendTelemetry, telemetryDisabled } = await import("../bin/telemetry.cjs");

describe("telemetry.cjs — telemetryDisabled()", () => {
  const savedDisabled = process.env.VANTIO_TELEMETRY_DISABLED;
  const savedDnt = process.env.DO_NOT_TRACK;

  afterEach(() => {
    if (savedDisabled === undefined) delete process.env.VANTIO_TELEMETRY_DISABLED;
    else process.env.VANTIO_TELEMETRY_DISABLED = savedDisabled;
    if (savedDnt === undefined) delete process.env.DO_NOT_TRACK;
    else process.env.DO_NOT_TRACK = savedDnt;
  });

  test("false by default", () => {
    delete process.env.VANTIO_TELEMETRY_DISABLED;
    delete process.env.DO_NOT_TRACK;
    assert.equal(telemetryDisabled(), false);
  });

  test("true when VANTIO_TELEMETRY_DISABLED=1", () => {
    process.env.VANTIO_TELEMETRY_DISABLED = "1";
    delete process.env.DO_NOT_TRACK;
    assert.equal(telemetryDisabled(), true);
  });

  test("true when DO_NOT_TRACK=1", () => {
    delete process.env.VANTIO_TELEMETRY_DISABLED;
    process.env.DO_NOT_TRACK = "1";
    assert.equal(telemetryDisabled(), true);
  });
});

describe("telemetry.cjs — sendTelemetry()", () => {
  let server, baseUrl, received, homeDir, savedHome, savedIngest, savedDisabled;

  beforeEach(async () => {
    received = [];
    server = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => (body += c));
      req.on("end", () => {
        received.push({ url: req.url, body: body ? JSON.parse(body) : null });
        res.writeHead(202, { "content-type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
      });
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    baseUrl = `http://127.0.0.1:${server.address().port}`;

    homeDir = mkdtempSync(join(tmpdir(), "vantio-test-"));
    savedHome = process.env.HOME;
    savedIngest = process.env.VANTIO_INGEST_URL;
    savedDisabled = process.env.VANTIO_TELEMETRY_DISABLED;
    process.env.HOME = homeDir;
    process.env.VANTIO_INGEST_URL = baseUrl;
    delete process.env.VANTIO_TELEMETRY_DISABLED;
  });

  afterEach(async () => {
    await new Promise((resolve) => server.close(resolve));
    rmSync(homeDir, { recursive: true, force: true });
    if (savedHome === undefined) delete process.env.HOME;
    else process.env.HOME = savedHome;
    if (savedIngest === undefined) delete process.env.VANTIO_INGEST_URL;
    else process.env.VANTIO_INGEST_URL = savedIngest;
    if (savedDisabled === undefined) delete process.env.VANTIO_TELEMETRY_DISABLED;
    else process.env.VANTIO_TELEMETRY_DISABLED = savedDisabled;
  });

  test("posts only the allowlisted fields to /api/v1/telemetry", async () => {
    sendTelemetry({
      event: "run",
      hosts: ["api.openai.com"],
      callCount: 3,
      cliVersion: "0.3.0",
      // Deliberately not on the whitelist — must never appear on the wire.
      apiKey: "vk_live_should_never_be_sent",
      prompt: "this is definitely not telemetry",
    });

    // Fire-and-forget — give the in-flight request a moment to land.
    await new Promise((resolve) => setTimeout(resolve, 200));

    assert.equal(received.length, 1);
    assert.equal(received[0].url, "/api/v1/telemetry");
    const body = received[0].body;
    assert.equal(body.event, "run");
    assert.deepEqual(body.hosts, ["api.openai.com"]);
    assert.equal(body.callCount, 3);
    assert.equal(body.cliVersion, "0.3.0");
    assert.equal(body.runtime, "node");
    assert.ok(body.anonymousId);
    // The privacy contract: no field outside the whitelist ever rides along.
    assert.equal(body.apiKey, undefined);
    assert.equal(body.prompt, undefined);
  });

  test("never sends anything when telemetry is disabled", async () => {
    process.env.VANTIO_TELEMETRY_DISABLED = "1";
    sendTelemetry({ event: "run", hosts: ["api.openai.com"] });
    await new Promise((resolve) => setTimeout(resolve, 200));
    assert.equal(received.length, 0);
  });

  test("never throws when the endpoint is unreachable", () => {
    process.env.VANTIO_INGEST_URL = "http://127.0.0.1:1"; // reserved, connection refused
    assert.doesNotThrow(() => sendTelemetry({ event: "run" }));
  });
});
