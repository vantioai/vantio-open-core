import path from "node:path";
import { fileURLToPath } from "node:url";
import { docker, event, makeExporter, send, sleep, traceId } from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const certs = "/tmp/vantio-matrix/certs";
const minutes = Number(process.env.VANTIO_DOWN_MINUTES || "10");
const exporter = makeExporter({
  endpoint: "https://localhost:4320",
  protocol: "otlp-http-json",
  caFile: `${certs}/ca.pem`,
  certFile: `${certs}/client.pem`,
  keyFile: `${certs}/client.key`,
  timeoutMs: 80,
  maxDelayMs: 200,
  maxQueue: 8,
  maxBatch: 4,
});
const row = event("down-jaeger-tls", { workload_id: "qdrain-jaeger-tls" });
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
  if (offers % 270 === 0) console.log("DOWN_BEAT", offers, exporter.status());
  if (result.accepted !== true && result.reason !== "DROPPED") process.exit(1);
  await sleep(200);
}
exporter.suspend();
await exporter.flush();
const before = exporter.status();
console.log("DOWN_PHASE", JSON.stringify({ minutes, offers, max_offer_ms: Number(maxOfferMs.toFixed(3)), rss_delta_bytes: process.memoryUsage().rss - rss0, ...before }));
try { docker(["rm", "-f", "vantio-jaeger-tls"]); } catch { /* */ }
docker([
  "run", "-d", "--name", "vantio-jaeger-tls",
  "-p", "4320:4318", "-p", "4319:4317", "-p", "16686:16686",
  "-v", `${certs}:/certs:ro`,
  "jaegertracing/all-in-one:1.62.0",
  "--collector.otlp.http.tls.enabled=true",
  "--collector.otlp.http.tls.cert=/certs/server.pem",
  "--collector.otlp.http.tls.key=/certs/server.key",
  "--collector.otlp.http.tls.client-ca=/certs/ca.pem",
]);
await sleep(3000);
exporter.resume();
await exporter.flush({ drain: true, timeoutMs: 20000 });
const after = exporter.status();
const id = traceId("down-jaeger-tls");
const body = await (await fetch(`http://127.0.0.1:16686/api/traces/${id}`)).text();
console.log("DRAIN", JSON.stringify({ after, trace_hit: body.includes(id), workload: body.includes("qdrain-jaeger-tls"), hits_canary: body.toLowerCase().includes("canary") }));
exporter.stop();
docker(["rm", "-f", "vantio-jaeger-tls"]);
if (after.sent < before.queued || !body.includes(id)) process.exit(1);
