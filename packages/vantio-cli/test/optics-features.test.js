import { test, describe, before, after } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import http from "node:http";
import http2 from "node:http2";
import dgram from "node:dgram";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync, symlinkSync } from "node:fs";
import { tmpdir, hostname } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const features = require("../bin/optics-features.cjs");
const proc = require("../bin/optics-proc.cjs");
const grpc = require("../bin/optics-otlp-grpc.cjs");
const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI = join(__dirname, "..", "bin", "vantio.js");
const CANARY = "PROMPT-CANARY";
const SECRET = "secret-canary";
const TOKEN = "webhook-token-canary";

function runCli(args, env = {}) {
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [CLI, ...args], {
      env: { PATH: process.env.PATH, ...env },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.on("close", (code) => resolve({ code, stdout, stderr }));
  });
}

function listenHttp(handler) {
  const server = http.createServer(handler);
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

function writeJson(path, value) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
}

function fixtureHome() {
  const home = mkdtempSync(join(tmpdir(), "vantio-optics-"));
  const runs = join(home, ".vantio", "runs");
  mkdirSync(runs, { recursive: true });
  const host = hostname();
  writeJson(join(runs, "agent.json"), {
    vantio_run_log: "1",
    trace_id: "0xa1b2c3d4e5f60718",
    program: "agent.js",
    system_hostname: host,
    pid: 42,
    ppid: 7,
    runtime: "node",
    started_at: "2026-10-21T14:02:01.000Z",
    generated_at: "2026-10-21T14:02:08.000Z",
    calls: [
      {
        hostname: `user:${SECRET}@billing.internal.example`,
        method: "POST",
        path: `/v1/tools?token=${SECRET}`,
        bytes: 1840,
        status: 200,
        ts: "2026-10-21T14:02:07.000Z",
        prompt: CANARY,
        completion: "COMPLETION-CANARY",
        authorization: "Bearer SECRET",
        mediation: "node_http",
      },
      {
        hostname: "billing.internal.example",
        method: "POST",
        path: "/v1/tools",
        bytes: 10,
        status: 200,
        ts: "2026-10-21T14:03:07.000Z",
      },
      {
        hostname: "api.openai.example",
        method: "POST",
        path: "/v1/chat/completions",
        bytes: 20,
        status: 200,
        ts: "2026-10-21T14:04:00.000Z",
      },
      {
        hostname: "a.b.openai.example",
        method: "POST",
        path: "/v1/chat/completions",
        bytes: 30,
        status: 500,
        ts: "2026-10-21T14:05:00.000Z",
      },
      {
        hostname: "203.0.113.50",
        method: "GET",
        path: "/",
        bytes: 40,
        status: 200,
        ts: "2026-10-21T14:06:00.000Z",
        mediation: "node_curl",
      },
    ],
  });
  writeJson(join(runs, "assistant.json"), {
    vantio_run_log: "1",
    trace_id: "0xbbbbbbbbbbbbbbbb",
    program: "assistant.py",
    system_hostname: host,
    pid: 77,
    runtime: "python",
    started_at: "2026-10-21T14:02:11.000Z",
    generated_at: "2026-10-21T14:02:12.000Z",
    calls: [
      {
        hostname: "203.0.113.50",
        method: "POST",
        path: "/v1/responses",
        bytes: 50,
        status: 200,
        ts: "2026-10-21T14:02:11.000Z",
      },
    ],
  });
  writeJson(join(runs, "notes.json"), { hello: "not a run" });
  const mcp = [
    { schema: "vantio.mcp_observation.v1", tool_name: "tools/read", method: "tools/call", prompt: CANARY },
    { schema: "vantio.mcp_observation.v1", tool_name: "tools/write", method: "tools/call" },
    { schema: "vantio.mcp_observation.v1", tool_hmac: "abcd", method_hmac: "ef" },
  ];
  writeFileSync(join(home, ".vantio", "mcp-observations.jsonl"), `${mcp.map((row) => JSON.stringify(row)).join("\n")}\n`);
  writeJson(join(home, ".vantio", "allowlist.json"), {
    schema: "vantio.optics.allowlist.v1",
    destinations: ["billing.internal.example", "*.openai.example"],
    mcp_tools: ["tools/read"],
    alert_on_allowlist: false,
  });
  return home;
}

