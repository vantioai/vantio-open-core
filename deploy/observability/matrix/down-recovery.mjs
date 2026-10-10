import { execFileSync, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  docker,
  event,
  prepareDir,
  readText,
  sleep,
  traceId,
  waitForPort,
} from "./lib.mjs";
import { attestObservation, createExporter } from "../../../packages/optics-export/src/exporter.cjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const minutes = Number(process.env.VANTIO_DOWN_MINUTES || "10");
const outDir = "/tmp/vantio-matrix";
mkdirSync(outDir, { recursive: true });

function compose(file, project, args) {
  docker(["compose", "-p", project, "-f", file, ...args], { timeout: 180000 });
}

function stopQuiet(names) {
  try {
    docker(["rm", "-f", ...names]);
  } catch {
    /* already gone */
  }
}

function send(exporter, row) {
  const attested = attestObservation(row);
  if (!attested.ok) return { accepted: false, reason: attested.reason || "ATTEST_FAILED" };
  return exporter.offer(row, exporter.token);
}

function makeExporter(extra) {
  return createExporter({
    enabled: true,
    endpoint: "http://127.0.0.1:9",
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 4,
    maxDelayMs: 200,
    maxQueue: 8,
    timeoutMs: 80,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
    ...extra,
  });
}

function discardSink() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      req.resume();
      res.writeHead(200);
      res.end("ok");
    });
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

function readyFile(dir) {
  prepareDir(dir);
  writeFileSync(path.join(dir, "traces.json"), "");
  writeFileSync(path.join(dir, "logs.json"), "");
  execFileSync("chmod", ["0666", path.join(dir, "traces.json"), path.join(dir, "logs.json")]);
}

function logsReady(name) {
  const result = spawnSync("sudo", ["docker", "logs", name], { encoding: "utf8" });
  const text = `${result.stdout || ""}\n${result.stderr || ""}`;
  return text.includes("Everything is ready");
}

stopQuiet(["vantio-jaeger", "vantio-tempo", "vantio-rsyslog"]);
try {
  compose(path.join(root, "collector/compose.yaml"), "collector", ["down"]);
} catch {
  /* not up */
}
try {
  compose(path.join(root, "collector/compose-old.yaml"), "collector-old", ["down"]);
} catch {
  /* not up */
}

const sink = await discardSink();
const specs = [
  ["collector-json", { endpoint: "http://127.0.0.1:4318", protocol: "otlp-http-json" }],
  ["collector-proto", { endpoint: "http://127.0.0.1:4318", protocol: "otlp-http-protobuf" }],
  ["collector-grpc", { endpoint: "http://127.0.0.1:4317", protocol: "otlp-grpc" }],
  ["collector-old", { endpoint: "http://127.0.0.1:4418", protocol: "otlp-http-json" }],
  ["jaeger-http", { endpoint: "http://127.0.0.1:4320", protocol: "otlp-http-json" }],
  ["jaeger-grpc", { endpoint: "http://127.0.0.1:4319", protocol: "otlp-grpc" }],
  ["tempo-http", { endpoint: "http://127.0.0.1:4348", protocol: "otlp-http-json" }],
  ["syslog-tcp", { endpoint: sink.url, protocol: "otlp-http-json", syslog: "tcp://127.0.0.1:5515" }],
  ["webhook", { endpoint: sink.url, protocol: "otlp-http-json", webhook: "http://127.0.0.1:9096/hook" }],
];

const targets = specs.map(([name, opts]) => ({
  name,
  exporter: makeExporter(opts),
  row: event(`down-${name}`, { workload_id: `qdrain-${name}` }),
}));

const rss0 = process.memoryUsage().rss;
const deadline = Date.now() + minutes * 60 * 1000;
let offers = 0;
let maxOfferMs = 0;
let nextBeat = Date.now() + 60000;
while (Date.now() < deadline) {
  for (const target of targets) {
    const t0 = process.hrtime.bigint();
    const result = send(target.exporter, target.row);
    const ms = Number(process.hrtime.bigint() - t0) / 1e6;
    if (ms > maxOfferMs) maxOfferMs = ms;
    offers += 1;
    if (result.accepted !== true && result.reason !== "DROPPED") {
      console.error("unexpected", target.name, result);
      process.exit(1);
    }
  }
  if (Date.now() >= nextBeat) {
    console.log("DOWN_BEAT", JSON.stringify({ offers, max_offer_ms: Number(maxOfferMs.toFixed(3)), rss_delta_bytes: process.memoryUsage().rss - rss0 }));
    nextBeat = Date.now() + 60000;
  }
  await sleep(200);
}

