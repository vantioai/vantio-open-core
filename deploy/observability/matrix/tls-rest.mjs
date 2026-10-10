import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import https from "node:https";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { deliverRows, docker, event, leakHits, makeExporter, pushPrivacyAndForged, send, sleep, trio } from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const certs = "/tmp/vantio-matrix/certs";
const outFile = "/tmp/vantio-matrix/tls-rest.json";
const report = {};
const ca = readFileSync(path.join(certs, "ca.pem"));
const cert = readFileSync(path.join(certs, "client.pem"));
const key = readFileSync(path.join(certs, "client.key"));

function save() {
  mkdirSync("/tmp/vantio-matrix", { recursive: true });
  writeFileSync(outFile, JSON.stringify(report, null, 2));
}

function tlsOpts(url) {
  return makeExporter({
    endpoint: url,
    protocol: "otlp-http-json",
    caFile: path.join(certs, "ca.pem"),
    certFile: path.join(certs, "client.pem"),
    keyFile: path.join(certs, "client.key"),
    timeoutMs: 8000,
    maxDelayMs: 20,
  });
}

function httpsText(urlPath, port) {
  return new Promise((resolve, reject) => {
    const req = https.get({
      host: "127.0.0.1",
      port,
      path: urlPath,
      ca, cert, key,
      servername: "localhost",
      rejectUnauthorized: true,
    }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
    });
    req.on("error", reject);
  });
}

async function badCa(url) {
  const bad = makeExporter({
    endpoint: url,
    protocol: "otlp-http-json",
    caFile: path.join(certs, "wrong.pem"),
    certFile: path.join(certs, "client.pem"),
    keyFile: path.join(certs, "client.key"),
    timeoutMs: 2000,
    maxDelayMs: 60000,
    maxQueue: 2,
  });
  send(bad, event("bad-ca"));
  await bad.flush();
  const status = bad.status();
  bad.stop();
  return { sent: status.sent, health: status.health, error: status.lastError };
}

try {
  docker(["rm", "-f", "vantio-loki-tls", "vantio-loki-collector"]);
} catch { /* none */ }
docker([
  "run", "-d", "--name", "vantio-loki-tls",
  "-p", "3100:3100",
  "--add-host", "host.docker.internal:host-gateway",
  "-v", `${path.join(root, "grafana/loki-tls.yaml")}:/etc/loki/loki.yaml:ro`,
  "-v", `${certs}:/certs:ro`,
  "grafana/loki:3.4.2", "-config.file=/etc/loki/loki.yaml",
]);
docker([
  "run", "-d", "--name", "vantio-loki-collector",
  "-p", "4518:4318",
  "--add-host", "host.docker.internal:host-gateway",
  "-v", `${path.join(root, "grafana/collector-loki-tls.yaml")}:/etc/otel/config.yaml:ro`,
  "-v", `${certs}:/certs:ro`,
  "otel/opentelemetry-collector-contrib:0.136.0",
  "--config=/etc/otel/config.yaml",
]);
await sleep(4000);
try {
  const exporter = tlsOpts("https://localhost:4518");
  const main = await deliverRows(exporter, trio("loki-tls"));
  const extra = await pushPrivacyAndForged(exporter, "loki-tls");
  exporter.stop();
  await sleep(1500);
  const queried = await httpsText("/loki/api/v1/query_range?query=%7Bservice_name%3D%22vantio-optics%22%7D&limit=5", 3100);
  const bad = await badCa("https://localhost:3100/otlp/v1/logs");
  report.loki = {
    health: main.status.health,
    sent: main.status.sent,
    schema: queried.body.includes("1.0.0"),
    block: queried.body.includes("BLOCK"),
    hits: leakHits(queried.body),
    forged: extra.forged.reason,
    forged_marker: queried.body.includes("FORGED-WORKLOAD"),
    query_status: queried.status,
    bad_direct: bad,
  };
} catch (err) {
  report.loki_error = String(err && err.message ? err.message : err);
  try { report.loki_log = execFileSync("sudo", ["docker", "logs", "vantio-loki-tls"], { encoding: "utf8" }).slice(-800); } catch { /* */ }
}
save();
console.log("LOKI", JSON.stringify(report.loki || report.loki_error));

