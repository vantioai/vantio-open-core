import { readFileSync } from "node:fs";
import http from "node:http";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createExporter } from "../../../packages/optics-export/src/exporter.cjs";
import { attestObservation } from "../../../packages/optics-export/src/exporter.cjs";
import { docker, event, send, sleep } from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const certs = "/tmp/vantio-matrix/certs";
const ca = readFileSync(`${certs}/ca.pem`);
const cert = readFileSync(`${certs}/client.pem`);
const key = readFileSync(`${certs}/client.key`);

function httpsText(port, urlPath) {
  return new Promise((resolve, reject) => {
    const req = https.get({
      host: "127.0.0.1", port, path: urlPath, ca, cert, key,
      servername: "localhost", rejectUnauthorized: true,
    }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", reject);
  });
}

const sink = await new Promise((resolve) => {
  const server = http.createServer((req, res) => {
    req.resume();
    res.writeHead(200, { "content-type": "application/json" });
    res.end("{}");
  });
  server.listen(0, "127.0.0.1", () => resolve(server));
});
const exporter = createExporter({
  enabled: true,
  endpoint: `http://127.0.0.1:${sink.address().port}`,
  protocol: "otlp-http-json",
  headers: {},
  compression: "none",
  maxBatch: 8,
  maxDelayMs: 20,
  maxQueue: 16,
  timeoutMs: 2000,
  jsonlPath: null,
  jsonlMaxBytes: 1024,
  syslog: null,
  webhook: null,
  allowInsecureLocalhost: true,
  metricsPort: 9464,
  metricsHost: "0.0.0.0",
  metricsTls: true,
  metricsMtls: true,
  caFile: `${certs}/ca.pem`,
  certFile: `${certs}/server.pem`,
  keyFile: `${certs}/server.key`,
});
for (let i = 0; i < 4; i += 1) send(exporter, event(`metric-${i}`, { span_id: (i + 1).toString(16).padStart(16, "0") }));
await exporter.flush();
const local = await httpsText(9464, "/metrics");
console.log("LOCAL_METRICS", local.body.trim(), "sent", exporter.status().sent);

try { docker(["rm", "-f", "vantio-prom-tls"]); } catch { /* */ }
docker([
  "run", "-d", "--name", "vantio-prom-tls",
  "-p", "9090:9090",
  "--add-host", "host.docker.internal:host-gateway",
  "-v", `${certs}:/certs:ro`,
  "-v", `${path.join(root, "grafana/prometheus-scrape.yml")}:/etc/prometheus/prometheus.yml:ro`,
  "-v", `${path.join(root, "grafana/prometheus-web.yml")}:/etc/prometheus/web.yml:ro`,
  "prom/prometheus:v3.2.1",
  "--config.file=/etc/prometheus/prometheus.yml",
  "--web.config.file=/etc/prometheus/web.yml",
  "--web.enable-remote-write-receiver",
]);
await sleep(3000);
let prom = "";
try {
  prom = (await httpsText(9090, "/api/v1/query?query=vantio_optics_events_sent_total")).body;
} catch (err) {
  prom = String(err.message || err);
}
console.log("PROM_QUERY", prom.slice(0, 800));
const plain = await new Promise((resolve) => {
  const req = http.get("http://127.0.0.1:9090/api/v1/query?query=up", (res) => {
    res.resume();
    resolve(res.statusCode);
  });
  req.on("error", (err) => resolve(err.code || "error"));
});
console.log("PROM_PLAINTEXT", plain);

try { docker(["rm", "-f", "vantio-grafana-tls"]); } catch { /* */ }
docker([
  "run", "-d", "--name", "vantio-grafana-tls",
  "-p", "3000:3000",
  "-v", `${certs}:/certs:ro`,
  "-e", "GF_SERVER_PROTOCOL=https",
  "-e", "GF_SERVER_CERT_FILE=/certs/server.pem",
  "-e", "GF_SERVER_CERT_KEY=/certs/server.key",
  "-e", "GF_AUTH_ANONYMOUS_ENABLED=true",
  "-e", "GF_AUTH_ANONYMOUS_ORG_ROLE=Admin",
  "-e", "GF_AUTH_DISABLE_LOGIN_FORM=true",
  "grafana/grafana:11.5.2",
]);
await sleep(4000);
try {
  const health = await httpsText(3000, "/api/health");
  console.log("GRAFANA", health.status, health.body.slice(0, 200));
} catch (err) {
  console.log("GRAFANA_ERR", err.message);
  try { console.log(docker(["logs", "vantio-grafana-tls"]).slice(-400)); } catch { /* */ }
}
const grafanaPlain = await new Promise((resolve) => {
  const req = http.get("http://127.0.0.1:3000/api/health", (res) => {
    res.resume();
    resolve(res.statusCode);
  });
  req.on("error", (err) => resolve(err.code || "error"));
});
console.log("GRAFANA_PLAINTEXT", grafanaPlain);
exporter.stop();
sink.close();
docker(["rm", "-f", "vantio-prom-tls", "vantio-grafana-tls"]);