describe("optics feature functions", () => {
  test("a wrapped process with no calls is still on the map", () => {
    const collected = features.collectObservations([{
      vantio_run_log: "1",
      program: "idle.js",
      trace_id: "0xidle",
      pid: 9,
      started_at: "2026-10-21T14:00:00.000Z",
      system_hostname: "box",
      calls: [],
    }], [], "box", null);
    const coverage = features.buildCoverage({
      observations: collected.observations,
      allowlist: features.parseAllowlist({}).allowlist,
      localHost: "box",
      platform: "linux",
    });
    assert.equal(coverage.counts.processes, 1);
    assert.equal(coverage.counts.connections, 0);
    assert.equal(coverage.processes[0].program, "idle.js");
    assert.equal(coverage.processes[0].covered, true);
    const events = features.buildExportBundle(collected.observations, [], features.parseAllowlist({}).allowlist);
    assert.equal(events.length, 0);
  });

  test("program label is the script basename", () => {
    assert.equal(features.programLabelFromArgv(["node", "/tmp/secret/agent.js", "--token", SECRET]), "agent.js");
    assert.equal(features.programLabelFromArgv(["node", "-e", "console.log(1)"]), "node");
    assert.equal(features.programLabelFromArgv(["python", "-m", "agent"]), "agent");
  });

  test("allowlist accepts hosts and tool names and rejects unknown fields", () => {
    const parsed = features.parseAllowlist({
      schema: "vantio.optics.allowlist.v1",
      destinations: ["Billing.Internal.Example", { destination: "*.openai.example", alert: true }],
      mcp_tools: [{ name: "tools/read", alert: false }],
    });
    assert.equal(parsed.error, undefined);
    assert.equal(parsed.allowlist.destinations[0].destination, "billing.internal.example");
    assert.equal(parsed.allowlist.destinations[1].alert, true);
    assert.equal(features.parseAllowlist({ hosts: [] }).error, "unknown field 'hosts'");
    assert.match(features.parseAllowlist({ destinations: ["*"] }).error, /not an allowlist entry/);
  });

  test("wildcard matches one label", () => {
    const parsed = features.parseAllowlist({ destinations: ["*.openai.example"] });
    const one = { kind: "connection", destination: "api.openai.example", display: "api.openai.example" };
    const two = { kind: "connection", destination: "a.b.openai.example", display: "a.b.openai.example" };
    const coverage = features.buildCoverage({
      observations: [
        { ...one, seq: 1, program: "agent.js", system_hostname: "box", host_recorded: true, time: "2026-10-21T14:04:00.000Z", bytes: 1 },
        { ...two, seq: 2, program: "agent.js", system_hostname: "box", host_recorded: true, time: "2026-10-21T14:05:00.000Z", bytes: 1 },
      ],
      allowlist: parsed.allowlist,
      localHost: "box",
      platform: "linux",
    });
    const system = coverage.systems[0];
    assert.deepEqual(system.under_authority.map((row) => row.destination), ["api.openai.example"]);
    assert.deepEqual(system.outside_authority.map((row) => row.destination), ["a.b.openai.example"]);
  });

  test("first connection flags once per program, and the allowlist can suppress it", () => {
    const allowlist = features.parseAllowlist({
      destinations: ["billing.internal.example"],
      mcp_tools: ["tools/read"],
      alert_on_allowlist: false,
    }).allowlist;
    const observations = [
      { seq: 1, kind: "connection", program: "agent.js", destination: "billing.internal.example", display: "billing.internal.example", time: "2026-10-21T14:02:07.000Z", trace_id: "0xa1" },
      { seq: 2, kind: "connection", program: "agent.js", destination: "billing.internal.example", display: "billing.internal.example", time: "2026-10-21T14:03:07.000Z", trace_id: "0xa1" },
      { seq: 3, kind: "connection", program: "assistant.py", destination: "203.0.113.50", display: "203.0.113.50", time: "2026-10-21T14:02:11.000Z", trace_id: "0xb" },
      { seq: 4, kind: "mcp_tool", program: "mcp", destination: "tools/read", display: "mcp tools/read", tool_name_retained: true, time: null },
    ];
    const first = features.evaluateNewDestinations(observations, [], allowlist);
    assert.deepEqual(first.alerts.map((alert) => alert.destination), ["203.0.113.50"]);
    assert.equal(first.alerts[0].flag_label, "New destination");
    assert.equal(first.alerts[0].program, "assistant.py");
    const second = features.evaluateNewDestinations(observations, first.pairs, allowlist);
    assert.deepEqual(second.alerts, []);
    const loud = features.parseAllowlist({
      destinations: ["billing.internal.example"],
      alert_on_allowlist: true,
    }).allowlist;
    const flagged = features.evaluateNewDestinations(observations, [], loud);
    assert.ok(flagged.alerts.some((alert) => alert.destination === "billing.internal.example" && alert.authority === "under_authority"));
  });

  test("export projection drops prompts, completions, and query strings", () => {
    const observations = features.collectObservations([
      {
        vantio_run_log: "1",
        trace_id: "0xa1b2c3d4e5f60718",
        program: "agent.js",
        system_hostname: "box",
        calls: [{
          hostname: `user:${SECRET}@billing.internal.example`,
          path: `/v1/tools?token=${SECRET}`,
          method: "POST",
          bytes: 1840,
          status: 200,
          ts: "2026-10-21T14:02:07.000Z",
          prompt: CANARY,
          completion: "COMPLETION-CANARY",
          authorization: "Bearer SECRET",
        }],
      },
    ], [], "box", null).observations;
    const evaluated = features.evaluateNewDestinations(observations, [], features.parseAllowlist({}).allowlist);
    const events = features.buildExportBundle(observations, evaluated.alerts, features.parseAllowlist({}).allowlist);
    const encoded = JSON.stringify(events) + features.formatJsonLines(events) + features.formatSyslogLines(events, { hostname: "box" });
    assert.equal(events[0].path, "/v1/tools");
    assert.equal(events[0].destination, "billing.internal.example");
    assert.equal(events[0].flag, "new_destination");
    assert.equal(events[1].kind, "new_destination");
    assert.equal(events.filter((event) => event.flag === "new_destination" && event.kind === "observation").length, 1);
    assert.doesNotMatch(encoded, new RegExp(CANARY));
    assert.doesNotMatch(encoded, new RegExp(SECRET));
    assert.doesNotMatch(encoded, /COMPLETION-CANARY/);
    assert.doesNotMatch(encoded, /Bearer/);
    const payloads = features.otlpPayloads(events, { hostname: "box", platform: "linux", machineId: null });
    const otlp = JSON.stringify(payloads);
    assert.equal(payloads.traces.resourceSpans[0].scopeSpans[0].spans[0].traceId.length, 32);
    assert.notEqual(payloads.traces.resourceSpans[0].scopeSpans[0].spans[0].traceId, "0xa1b2c3d4e5f60718");
    assert.equal(payloads.metrics.resourceMetrics[0].scopeMetrics[0].metrics[0].gauge.dataPoints[0].asInt, "1840");
    assert.match(otlp, /0xa1b2c3d4e5f60718/);
    assert.doesNotMatch(otlp, new RegExp(CANARY));
    assert.match(features.formatSyslogLines(events, { hostname: "box" }), /^<\d+>1 /);
  });

  test("plaintext export URLs stay on loopback", () => {
    assert.throws(() => features.assertExportUrl("http://203.0.113.50/hook", "webhook"), /plaintext/);
    assert.throws(() => features.assertExportUrl("http://user:pass@127.0.0.1/hook", "webhook"), /credentials/);
    assert.equal(features.assertExportUrl("https://collector.example/optics", "webhook").protocol, "https:");
    assert.equal(features.assertExportUrl("http://127.0.0.1:4318", "otlp").hostname, "127.0.0.1");
    assert.deepEqual(features.validateWebhookToken(`bad\n${TOKEN}`), { error: "webhook token is not valid" });
  });
});

