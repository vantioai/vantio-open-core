import { attestObservation, createExporter } from "../../../packages/optics-export/src/exporter.cjs";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const DIGEST = `sha256:${"ab".repeat(32)}`;
const TRACE = "11".repeat(16);
const base = {
  trace_id: TRACE,
  destination_host: "api.openai.com",
  destination_port: 443,
  pid: 42,
  executable: "node",
  lineage: [{ pid: 7, executable: "agent" }],
  request_bytes: 20,
  response_bytes: 40,
  duration_ms: 8,
  http_status: 204,
  optics_status: "SUCCESS",
  application_status: "SUCCESS",
  workload_id: "workload-a",
  coverage_state: "OBSERVED",
  path: "/v1/chat?CANARY-QUERYSTRING=1",
  prompt: "CANARY-PROMPTTEXT",
  body: "CANARY-BODYTEXT",
  headers: { authorization: "CANARY-HEADERVALUE" },
  completion: "CANARY-COMPLETION",
};

const events = [
  { ...base, kind: "optics.observation", span_id: "22".repeat(8) },
  { ...base, kind: "phantom.decision", span_id: "33".repeat(8), decision: "BLOCK", policy_digest: DIGEST },
  { ...base, kind: "enterprise.evidence", span_id: "44".repeat(8), policy_digest: DIGEST },
];

const protocols = [
  ["otlp-http-json", "http://127.0.0.1:4318"],
  ["otlp-http-protobuf", "http://127.0.0.1:4318"],
  ["otlp-grpc", "http://127.0.0.1:4317"],
];

for (const [protocol, endpoint] of protocols) {
  const exporter = createExporter({
    enabled: true,
    endpoint,
    protocol,
    headers: {},
    compression: "gzip",
    maxBatch: 16,
    maxDelayMs: 20,
    maxQueue: 16,
    timeoutMs: 3000,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
  });
  for (const event of events) {
    if (!attestObservation(event).ok) process.exit(1);
    exporter.offer(event, exporter.token);
  }
  await exporter.flush();
  const status = exporter.status();
  if (status.health !== "healthy") {
    console.error(protocol, status);
    process.exit(1);
  }
  exporter.stop();
}

await new Promise((resolve) => setTimeout(resolve, 1500));
const outDir = new URL("./out/", import.meta.url);
const files = readdirSync(outDir).filter((name) => statSync(join(outDir.pathname, name)).isFile());
const blob = files.map((name) => readFileSync(join(outDir.pathname, name), "utf8")).join("\n");
const required = ["1.0.0", TRACE, "api.openai.com", "workload-a", "BLOCK", DIGEST, "enterprise.evidence", "phantom.decision"];
for (const needle of required) {
  if (!blob.includes(needle)) {
    console.error("missing", needle);
    console.error(blob.slice(0, 1500));
    process.exit(1);
  }
}
for (const canary of ["CANARY-PROMPTTEXT", "CANARY-BODYTEXT", "CANARY-HEADERVALUE", "CANARY-COMPLETION", "CANARY-QUERYSTRING"]) {
  if (blob.includes(canary)) {
    console.error("canary leaked", canary);
    process.exit(1);
  }
}
console.log(`COLLECTOR_OK files=${files.join(",")} bytes=${Buffer.byteLength(blob)}`);
