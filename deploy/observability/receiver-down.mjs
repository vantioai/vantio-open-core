import { writeFileSync } from "node:fs";
import { attestObservation, createExporter } from "../../packages/optics-export/src/exporter.cjs";

const minutes = Number(process.env.VANTIO_DOWN_MINUTES || "10");
const TRACE = "aa".repeat(16);
const SPAN = "bb".repeat(8);
const event = {
  kind: "optics.observation",
  trace_id: TRACE,
  span_id: SPAN,
  destination_host: "api.openai.com",
  destination_port: 443,
  coverage_state: "OBSERVED",
  workload_id: "down-test",
};

function make(protocol, endpoint) {
  return createExporter({
    enabled: true,
    endpoint,
    protocol,
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
  });
}

const targets = [
  ["otlp-http-json", make("otlp-http-json", "http://127.0.0.1:1")],
  ["otlp-http-protobuf", make("otlp-http-protobuf", "http://127.0.0.1:1")],
  ["otlp-grpc", make("otlp-grpc", "http://127.0.0.1:1")],
];

if (!attestObservation(event).ok) {
  console.error("source attestation failed");
  process.exit(1);
}
const startedRss = process.memoryUsage().rss;
const deadline = Date.now() + minutes * 60 * 1000;
const latency = [];
let offers = 0;
while (Date.now() < deadline) {
  for (const [, exporter] of targets) {
    const t0 = process.hrtime.bigint();
    const result = exporter.offer(event, exporter.token);
    latency.push(Number(process.hrtime.bigint() - t0) / 1e6);
    offers += 1;
    if (result.reason !== "DROPPED" && result.accepted !== true) {
      console.error("unexpected offer", result);
      process.exit(1);
    }
  }
  await new Promise((resolve) => setTimeout(resolve, 200));
}
const rssDelta = process.memoryUsage().rss - startedRss;
const maxLatency = Math.max(...latency);
const report = {
  minutes,
  offers,
  max_offer_ms: Number(maxLatency.toFixed(3)),
  rss_delta_bytes: rssDelta,
  targets: targets.map(([name, exporter]) => ({ name, ...exporter.status() })),
};
for (const row of report.targets) {
  if (row.queued > 8) {
    console.error("queue unbounded", row);
    process.exit(1);
  }
  if (row.dropped < 1) {
    console.error("drop counter did not move", row);
    process.exit(1);
  }
}
if (maxLatency > 50) {
  console.error("offer blocked", maxLatency);
  process.exit(1);
}
if (rssDelta > 64 * 1024 * 1024) {
  console.error("rss grew", rssDelta);
  process.exit(1);
}
writeFileSync("/tmp/vantio-receiver-down.json", JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));
for (const [, exporter] of targets) exporter.stop();