describe("vantio coverage, destinations, and export", () => {
  let home;

  before(() => {
    home = fixtureHome();
  });

  after(() => {
    rmSync(home, { recursive: true, force: true });
  });

  test("coverage text and JSON list covered and outside paths without the prompt", async () => {
    const text = await runCli(["coverage"], { HOME: home });
    assert.equal(text.code, 0, text.stderr);
    assert.match(text.stdout, /Under authority/);
    assert.match(text.stdout, /billing\.internal\.example/);
    assert.match(text.stdout, /mcp tools\/read/);
    assert.match(text.stdout, /These paths are on the list a person approved/);
    assert.match(text.stdout, /Outside authority/);
    assert.match(text.stdout, /203\.0\.113\.50/);
    assert.match(text.stdout, /a\.b\.openai\.example/);
    assert.match(text.stdout, /mcp tools\/write/);
    assert.match(text.stdout, /These paths are still outside that list/);
    assert.match(text.stdout, /curl, from agent\.js/);
    assert.match(text.stdout, /Browser paths stay outside this wrap/);
    assert.doesNotMatch(text.stdout, new RegExp(CANARY));
    assert.doesNotMatch(text.stdout, new RegExp(SECRET));
    assert.equal(existsSync(join(home, ".vantio", "seen-destinations.json")), false);

    const json = await runCli(["coverage", "--json"], { HOME: home });
    assert.equal(json.code, 0, json.stderr);
    const body = JSON.parse(json.stdout);
    assert.equal(body.schema_status, "unstable-pre-1.0");
    assert.equal(body.schema, "vantio.optics.coverage.v1");
    assert.equal(body.command, "coverage");
    assert.equal(body.system.scope, "this_system");
    assert.equal(body.system.hostname, hostname());
    const system = body.systems.find((row) => row.hostname === hostname());
    const recorded = (rows) => rows.filter((row) => row.source !== "proc").map((row) => row.destination).sort();
    const under = recorded(system.under_authority);
    const outside = recorded(system.outside_authority);
    assert.deepEqual(under, ["api.openai.example", "billing.internal.example", "mcp tools/read"]);
    assert.deepEqual(outside, ["203.0.113.50", "a.b.openai.example", "mcp (tool name not retained)", "mcp tools/write"]);
    assert.ok(body.not_covered.some((row) => row.id === "browser"));
    assert.ok(body.processes.some((row) => row.program === "curl" && row.parent_program === "agent.js" && row.covered === true));
    const billing = body.connections.find((row) => row.destination === "billing.internal.example");
    assert.equal(billing.path, "/v1/tools");
    assert.equal(billing.authority, "under_authority");
    assert.doesNotMatch(json.stdout, new RegExp(CANARY));
    assert.doesNotMatch(json.stdout, new RegExp(SECRET));
  });

  test("destinations flags the first unseen destination and then stays quiet", async () => {
    const fresh = fixtureHome();
    try {
      const first = await runCli(["destinations", "--json"], { HOME: fresh });
      assert.equal(first.code, 0, first.stderr);
      const body = JSON.parse(first.stdout);
      const destinations = body.alerts.map((alert) => `${alert.program} ${alert.destination}`).sort();
      assert.deepEqual(destinations, [
        "agent.js 203.0.113.50",
        "agent.js a.b.openai.example",
        "assistant.py 203.0.113.50",
        "mcp mcp tools/write",
      ]);
      assert.equal(body.alerts[0].flag_label, "New destination");
      assert.equal(existsSync(join(fresh, ".vantio", "seen-destinations.json")), true);
      const second = await runCli(["destinations"], { HOME: fresh });
      assert.equal(second.code, 0, second.stderr);
      assert.match(second.stdout, /No new destination/);
      const dry = fixtureHome();
      const dryRun = await runCli(["destinations", "--dry-run", "--json"], { HOME: dry });
      assert.equal(dryRun.code, 0, dryRun.stderr);
      assert.equal(JSON.parse(dryRun.stdout).alerts.length, 4);
      assert.equal(existsSync(join(dry, ".vantio", "seen-destinations.json")), false);
      rmSync(dry, { recursive: true, force: true });
    } finally {
      rmSync(fresh, { recursive: true, force: true });
    }
  });

  test("export sends OTLP, JSON lines, and a webhook, and fails closed", async () => {
    const fresh = fixtureHome();
    const hits = [];
    const server = await listenHttp((req, res) => {
      const chunks = [];
      req.on("data", (chunk) => chunks.push(chunk));
      req.on("end", () => {
        hits.push({
          url: req.url,
          authorization: req.headers.authorization || "",
          body: Buffer.concat(chunks).toString("utf8"),
        });
        if (req.url === "/fail") {
          res.writeHead(500);
          res.end("no");
          return;
        }
        res.writeHead(200);
        res.end("ok");
      });
    });
    const udpMessages = [];
    const udp = dgram.createSocket("udp4");
    await new Promise((resolve) => udp.bind(0, "127.0.0.1", resolve));
    udp.on("message", (buf) => udpMessages.push(buf.toString("utf8")));
    const port = server.address().port;
    const udpPort = udp.address().port;
    const jsonl = join(fresh, "optics.jsonl");
    try {
      const denied = await runCli(["export", "--otlp=http://203.0.113.50:4318"], { HOME: fresh });
      assert.equal(denied.code, 1);
      assert.match(denied.stderr, /vantio export: otlp refuses plaintext to a remote host/);
      assert.equal(existsSync(join(fresh, ".vantio", "seen-destinations.json")), false);

      const missing = await runCli(["export"], { HOME: fresh });
      assert.equal(missing.code, 1);
      assert.match(missing.stderr, /vantio export: no destination/);

      const sent = await runCli([
        "export",
        `--otlp=http://127.0.0.1:${port}`,
        `--webhook=http://127.0.0.1:${port}/hook`,
        `--jsonl=${jsonl}`,
        `--syslog=udp://127.0.0.1:${udpPort}`,
        "--json",
      ], { HOME: fresh, VANTIO_EXPORT_WEBHOOK_TOKEN: TOKEN });
      assert.equal(sent.code, 0, sent.stderr);
      assert.doesNotMatch(sent.stdout, new RegExp(TOKEN));
      assert.doesNotMatch(sent.stderr, new RegExp(TOKEN));
      assert.doesNotMatch(sent.stdout, new RegExp(CANARY));
      const summary = JSON.parse(sent.stdout);
      assert.equal(summary.delivered, true);
      assert.ok(summary.alerts >= 4);
      const paths = hits.map((hit) => hit.url).sort();
      assert.deepEqual(paths, ["/hook", "/v1/logs", "/v1/metrics", "/v1/traces"]);
      const webhook = hits.find((hit) => hit.url === "/hook");
      assert.equal(webhook.authorization, `Bearer ${TOKEN}`);
      assert.doesNotMatch(webhook.body, new RegExp(CANARY));
      assert.doesNotMatch(webhook.body, new RegExp(SECRET));
      assert.match(webhook.body, /New destination/);
      const traces = hits.find((hit) => hit.url === "/v1/traces");
      assert.equal(traces.authorization, "");
      assert.match(traces.body, /0xa1b2c3d4e5f60718/);
      const metrics = JSON.parse(hits.find((hit) => hit.url === "/v1/metrics").body);
      const points = metrics.resourceMetrics[0].scopeMetrics[0].metrics[0].gauge.dataPoints;
      assert.ok(points.some((point) => point.asInt === "1850" || point.asInt === "1840"));
      const lines = readFileSync(jsonl, "utf8").trim().split("\n");
      assert.ok(lines.length >= 4);
      assert.doesNotMatch(lines.join("\n"), new RegExp(CANARY));
      const udpDeadline = Date.now() + 1000;
      while (!udpMessages.join("").includes("203.0.113.50") && Date.now() < udpDeadline) {
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      assert.match(udpMessages[0], /^<\d+>1 /);
      assert.match(udpMessages.join(""), /203\.0\.113\.50/);

      const again = await runCli(["export", `--jsonl=${join(fresh, "second.jsonl")}`, "--json"], { HOME: fresh });
      assert.equal(again.code, 0, again.stderr);
      assert.equal(JSON.parse(again.stdout).alerts, 0);

      const failedHome = fixtureHome();
      const failedJsonl = join(failedHome, "should-not-exist.jsonl");
      const broken = await runCli(["export", `--webhook=http://127.0.0.1:${port}/fail`, `--jsonl=${failedJsonl}`], {
        HOME: failedHome,
        VANTIO_EXPORT_WEBHOOK_TOKEN: TOKEN,
      });
      assert.equal(broken.code, 1);
      assert.match(broken.stderr, /vantio export: webhook returned 500/);
      assert.doesNotMatch(broken.stderr, new RegExp(TOKEN));
      assert.equal(existsSync(join(failedHome, ".vantio", "seen-destinations.json")), false);
      assert.equal(existsSync(failedJsonl), false);
      rmSync(failedHome, { recursive: true, force: true });
    } finally {
      server.close();
      udp.close();
      rmSync(fresh, { recursive: true, force: true });
    }
  });

  test("a narrow window does not treat an older destination as new", async () => {
    const fresh = mkdtempSync(join(tmpdir(), "vantio-window-"));
    const runs = join(fresh, ".vantio", "runs");
    mkdirSync(runs, { recursive: true });
    writeJson(join(runs, "old.json"), {
      vantio_run_log: "1",
      trace_id: "0xold",
      program: "agent.js",
      system_hostname: hostname(),
      pid: 1,
      started_at: "2020-01-01T00:00:00.000Z",
      generated_at: "2020-01-01T00:00:01.000Z",
      calls: [{ hostname: "old.example", method: "POST", path: "/v1", bytes: 1, status: 200, ts: "2020-01-01T00:00:01.000Z" }],
    });
    writeJson(join(runs, "new.json"), {
      vantio_run_log: "1",
      trace_id: "0xnew",
      program: "agent.js",
      system_hostname: hostname(),
      pid: 2,
      started_at: new Date().toISOString(),
      generated_at: new Date().toISOString(),
      calls: [{ hostname: "old.example", method: "POST", path: "/v1", bytes: 1, status: 200, ts: new Date().toISOString() }],
    });
    try {
      const narrow = await runCli(["destinations", "--since=24h", "--json"], { HOME: fresh });
      assert.equal(narrow.code, 0, narrow.stderr);
      assert.deepEqual(JSON.parse(narrow.stdout).alerts, []);
      const seen = JSON.parse(readFileSync(join(fresh, ".vantio", "seen-destinations.json"), "utf8"));
      assert.ok(seen.pairs.some((pair) => pair.destination === "old.example"));
    } finally {
      rmSync(fresh, { recursive: true, force: true });
    }
  });

  test("VANTIO_HOME is the record, allowlist, and seen directory", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-home-"));
    const vantioHome = mkdtempSync(join(tmpdir(), "vantio-alt-"));
    mkdirSync(join(vantioHome, "runs"), { recursive: true });
    writeJson(join(vantioHome, "runs", "agent.json"), {
      vantio_run_log: "1",
      trace_id: "0xhome",
      program: "agent.js",
      system_hostname: hostname(),
      pid: 3,
      started_at: "2026-10-21T14:02:01.000Z",
      generated_at: "2026-10-21T14:02:08.000Z",
      calls: [{ hostname: "billing.internal.example", method: "POST", path: "/v1/tools", bytes: 4, status: 200, ts: "2026-10-21T14:02:07.000Z" }],
    });
    writeJson(join(vantioHome, "allowlist.json"), {
      schema: "vantio.optics.allowlist.v1",
      destinations: ["billing.internal.example"],
    });
    try {
      const coverage = await runCli(["coverage", "--json"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(coverage.code, 0, coverage.stderr);
      const body = JSON.parse(coverage.stdout);
      const recorded = body.connections.filter((row) => row.source !== "proc");
      assert.equal(recorded.length, 1);
      assert.equal(recorded[0].authority, "under_authority");
      const flagged = await runCli(["destinations", "--json"], { HOME: home, VANTIO_HOME: vantioHome });
      assert.equal(flagged.code, 0, flagged.stderr);
      assert.deepEqual(JSON.parse(flagged.stdout).alerts, []);
      assert.equal(existsSync(join(vantioHome, "seen-destinations.json")), true);
      assert.equal(existsSync(join(home, ".vantio", "seen-destinations.json")), false);
    } finally {
      rmSync(home, { recursive: true, force: true });
      rmSync(vantioHome, { recursive: true, force: true });
    }
  });

  test("bad records and allowlists fail the command", async () => {
    const fresh = fixtureHome();
    try {
      writeFileSync(join(fresh, ".vantio", "runs", "broken.json"), "{");
      const broken = await runCli(["coverage"], { HOME: fresh });
      assert.equal(broken.code, 1);
      assert.match(broken.stderr, /vantio coverage: could not read /);
      const missing = await runCli(["coverage", "--allowlist=/no/such/allowlist.json"], { HOME: fresh });
      assert.equal(missing.code, 1);
      assert.match(missing.stderr, /allowlist file not found/);
    } finally {
      rmSync(fresh, { recursive: true, force: true });
    }
  });
});

describe("live destination, follow, proc, and grpc", () => {
  test("the clock is local HH:MM:SS and a live call flags once", () => {
    assert.equal(features.localClock(new Date(2026, 9, 21, 14, 2, 7)), "14:02:07");
    const home = mkdtempSync(join(tmpdir(), "vantio-live-"));
    const previous = process.env.VANTIO_HOME;
    process.env.VANTIO_HOME = home;
    try {
      const first = features.noteLiveCall({
        hostname: "billing.internal.example",
        method: "POST",
        path: `/v1/tools?token=${SECRET}`,
        bytes: 1840,
        status: 200,
        ts: "2026-10-21T18:02:07.000Z",
        prompt: CANARY,
      }, { program: "agent.js", trace_id: "0xa1b2c3d4e5f60718", pid: 42 });
      assert.equal(first.flag, "new_destination");
      assert.match(first.clock, /^\d{2}:\d{2}:\d{2}$/);
      assert.match(features.formatLiveAlert(first), /New destination/);
      assert.match(features.formatLiveAlert(first), /First connection: \d{2}:\d{2}:\d{2}/);
      assert.match(features.formatLiveAlert(first), /billing\.internal\.example/);
      assert.match(features.formatLiveAlert(first), /agent\.js/);
      const second = features.noteLiveCall({
        hostname: "billing.internal.example",
        method: "POST",
        path: "/v1/tools",
        ts: "2026-10-21T18:03:07.000Z",
      }, { program: "agent.js", trace_id: "0xa1b2c3d4e5f60718", pid: 42 });
      assert.equal(second.flag, null);
      const journal = readFileSync(features.liveJournalPath(), "utf8");
      assert.doesNotMatch(journal, new RegExp(CANARY));
      assert.doesNotMatch(journal, new RegExp(SECRET));
      const buffer = features.createFollowBuffer(2);
      assert.equal(buffer.push({ n: 1 }), 0);
      assert.equal(buffer.push({ n: 2 }), 0);
      assert.equal(buffer.push({ n: 3 }), 1);
      assert.deepEqual(buffer.drain(), [{ n: 2 }, { n: 3 }]);
      assert.equal(features.backoffMs(0), 250);
      assert.equal(features.backoffMs(10), 10000);
    } finally {
      if (previous == null) delete process.env.VANTIO_HOME;
      else process.env.VANTIO_HOME = previous;
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("a wrapped process tree records outbound sockets for new-destination checks", () => {
    const root = mkdtempSync(join(tmpdir(), "vantio-wrap-proc-"));
    const previous = process.env.VANTIO_HOME;
    const home = mkdtempSync(join(tmpdir(), "vantio-wrap-home-"));
    process.env.VANTIO_HOME = home;
    try {
      mkdirSync(join(root, "net"), { recursive: true });
      mkdirSync(join(root, "11", "fd"), { recursive: true });
      mkdirSync(join(root, "12", "fd"), { recursive: true });
      writeFileSync(join(root, "11", "stat"), "11 (bash) S 1 0 0\n");
      writeFileSync(join(root, "11", "cmdline"), "bash\0-c\0curl\0");
      writeFileSync(join(root, "12", "stat"), "12 (curl) S 11 0 0\n");
      writeFileSync(join(root, "12", "cmdline"), "curl\0");
      writeFileSync(join(root, "net", "tcp"), "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n   0: 0100007F:3039 327100CB:01BB 01 00000000:00000000 00:00000000 00000000     0        0 4242 1 0000000000000000 100 0 0 10 0\n");
      symlinkSync("socket:[4242]", join(root, "12", "fd", "3"));
      writeFileSync(join(root, "hosts"), "203.0.113.50 example.test\n");
      const snap = proc.sampleWrappedTree(root, 11, readFileSync(join(root, "hosts"), "utf8"));
      assert.deepEqual(snap.processes.map((item) => item.program).sort(), ["bash", "curl"]);
      assert.equal(snap.connections.length, 1);
      assert.equal(snap.connections[0].destination, "example.test");
      assert.equal(snap.connections[0].program, "curl");
      snap.connections.push({
        pid: 11,
        ppid: 1,
        program: "bash",
        destination: "example.test",
        port: 443,
      });
      snap.connections.push({
        pid: 11,
        ppid: 1,
        program: "bash",
        destination: "other.test",
        port: 80,
      });
      const noted = [];
      const sampler = proc.createWrapSampler({
        procRoot: root,
        rootPid: 11,
        hostsPath: join(root, "hosts"),
        intervalMs: 0,
        onConnection: (conn) => noted.push(conn.program),
      });
      const stopped = sampler.stop();
      assert.deepEqual(noted, ["curl"]);
      assert.equal(stopped.connections.length, 1);
      assert.doesNotThrow(() => {
        proc.createWrapSampler({
          procRoot: root,
          rootPid: 11,
          hostsPath: join(root, "hosts"),
          intervalMs: 0,
          onConnection: () => { throw new Error("boom"); },
        }).stop();
      });
      const live = features.noteWrappedSocket(snap.connections[0], {
        trace_id: "0xwraptree",
        system_hostname: "box",
      });
      assert.equal(live.flag, "new_destination");
      assert.equal(live.program, "curl");
      assert.equal(live.destination, "example.test");
      assert.match(features.formatLiveAlert(live), /New destination/);
      assert.match(features.formatLiveAlert(live), /example\.test/);
      const repeat = features.noteWrappedSocket(snap.connections[0], {
        trace_id: "0xwraptree",
        system_hostname: "box",
      });
      assert.equal(repeat.flag, null);
      const journal = readFileSync(features.liveJournalPath(), "utf8");
      assert.doesNotMatch(journal, /prompt|completion|authorization/i);
      const written = features.recordWrappedRun({
        traceId: "0xwraptree",
        program: "bash",
        pid: 11,
        ppid: 1,
        startedAt: "2026-10-21T14:02:01.000Z",
        processes: snap.processes,
        connections: snap.connections,
      });
      assert.equal(written.log.vantio_run_log, "1");
      const curlCall = written.log.calls.find((call) => call.hostname === "example.test");
      assert.equal(curlCall.mediation, "proc_socket");
      assert.equal(curlCall.program, "curl");
      assert.equal(curlCall.pid, 12);
      assert.equal(written.log.calls.some((call) => call.hostname === "other.test" && call.program === "bash"), true);
      const observations = features.collectObservations([written.log], [], "box", null).observations;
      const flags = features.evaluateNewDestinations(observations, [], features.parseAllowlist({}).allowlist);
      const byDest = new Map(flags.alerts.map((alert) => [alert.destination, alert.program]));
      assert.equal(byDest.get("example.test"), "curl");
      assert.equal(byDest.get("other.test"), "bash");
      const coverage = features.buildCoverage({
        observations,
        allowlist: features.parseAllowlist({}).allowlist,
        localHost: "box",
        platform: "linux",
      });
      assert.ok(coverage.processes.some((row) => row.program === "bash" && row.covered === true && row.pid === 11));
      assert.ok(coverage.processes.some((row) => row.program === "curl" && row.parent_program === "bash" && row.covered === true && row.pid === 12));
      assert.ok(coverage.connections.some((row) => row.destination === "example.test" && row.program === "curl" && row.pid === 12));
      const again = features.recordWrappedRun({
        traceId: "0xwraptree",
        program: "bash",
        pid: 11,
        ppid: 1,
        startedAt: "2026-10-21T14:02:01.000Z",
        processes: snap.processes,
        connections: snap.connections,
      });
      assert.equal(again.log.calls.length, 2);
      mkdirSync(join(home, "runs"), { recursive: true });
      writeFileSync(join(home, "runs", "0xmerge.json"), `${JSON.stringify({
        vantio_run_log: "1",
        trace_id: "0xmerge",
        program: "agent.js",
        pid: 11,
        calls: [{
          hostname: "example.test",
          mediation: "node_http",
          method: "POST",
          path: "/v1",
          bytes: 4,
          status: 200,
          ts: "2026-10-21T14:02:07.000Z",
        }],
      })}\n`);
      const merged = features.recordWrappedRun({
        traceId: "0xmerge",
        program: "bash",
        pid: 11,
        ppid: 1,
        startedAt: "2026-10-21T14:02:01.000Z",
        processes: snap.processes,
        connections: snap.connections,
      });
      assert.equal(merged.log.program, "agent.js");
      assert.equal(merged.log.calls.length, 2);
      assert.equal(merged.log.calls.find((call) => call.hostname === "example.test").mediation, "node_http");
      assert.equal(merged.log.calls.some((call) => call.hostname === "other.test" && call.mediation === "proc_socket"), true);
    } finally {
      if (previous == null) delete process.env.VANTIO_HOME;
      else process.env.VANTIO_HOME = previous;
      rmSync(root, { recursive: true, force: true });
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("a failed later sink does not send an earlier sink again", async () => {
    let hits = 0;
    const server = await listenHttp((req, res) => {
      hits += 1;
      res.writeHead(200);
      res.end("ok");
    });
    const port = server.address().port;
    const dir = mkdtempSync(join(tmpdir(), "vantio-export-retry-"));
    const completed = new Set();
    const events = [{
      schema: "vantio.optics.export.v1",
      kind: "observation",
      time: "2026-10-21T18:02:07.000Z",
      program: "curl",
      destination: "example.test",
      optics_status: "OBSERVED",
      authority: "outside_authority",
    }];
    try {
      await assert.rejects(
        () => features.deliverExport(events, {
          webhook: `http://127.0.0.1:${port}/hook`,
          jsonl: dir,
          completed,
        }),
        /EISDIR|directory/i,
      );
      assert.equal(hits, 1);
      assert.equal(completed.has("webhook"), true);
      await assert.rejects(
        () => features.deliverExport(events, {
          webhook: `http://127.0.0.1:${port}/hook`,
          jsonl: dir,
          completed,
        }),
        /EISDIR|directory/i,
      );
      assert.equal(hits, 1);
      const file = join(dir, "out.jsonl");
      const delivered = await features.deliverExport(events, {
        webhook: `http://127.0.0.1:${port}/hook`,
        jsonl: file,
        completed,
      });
      assert.equal(hits, 1);
      assert.deepEqual(delivered, ["jsonl"]);
      assert.equal(readFileSync(file, "utf8").trim().split("\n").length, 1);
    } finally {
      server.close();
      rmSync(dir, { recursive: true, force: true });
    }
  });

  test("a stuck export batch does not drop journal lines that have not been read", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-follow-hold-"));
    const path = join(home, "live.jsonl");
    const line = (destination) => `${JSON.stringify({
      schema: "vantio.optics.live.v1",
      kind: "observation",
      time: "2026-10-21T18:02:07.000Z",
      program: "curl",
      destination,
      flag: null,
    })}\n`;
    writeFileSync(path, line("queued.example"));
    let hits = 0;
    const server = await listenHttp((req, res) => {
      hits += 1;
      res.writeHead(200);
      res.end("ok");
    });
    const port = server.address().port;
    const state = {
      path,
      offset: 0,
      buffer: features.createFollowBuffer(2),
      pending: [{ destination: "held.example", program: "curl", kind: "observation" }],
      attempt: 0,
      dropped: 0,
      deliverOptions: { completed: new Set(), webhook: "http://127.0.0.1:1/hook" },
      readError: null,
      badLine: false,
      lastError: null,
    };
    try {
      const held = await features.stepFollowExport(state);
      assert.equal(held, "retry");
      assert.equal(state.offset, 0);
      assert.equal(state.pending[0].destination, "held.example");
      assert.equal(state.buffer.size(), 0);
      state.deliverOptions.webhook = `http://127.0.0.1:${port}/hook`;
      const sent = await features.stepFollowExport(state);
      assert.equal(sent, "sent");
      assert.equal(hits, 1);
      assert.equal(state.offset, 0);
      const next = await features.stepFollowExport(state);
      assert.equal(next, "sent");
      assert.ok(state.offset > 0);
      assert.equal(hits, 2);
    } finally {
      server.close();
      rmSync(home, { recursive: true, force: true });
    }
  });

  test("an older run still covers a live process outside the coverage window", () => {
    const root = mkdtempSync(join(tmpdir(), "vantio-proc-window-"));
    mkdirSync(join(root, "net"), { recursive: true });
    mkdirSync(join(root, "321", "fd"), { recursive: true });
    writeFileSync(join(root, "net", "tcp"), "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n   0: 0100007F:3039 327100CB:01BB 01 00000000:00000000 00:00000000 00000000     0        0 4242 1 0000000000000000 100 0 0 10 0\n");
    writeFileSync(join(root, "321", "cmdline"), "node\0agent.js\0");
    symlinkSync("socket:[4242]", join(root, "321", "fd", "3"));
    writeFileSync(join(root, "hosts"), "203.0.113.50 api.openai.com\n");
    const options = {
      procRoot: root,
      hostsPath: join(root, "hosts"),
      selfPid: 1,
      isAiHost: (host) => host === "api.openai.com",
    };
    const old = { pid: 321, program: "agent.js", kind: "connection", destination: "api.openai.com" };
    try {
      const windowed = features.procGapsForCoverage({ observations: [], allObservations: [old] }, options);
      assert.deepEqual(windowed.processes, []);
      const missed = features.procGapsForCoverage({ observations: [old], allObservations: [] }, options);
      assert.equal(missed.processes.length, 1);
      assert.equal(missed.processes[0].pid, 321);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  test("the process table marks an unwrapped AI socket not covered", () => {
    const root = mkdtempSync(join(tmpdir(), "vantio-proc-"));
    mkdirSync(join(root, "net"), { recursive: true });
    mkdirSync(join(root, "321", "fd"), { recursive: true });
    mkdirSync(join(root, "322", "fd"), { recursive: true });
    const remote = "327100CB:01BB";
    writeFileSync(join(root, "net", "tcp"), `  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n   0: 0100007F:3039 ${remote} 01 00000000:00000000 00:00000000 00000000     0        0 4242 1 0000000000000000 100 0 0 10 0\n`);
    writeFileSync(join(root, "321", "cmdline"), "node\0agent.js\0");
    symlinkSync("socket:[4242]", join(root, "321", "fd", "3"));
    writeFileSync(join(root, "322", "cmdline"), "nginx\0");
    symlinkSync("socket:[1]", join(root, "322", "fd", "4"));
    writeFileSync(join(root, "hosts"), "203.0.113.50 api.openai.com\n");
    const found = proc.discoverUncovered({
      procRoot: root,
      hostsPath: join(root, "hosts"),
      covered: [{ pid: 999, program: "other.js" }],
      isAiHost: (host) => host === "api.openai.com",
    });
    assert.equal(found.readable, true);
    assert.equal(found.processes.length, 1);
    assert.equal(found.processes[0].pid, 321);
    assert.equal(found.processes[0].program, "agent.js");
    assert.equal(found.processes[0].destination, "api.openai.com");
    assert.equal(found.processes[0].covered, false);
    const hidden = proc.discoverUncovered({
      procRoot: root,
      hostsPath: join(root, "hosts"),
      covered: [{ pid: 321, program: "agent.js" }],
      isAiHost: (host) => host === "api.openai.com",
    });
    assert.deepEqual(hidden.processes, []);
    rmSync(root, { recursive: true, force: true });
  });

  test("OTLP gRPC sends traces, metrics, and logs over HTTP/2", async () => {
    const paths = [];
    const bodies = [];
    const server = http2.createServer();
    server.on("stream", (stream, headers) => {
      const chunks = [];
      paths.push(headers[":path"]);
      stream.on("data", (chunk) => chunks.push(chunk));
      stream.on("end", () => {
        bodies.push(Buffer.concat(chunks));
        stream.respond({ ":status": 200, "content-type": "application/grpc", "grpc-status": "0" });
        stream.end();
      });
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    try {
      const events = [{
        schema: "vantio.optics.export.v1",
        kind: "observation",
        time: "2026-10-21T18:02:07.000Z",
        program: "agent.js",
        destination: "billing.internal.example",
        method: "POST",
        path: "/v1/tools",
        bytes: 1840,
        http_status: 200,
        optics_status: "OBSERVED",
        authority: "outside_authority",
        trace_id: "0xa1b2c3d4e5f60718",
        otel_trace_id: "ab".repeat(16),
        otel_span_id: "cd".repeat(8),
        flag: "new_destination",
        flag_label: "New destination",
        pid: 42,
      }];
      const payloads = features.otlpPayloads(events, { hostname: "box", platform: "linux" });
      const encoded = grpc.encodeOtlpGrpc(payloads);
      assert.ok(encoded.traces.includes(Buffer.from("ab".repeat(16), "hex")));
      assert.doesNotMatch(encoded.traces.toString("utf8"), new RegExp(CANARY));
      await grpc.deliverOtlpGrpc(`grpc://127.0.0.1:${port}`, payloads);
      assert.deepEqual(paths.sort(), [
        grpc.LOGS_PATH,
        grpc.METRICS_PATH,
        grpc.TRACE_PATH,
      ].sort());
      assert.ok(bodies.every((body) => body.length > 5 && body[0] === 0));
    } finally {
      server.close();
    }
  });

  test("OTLP gRPC uses grpc-status from trailers and does not treat a missing status as success", async () => {
    const server = http2.createServer();
    server.on("stream", (stream) => {
      stream.on("data", () => {});
      stream.respond({
        ":status": 200,
        "content-type": "application/grpc",
      }, { waitForTrailers: true });
      stream.on("wantTrailers", () => {
        stream.sendTrailers({ "grpc-status": "13" });
      });
      stream.end();
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = server.address().port;
    try {
      const payloads = features.otlpPayloads([{
        schema: "vantio.optics.export.v1",
        kind: "observation",
        time: "2026-10-21T18:02:07.000Z",
        program: "agent.js",
        destination: "billing.internal.example",
        bytes: 1,
        optics_status: "OBSERVED",
        authority: "outside_authority",
      }], { hostname: "box", platform: "linux" });
      await assert.rejects(
        () => grpc.deliverOtlpGrpc(`grpc://127.0.0.1:${port}`, payloads),
        /otlp grpc traces: otlp grpc returned 13/,
      );
    } finally {
      server.close();
    }
  });

  test("tail and export follow print and send a destination as it is recorded", async () => {
    const home = mkdtempSync(join(tmpdir(), "vantio-follow-"));
    mkdirSync(join(home, ".vantio"), { recursive: true });
    const hits = [];
    const server = await listenHttp((req, res) => {
      const chunks = [];
      req.on("data", (chunk) => chunks.push(chunk));
      req.on("end", () => {
        hits.push(Buffer.concat(chunks).toString("utf8"));
        res.writeHead(200);
        res.end("ok");
      });
    });
    const port = server.address().port;
    const tail = spawn(process.execPath, [CLI, "tail", "--follow"], {
      env: { PATH: process.env.PATH, HOME: home },
      stdio: ["ignore", "pipe", "pipe"],
    });
    const exporter = spawn(process.execPath, [CLI, "export", "--follow", `--webhook=http://127.0.0.1:${port}/hook`], {
      env: { PATH: process.env.PATH, HOME: home },
      stdio: ["ignore", "pipe", "pipe"],
    });
    let tailOut = "";
    tail.stdout.on("data", (chunk) => { tailOut += chunk; });
    try {
      await new Promise((resolve) => setTimeout(resolve, 300));
      const event = {
        schema: "vantio.optics.live.v1",
        kind: "new_destination",
        flag: "new_destination",
        flag_label: "New destination",
        clock: "14:02:07",
        time: "2026-10-21T18:02:07.000Z",
        program: "agent.js",
        destination: "billing.internal.example",
        trace_id: "0xa1b2c3d4e5f60718",
        path: "/v1/tools",
        bytes: 1840,
      };
      writeFileSync(join(home, ".vantio", "live.jsonl"), `${JSON.stringify(event)}\n`);
      const deadline = Date.now() + 2000;
      while ((!tailOut.includes("14:02:07") || hits.length < 1) && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
      assert.match(tailOut, /New destination/);
      assert.match(tailOut, /First connection: 14:02:07/);
      assert.match(tailOut, /agent\.js/);
      assert.ok(hits.length >= 1);
      assert.match(hits[0], /billing\.internal\.example/);
      assert.doesNotMatch(hits[0], new RegExp(CANARY));
    } finally {
      tail.kill("SIGTERM");
      exporter.kill("SIGTERM");
      await new Promise((resolve) => setTimeout(resolve, 200));
      server.close();
      rmSync(home, { recursive: true, force: true });
    }
  });
});
