import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  deliverRows,
  docker,
  event,
  leakHits,
  makeExporter,
  okSink,
  prepareDir,
  pushPrivacyAndForged,
  readText,
  send,
  sleep,
  traceId,
  trio,
  waitForPort,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const minutes = Number(process.env.VANTIO_DOWN_MINUTES || "10");

function stopQuiet(names) {
  try {
    docker(["stop", ...names]);
  } catch {
    /* already stopped */
  }
}

stopQuiet(["vantio-jaeger", "vantio-tempo", "vantio-rsyslog", "opensearch-collector-1"]);
try {
  docker(["compose", "-p", "collector", "-f", path.join(root, "collector/compose.yaml"), "down"]);
} catch {
  /* not up */
}

const sink = await okSink();
const specs = [
  ["collector-json", { endpoint: "http://127.0.0.1:4318", protocol: "otlp-http-json" }],
  ["collector-proto", { endpoint: "http://127.0.0.1:4318", protocol: "otlp-http-protobuf" }],
  ["collector-grpc", { endpoint: "http://127.0.0.1:4317", protocol: "otlp-grpc" }],
  ["jaeger-http", { endpoint: "http://127.0.0.1:4320", protocol: "otlp-http-json" }],
  ["jaeger-grpc", { endpoint: "http://127.0.0.1:4319", protocol: "otlp-grpc" }],
  ["tempo-http", { endpoint: "http://127.0.0.1:4348", protocol: "otlp-http-json" }],
  ["syslog-tcp", { endpoint: sink.url, protocol: "otlp-http-json", syslog: "tcp://127.0.0.1:5515" }],
  ["webhook", { endpoint: sink.url, protocol: "otlp-http-json", webhook: "http://127.0.0.1:9096/hook" }],
];

const targets = specs.map(([name, opts]) => {
  const exporter = makeExporter({
    ...opts,
    compression: "none",
    maxBatch: 4,
    maxDelayMs: 200,
    maxQueue: 8,
    timeoutMs: 80,
  });
  const row = event(`down-${name}`);
  return { name, exporter, row };
});

const rss0 = process.memoryUsage().rss;
const deadline = Date.now() + minutes * 60 * 1000;
let offers = 0;
let maxOfferMs = 0;
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
  await sleep(200);
}

const down = {
  minutes,
  offers,
  max_offer_ms: Number(maxOfferMs.toFixed(3)),
  rss_delta_bytes: process.memoryUsage().rss - rss0,
  targets: targets.map((target) => ({ name: target.name, ...target.exporter.status() })),
};
for (const row of down.targets) {
  if (row.queued > 8 || row.dropped < 1 || row.sent !== 0) {
    console.error("down invariant failed", row);
    process.exit(1);
  }
}
if (maxOfferMs > 50 || down.rss_delta_bytes > 64 * 1024 * 1024) {
  console.error("down budget failed", down);
  process.exit(1);
}
writeFileSync("/tmp/vantio-matrix/down.json", JSON.stringify(down, null, 2));
console.log("DOWN_OK", JSON.stringify(down));

const out = path.join(root, "collector/out");
prepareDir(out);
writeFileSync(path.join(out, "traces.json"), "");
writeFileSync(path.join(out, "logs.json"), "");
execFileSync("chmod", ["0666", path.join(out, "traces.json"), path.join(out, "logs.json")]);
docker(["compose", "-p", "collector", "-f", path.join(root, "collector/compose.yaml"), "up", "-d"]);
docker(["start", "vantio-jaeger"]);
docker(["start", "vantio-tempo"]);
docker(["start", "vantio-rsyslog"]);
docker(["exec", "vantio-rsyslog", "sh", "-c", ": > /out/syslog.log"]);
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

await waitForPort(4318);
await waitForPort(4320);
await waitForPort(4348);
await waitForPort(5515);
await sleep(1000);

const recovery = {};
for (const target of targets) await target.exporter.flush();
for (const [name, opts] of specs) {
  const exporter = makeExporter({ ...opts, compression: "none", timeoutMs: 5000, maxDelayMs: 20 });
  if (name === "webhook") exporter; 
  const main = await deliverRows(exporter, trio(`recover-${name}`));
  const extra = await pushPrivacyAndForged(exporter, `recover-${name}`);
  exporter.stop();
  recovery[name] = { health: main.status.health, sent: main.status.sent, forged: extra.forged.reason, unbound: extra.unbound.reason };
}
await sleep(1500);

function report(name, blob) {
  const hits = leakHits(blob);
  return {
    schema: blob.includes("1.0.0"),
    block: blob.includes("BLOCK"),
    hits,
    forged: blob.includes("FORGED-WORKLOAD-9f3a"),
    bytes: blob.length,
  };
}

const blobs = {
  collector: report("collector", `${readText(path.join(out, "traces.json"))}\n${readText(path.join(out, "logs.json"))}`),
  jaeger: report("jaeger", await fetch(`http://127.0.0.1:16686/api/traces/${traceId("recover-jaeger-http")}`).then((res) => res.text())),
  tempo: report("tempo", await fetch(`http://127.0.0.1:3201/api/traces/${traceId("recover-tempo-http")}`).then((res) => res.text())),
  syslog: report("syslog", readText(path.join(root, "rsyslog/out/syslog.log"))),
  webhook: report("webhook", seen.join("\n")),
};
const result = { down, recovery, blobs };
writeFileSync("/tmp/vantio-matrix/recovery.json", JSON.stringify(result, null, 2));
console.log("RECOVERY", JSON.stringify({ recovery, blobs }));
for (const target of targets) target.exporter.stop();
sink.server.close();
hook.close();
