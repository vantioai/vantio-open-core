import { test, describe, before, after } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import http from "node:http";
import dgram from "node:dgram";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir, hostname } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const features = require("../bin/optics-features.cjs");
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
    const under = system.under_authority.map((row) => row.destination).sort();
    const outside = system.outside_authority.map((row) => row.destination).sort();
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
      assert.equal(body.counts.connections, 1);
      assert.equal(body.connections[0].authority, "under_authority");
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