const down = {
  minutes,
  offers,
  max_offer_ms: Number(maxOfferMs.toFixed(3)),
  rss_delta_bytes: process.memoryUsage().rss - rss0,
  memory_within_64mb: process.memoryUsage().rss - rss0 <= 64 * 1024 * 1024,
  targets: targets.map((target) => {
    const status = target.exporter.status();
    return {
      name: target.name,
      trace_id: target.row.trace_id,
      workload_id: target.row.workload_id,
      ...status,
    };
  }),
};
writeFileSync(path.join(outDir, "down.json"), JSON.stringify(down, null, 2));
console.log("DOWN_PHASE", JSON.stringify(down));

const queuedBefore = new Map(targets.map((target) => [target.name, target.exporter.status()]));
readyFile(path.join(root, "collector/out"));
readyFile(path.join(root, "collector/out-old"));
prepareDir(path.join(root, "rsyslog/out"));
compose(path.join(root, "collector/compose.yaml"), "collector", ["up", "-d"]);
compose(path.join(root, "collector/compose-old.yaml"), "collector-old", ["up", "-d"]);
compose(path.join(root, "jaeger/compose.yaml"), "jaeger", ["up", "-d"]);
compose(path.join(root, "tempo/compose.yaml"), "tempo", ["up", "-d"]);
compose(path.join(root, "rsyslog/compose.yaml"), "rsyslog", ["up", "-d"]);

const seen = [];
const hook = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    seen.push(Buffer.concat(chunks).toString("utf8"));
    res.writeHead(200);
    res.end("ok");
  });
});
await new Promise((resolve) => hook.listen(9096, "127.0.0.1", resolve));

const ports = [4318, 4317, 4418, 4320, 4319, 16686, 4348, 3201, 5515];
for (const port of ports) {
  if (!(await waitForPort(port, "127.0.0.1", 80))) console.error("port closed", port);
}
for (let i = 0; i < 40 && !logsReady("collector-collector-1"); i += 1) await sleep(500);
for (let i = 0; i < 40 && !logsReady("collector-old-collector-1"); i += 1) await sleep(500);
try {
  docker(["exec", "vantio-rsyslog", "sh", "-c", ": > /out/syslog.log"]);
} catch (err) {
  console.error("syslog truncate", err && err.message);
}
await sleep(1000);

for (const target of targets) {
  await target.exporter.flush({ drain: true, timeoutMs: 20000 });
}
await sleep(2000);

function forms(tag) {
  const hex = traceId(tag);
  return [hex, Buffer.from(hex, "hex").toString("base64")];
}

async function textFrom(url) {
  try {
    const response = await fetch(url);
    return await response.text();
  } catch (err) {
    return String(err && err.message ? err.message : err);
  }
}

async function jaegerBody(tag) {
  let body = "";
  for (let i = 0; i < 20; i += 1) {
    body = await textFrom(`http://127.0.0.1:16686/api/traces/${traceId(tag)}`);
    if (forms(tag).some((form) => body.includes(form))) return body;
    await sleep(500);
  }
  return body;
}

async function tempoBody(tag) {
  let body = "";
  for (let i = 0; i < 20; i += 1) {
    body = await textFrom(`http://127.0.0.1:3201/api/traces/${traceId(tag)}`);
    if (forms(tag).some((form) => body.includes(form))) return body;
    await sleep(500);
  }
  return body;
}

const collectorBlob = `${readText(path.join(root, "collector/out/traces.json"))}\n${readText(path.join(root, "collector/out/logs.json"))}`;
const oldBlob = `${readText(path.join(root, "collector/out-old/traces.json"))}\n${readText(path.join(root, "collector/out-old/logs.json"))}`;
const syslogBlob = readText(path.join(root, "rsyslog/out/syslog.log"));
const webhookBlob = seen.join("\n");
const storage = {
  "collector-json": collectorBlob,
  "collector-proto": collectorBlob,
  "collector-grpc": collectorBlob,
  "collector-old": oldBlob,
  "jaeger-http": await jaegerBody("down-jaeger-http"),
  "jaeger-grpc": await jaegerBody("down-jaeger-grpc"),
  "tempo-http": await tempoBody("down-tempo-http"),
  "syslog-tcp": syslogBlob,
  webhook: webhookBlob,
};

const recovery = targets.map((target) => {
  const before = queuedBefore.get(target.name);
  const after = target.exporter.status();
  const blob = storage[target.name] || "";
  const traceHit = forms(`down-${target.name}`).some((form) => blob.includes(form));
  const workloadHit = blob.includes(target.row.workload_id);
  const drained = after.queued === 0 && after.sent >= before.queued && before.sent === 0 && before.queued > 0;
  return {
    name: target.name,
    before,
    after,
    trace_hit: traceHit,
    workload_hit: workloadHit,
    drained,
    storage_bytes: blob.length,
  };
});

const result = {
  down,
  recovery,
  drain_pass: recovery.every((row) => row.drained && row.trace_hit),
};
writeFileSync(path.join(outDir, "recovery.json"), JSON.stringify(result, null, 2));
console.log("RECOVERY", JSON.stringify(result));
for (const target of targets) target.exporter.stop();
sink.server.close();
hook.close();
if (!result.drain_pass) process.exit(1);
