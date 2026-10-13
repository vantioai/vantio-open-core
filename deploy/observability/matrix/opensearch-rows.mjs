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
  send,
  sleep,
  traceId,
  trio,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const minutes = Number(process.env.VANTIO_DOWN_MINUTES || "10");
const endpoint = "http://127.0.0.1:4518";

function compose(args) {
  docker(["compose", "-p", "opensearch", "-f", path.join(root, "opensearch/compose.yaml"), ...args], { timeout: 180000 });
}

try {
  compose(["down"]);
} catch {
  /* not up */
}

const exporter = makeExporter({
  endpoint,
  protocol: "otlp-http-json",
  timeoutMs: 80,
  maxDelayMs: 200,
  maxQueue: 8,
  maxBatch: 4,
});
const row = event("down-opensearch", { workload_id: "qdrain-opensearch" });
const rss0 = process.memoryUsage().rss;
const deadline = Date.now() + minutes * 60 * 1000;
let offers = 0;
let maxOfferMs = 0;
while (Date.now() < deadline) {
  const t0 = process.hrtime.bigint();
  const result = send(exporter, row);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  if (ms > maxOfferMs) maxOfferMs = ms;
  offers += 1;
  if (offers % 270 === 0) {
    console.log("DOWN_BEAT", JSON.stringify({ offers, max_offer_ms: Number(maxOfferMs.toFixed(3)), rss_delta_bytes: process.memoryUsage().rss - rss0, ...exporter.status() }));
  }
  if (result.accepted !== true && result.reason !== "DROPPED") {
    console.error("unexpected", result);
    process.exit(1);
  }
  await sleep(200);
}

exporter.suspend();
await exporter.flush();
const before = exporter.status();
const down = {
  minutes,
  offers,
  max_offer_ms: Number(maxOfferMs.toFixed(3)),
  rss_delta_bytes: process.memoryUsage().rss - rss0,
  memory_within_64mb: process.memoryUsage().rss - rss0 <= 64 * 1024 * 1024,
  ...before,
  trace_id: row.trace_id,
};
console.log("DOWN_PHASE", JSON.stringify(down));
if (before.sent !== 0 || before.queued < 1) {
  console.error("down invariant failed", down);
  process.exit(1);
}

compose(["up", "-d"]);
for (let i = 0; i < 40; i += 1) {
  try {
    const health = await fetch("http://127.0.0.1:9200/_cluster/health");
    if (health.ok) break;
  } catch {
    /* starting */
  }
  await sleep(1000);
}
for (let i = 0; i < 30; i += 1) {
  try {
    const logs = docker(["logs", "opensearch-collector-1"]);
    if (String(logs).includes("Everything is ready")) break;
  } catch {
    /* stderr-only logs */
  }
  await sleep(500);
}
await sleep(1000);
exporter.resume();
await exporter.flush({ drain: true, timeoutMs: 20000 });
await sleep(1500);
const after = exporter.status();
const trace = traceId("down-opensearch");
let search = "";
try {
  const response = await fetch("http://127.0.0.1:9200/vantio-traces,vantio-logs/_search?size=20");
  search = await response.text();
} catch (err) {
  search = String(err && err.message ? err.message : err);
}
const row5 = {
  down,
  after,
  trace_hit: search.includes(trace),
  workload_hit: search.includes("qdrain-opensearch"),
  schema: search.includes("1.0.0"),
  hits: leakHits(search),
  drained: after.queued === 0 && after.sent >= before.queued && before.sent === 0,
};
console.log("ROW5", JSON.stringify(row5));
exporter.stop();

const fresh = makeExporter({
  endpoint,
  protocol: "otlp-http-json",
  timeoutMs: 8000,
  maxDelayMs: 20,
  maxBatch: 32,
  maxQueue: 2000,
});
const main = await deliverRows(fresh, trio("opensearch-rows"));
const extra = await pushPrivacyAndForged(fresh, "opensearch-rows");
const cpu = process.cpuUsage();
const mem = process.memoryUsage();
const t0 = performance.now();
let accepted = 0;
for (let i = 0; i < 1000; i += 1) {
  if (send(fresh, event(`os-throughput-${i}`, { span_id: (i + 1).toString(16).padStart(16, "0") })).accepted) accepted += 1;
}
await fresh.flush({ drain: true, timeoutMs: 30000 });
const elapsed = performance.now() - t0;
const cpuAfter = process.cpuUsage(cpu);
const memAfter = process.memoryUsage();
const throughput = fresh.status();
fresh.stop();

docker(["pause", "opensearch-opensearch-1"]);
const paused = makeExporter({ endpoint, protocol: "otlp-http-json", timeoutMs: 200, maxDelayMs: 60000, maxQueue: 4 });
const offerStart = performance.now();
const pauseOffer = send(paused, event("os-paused"));
const pauseOfferMs = performance.now() - offerStart;
const flushStart = performance.now();
await paused.flush();
const pauseFlush = performance.now() - flushStart;
const pauseStatus = paused.status();
paused.stop();
docker(["unpause", "opensearch-opensearch-1"]);

const direct = makeExporter({
  endpoint: "http://127.0.0.1:9200",
  protocol: "otlp-http-json",
  timeoutMs: 2000,
  maxDelayMs: 60000,
  maxQueue: 2,
});
send(direct, event("os-direct"));
await direct.flush();
const directStatus = direct.status();
direct.stop();

let indices = "";
try {
  indices = await (await fetch("http://127.0.0.1:9200/_cat/indices?v")).text();
} catch (err) {
  indices = String(err && err.message ? err.message : err);
}
let oldImage = "";
try {
  oldImage = docker([
    "run", "--rm",
    "otel/opentelemetry-collector-contrib:0.103.0@sha256:0dffde3e58fc3f255cad861deb62d7c51505ce961a8a7e2107c7fc2668b774a3",
    "components",
  ]);
} catch (err) {
  oldImage = `${err.stdout || ""}\n${err.stderr || ""}\n${err.message || ""}`;
}
const result = {
  row5,
  row6: {
    pause_offer_ms: Number(pauseOfferMs.toFixed(3)),
    pause_flush_ms: Number(pauseFlush.toFixed(3)),
    pause_offer_accepted: pauseOffer.accepted === true,
    pause_health: pauseStatus.health,
    pause_sent: pauseStatus.sent,
    pause_error: pauseStatus.lastError,
    direct_health: directStatus.health,
    direct_sent: directStatus.sent,
    direct_error: directStatus.lastError,
  },
  row7: {
    accepted,
    elapsed_ms: Number(elapsed.toFixed(1)),
    cpu_user_us: cpuAfter.user,
    cpu_system_us: cpuAfter.system,
    rss_delta_bytes: memAfter.rss - mem.rss,
    sent: throughput.sent,
    dropped: throughput.dropped,
    health: throughput.health,
  },
  ingest: {
    health: main.status.health,
    sent: main.status.sent,
    forged: extra.forged.reason,
    unbound: extra.unbound.reason,
  },
  indices,
  old_collector_has_opensearch_exporter: /name:\s+opensearch/.test(oldImage),
};
console.log("OPENSEARCH_ROWS", JSON.stringify(result));
if (!row5.drained || !row5.trace_hit) process.exit(1);
