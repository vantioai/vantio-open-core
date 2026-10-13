import { performance } from "node:perf_hooks";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  deliverRows,
  docker,
  event,
  leakHits,
  makeExporter,
  pushPrivacyAndForged,
  readText,
  send,
  sleep,
  trio,
  waitForPort,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function timedProbe(name, extra) {
  const exporter = makeExporter({
    timeoutMs: 150,
    maxDelayMs: 60000,
    maxQueue: 4,
    maxBatch: 10,
    ...extra,
  });
  const started = performance.now();
  const offered = send(exporter, event(`${name}-live`));
  const offerMs = performance.now() - started;
  const flushStarted = performance.now();
  await exporter.flush();
  const flushMs = performance.now() - flushStarted;
  const status = exporter.status();
  exporter.stop();
  return {
    name,
    offer_accepted: offered.accepted === true,
    offer_ms: Number(offerMs.toFixed(3)),
    flush_ms: Number(flushMs.toFixed(3)),
    health: status.health,
    sent: status.sent,
    queued: status.queued,
    last_error: status.lastError,
  };
}

async function paused(container, name, extra) {
  docker(["pause", container]);
  try {
    return await timedProbe(name, extra);
  } finally {
    try {
      docker(["unpause", container]);
    } catch (err) {
      console.error("unpause", container, err && err.message);
    }
  }
}

const sink = await new Promise((resolve) => {
  import("node:http").then(({ default: http }) => {
    const server = http.createServer((req, res) => {
      req.resume();
      res.writeHead(200);
      res.end("ok");
    });
    server.listen(0, "127.0.0.1", () => resolve({ server, url: `http://127.0.0.1:${server.address().port}` }));
  });
});

const rows = [];
rows.push(await paused("vantio-jaeger", "jaeger-paused", { endpoint: "http://127.0.0.1:4320", protocol: "otlp-http-json" }));
rows.push(await timedProbe("jaeger-ui", { endpoint: "http://127.0.0.1:16686", protocol: "otlp-http-json" }));
rows.push(await paused("vantio-tempo", "tempo-paused", { endpoint: "http://127.0.0.1:4348", protocol: "otlp-http-json" }));
rows.push(await timedProbe("tempo-query", { endpoint: "http://127.0.0.1:3201", protocol: "otlp-http-json" }));
rows.push(await paused("vantio-rsyslog", "rsyslog-paused", {
  endpoint: sink.url,
  protocol: "otlp-http-json",
  syslog: "tcp://127.0.0.1:5515",
}));

await waitForPort(5515);
await sleep(300);
const syslogAfter = makeExporter({
  endpoint: sink.url,
  protocol: "otlp-http-json",
  syslog: "tcp://127.0.0.1:5515",
  timeoutMs: 1000,
  maxDelayMs: 20,
});
const after = await deliverRows(syslogAfter, [event("syslog-after-pause", { workload_id: "after-pause-marker" })]);
syslogAfter.stop();
const syslogBlob = readText(path.join(root, "rsyslog/out/syslog.log"));

if (!(await waitForPort(4418))) throw new Error("old collector closed");
const old = makeExporter({
  endpoint: "http://127.0.0.1:4418",
  protocol: "otlp-http-json",
  timeoutMs: 4000,
  maxDelayMs: 20,
  maxBatch: 32,
  maxQueue: 2000,
});
const main = await deliverRows(old, trio("old-collector-rescore"));
const extra = await pushPrivacyAndForged(old, "old-collector-rescore");
const before = process.memoryUsage();
const cpu = process.cpuUsage();
const t0 = performance.now();
let accepted = 0;
for (let i = 0; i < 1000; i += 1) {
  const row = event(`old-throughput-${i}`, { span_id: (i + 1).toString(16).padStart(16, "0") });
  if (send(old, row).accepted) accepted += 1;
}
await old.flush({ drain: true, timeoutMs: 20000 });
const elapsed = performance.now() - t0;
const cpuAfter = process.cpuUsage(cpu);
const memAfter = process.memoryUsage();
const oldStatus = old.status();
old.stop();
await sleep(1000);
const oldBlob = `${readText(path.join(root, "collector/out-old/traces.json"))}\n${readText(path.join(root, "collector/out-old/logs.json"))}`;

const result = {
  hostile: rows,
  syslog_after: {
    health: after.status.health,
    sent: after.status.sent,
    marker: syslogBlob.includes("syslog-after-pause"),
  },
  old_collector: {
    health: main.status.health,
    sent: main.status.sent,
    schema: oldBlob.includes("1.0.0"),
    block: oldBlob.includes("BLOCK"),
    kinds: ["optics.observation", "phantom.decision", "enterprise.evidence"].filter((kind) => oldBlob.includes(kind)),
    hits: leakHits(oldBlob),
    forged: extra.forged.reason,
    unbound: extra.unbound.reason,
    forged_marker: oldBlob.includes("FORGED-WORKLOAD-9f3a"),
    throughput: {
      accepted,
      elapsed_ms: Number(elapsed.toFixed(1)),
      cpu_user_us: cpuAfter.user,
      cpu_system_us: cpuAfter.system,
      rss_delta_bytes: memAfter.rss - before.rss,
      sent: oldStatus.sent,
      dropped: oldStatus.dropped,
      health: oldStatus.health,
    },
  },
};
console.log(JSON.stringify(result, null, 2));
sink.server.close();
