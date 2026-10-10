import { execFileSync } from "node:child_process";
import http from "node:http";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  deliverRows,
  docker,
  leakHits,
  makeExporter,
  okSink,
  prepareDir,
  pushPrivacyAndForged,
  readText,
  sleep,
  traceId,
  trio,
  waitForPort,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "collector/out");
prepareDir(out);
writeFileSync(path.join(out, "traces.json"), "");
writeFileSync(path.join(out, "logs.json"), "");
execFileSync("chmod", ["0666", path.join(out, "traces.json"), path.join(out, "logs.json")]);
docker(["compose", "-p", "collector", "-f", path.join(root, "collector/compose.yaml"), "up", "-d"], { inherit: true });
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
const sink = await okSink();
await waitForPort(4318);
await waitForPort(4320);
await waitForPort(4348);
await waitForPort(5515);
await sleep(800);

const specs = [
  ["collector-json", { endpoint: "http://127.0.0.1:4318", protocol: "otlp-http-json" }],
  ["jaeger-http", { endpoint: "http://127.0.0.1:4320", protocol: "otlp-http-json" }],
  ["tempo-http", { endpoint: "http://127.0.0.1:4348", protocol: "otlp-http-json" }],
  ["syslog-tcp", { endpoint: sink.url, protocol: "otlp-http-json", syslog: "tcp://127.0.0.1:5515" }],
  ["webhook", { endpoint: sink.url, protocol: "otlp-http-json", webhook: "http://127.0.0.1:9096/hook" }],
];
const recovery = {};
for (const [name, opts] of specs) {
  const exporter = makeExporter({ ...opts, compression: "none", timeoutMs: 5000, maxDelayMs: 20 });
  const main = await deliverRows(exporter, trio(`recover-${name}`));
  const extra = await pushPrivacyAndForged(exporter, `recover-${name}`);
  exporter.stop();
  recovery[name] = { health: main.status.health, sent: main.status.sent, forged: extra.forged.reason };
}
await sleep(1500);
const blobs = {
  collector: `${readText(path.join(out, "traces.json"))}\n${readText(path.join(out, "logs.json"))}`,
  jaeger: await fetch(`http://127.0.0.1:16686/api/traces/${traceId("recover-jaeger-http")}`).then((res) => res.text()),
  tempo: await fetch(`http://127.0.0.1:3201/api/traces/${traceId("recover-tempo-http")}`).then((res) => res.text()),
  syslog: readText(path.join(root, "rsyslog/out/syslog.log")),
  webhook: seen.join("\n"),
};
const summary = {};
for (const [name, blob] of Object.entries(blobs)) {
  summary[name] = {
    schema: blob.includes("1.0.0"),
    block: blob.includes("BLOCK"),
    kinds: blob.includes("enterprise.evidence") && blob.includes("phantom.decision"),
    hits: leakHits(blob).slice(0, 6),
    forged: blob.includes("FORGED-WORKLOAD-9f3a"),
    bytes: blob.length,
    health: recovery[name === "collector" ? "collector-json" : name === "jaeger" ? "jaeger-http" : name === "tempo" ? "tempo-http" : name === "syslog" ? "syslog-tcp" : "webhook"],
  };
}
console.log(JSON.stringify(summary, null, 2));
sink.server.close();
hook.close();