const seen = [];
const hook = https.createServer({
  cert: readFileSync(path.join(certs, "server.pem")),
  key: readFileSync(path.join(certs, "server.key")),
  ca, requestCert: true, rejectUnauthorized: true,
}, (req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("end", () => {
    seen.push(Buffer.concat(chunks).toString("utf8"));
    res.writeHead(200, { "content-type": "text/plain" });
    res.end("ok");
  });
});
await new Promise((resolve) => hook.listen(9443, "127.0.0.1", resolve));
const sink = await new Promise((resolve) => {
  const server = http.createServer((req, res) => { req.resume(); res.writeHead(200, { "content-type": "application/json" }); res.end("{}"); });
  server.listen(0, "127.0.0.1", () => resolve(server));
});
const hookExporter = makeExporter({
  endpoint: `http://127.0.0.1:${sink.address().port}`,
  protocol: "otlp-http-json",
  webhook: "https://localhost:9443/hook",
  caFile: path.join(certs, "ca.pem"),
  certFile: path.join(certs, "client.pem"),
  keyFile: path.join(certs, "client.key"),
  timeoutMs: 4000,
  maxDelayMs: 20,
});
const hookMain = await deliverRows(hookExporter, trio("webhook-tls"));
hookExporter.stop();
const hookBad = makeExporter({
  endpoint: `http://127.0.0.1:${sink.address().port}`,
  protocol: "otlp-http-json",
  webhook: "https://localhost:9443/hook",
  caFile: path.join(certs, "wrong.pem"),
  certFile: path.join(certs, "client.pem"),
  keyFile: path.join(certs, "client.key"),
  timeoutMs: 2000,
  maxDelayMs: 60000,
  maxQueue: 2,
});
send(hookBad, event("webhook-bad"));
await hookBad.flush();
report.webhook = {
  health: hookMain.status.health,
  sent: hookMain.status.sent,
  schema: seen.join("").includes("1.0.0"),
  block: seen.join("").includes("BLOCK"),
  hits: leakHits(seen.join("")),
  bad_sent: hookBad.status().sent,
  bad_error: hookBad.status().lastError,
};
hookBad.stop();
hook.close();
sink.close();
save();
console.log("WEBHOOK", JSON.stringify(report.webhook));

try { docker(["rm", "-f", "vantio-rsyslog-tls"]); } catch { /* */ }
mkdirSync(path.join(root, "rsyslog/out"), { recursive: true });
docker([
  "run", "-d", "--name", "vantio-rsyslog-tls",
  "-p", "6514:6514",
  "-v", `${path.join(root, "rsyslog/rsyslog.tls.conf")}:/etc/rsyslog.conf:ro`,
  "-v", `${path.join(root, "rsyslog/out")}:/out`,
  "-v", `${certs}:/certs:ro`,
  "vantio-rsyslog-tls:local",
]);
await sleep(1500);
const syslogSink = await new Promise((resolve) => {
  const server = http.createServer((req, res) => { req.resume(); res.writeHead(200, { "content-type": "application/json" }); res.end("{}"); });
  server.listen(0, "127.0.0.1", () => resolve(server));
});
const syslogExporter = makeExporter({
  endpoint: `http://127.0.0.1:${syslogSink.address().port}`,
  protocol: "otlp-http-json",
  syslog: "tls://localhost:6514",
  caFile: path.join(certs, "ca.pem"),
  certFile: path.join(certs, "client.pem"),
  keyFile: path.join(certs, "client.key"),
  timeoutMs: 4000,
  maxDelayMs: 20,
});
const syslogMain = await deliverRows(syslogExporter, trio("syslog-tls"));
syslogExporter.stop();
await sleep(500);
let syslogBody = "";
try { syslogBody = execFileSync("sudo", ["docker", "exec", "vantio-rsyslog-tls", "cat", "/out/syslog.log"], { encoding: "utf8" }); } catch (err) { syslogBody = String(err.stderr || err.message); }
const syslogBad = makeExporter({
  endpoint: `http://127.0.0.1:${syslogSink.address().port}`,
  protocol: "otlp-http-json",
  syslog: "tls://localhost:6514",
  caFile: path.join(certs, "wrong.pem"),
  certFile: path.join(certs, "client.pem"),
  keyFile: path.join(certs, "client.key"),
  timeoutMs: 2000,
  maxDelayMs: 60000,
  maxQueue: 2,
});
send(syslogBad, event("syslog-bad"));
await syslogBad.flush();
report.syslog = {
  health: syslogMain.status.health,
  sent: syslogMain.status.sent,
  last: syslogMain.status.lastError,
  schema: syslogBody.includes("1.0.0"),
  block: syslogBody.includes("BLOCK"),
  hits: leakHits(syslogBody),
  bad_sent: syslogBad.status().sent,
  bad_error: syslogBad.status().lastError,
  log: syslogBody.slice(0, 400),
};
syslogBad.stop();
syslogSink.close();
save();
console.log("SYSLOG", JSON.stringify(report.syslog));

docker(["rm", "-f", "vantio-loki-tls", "vantio-loki-collector", "vantio-rsyslog-tls"]);
console.log("REST_DONE");
save();
