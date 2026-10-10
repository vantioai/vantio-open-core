import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import http from "node:http";
import https from "node:https";
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
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const certs = "/tmp/vantio-matrix/certs";
const outFile = "/tmp/vantio-matrix/tls-final.json";
const report = { destinations: {} };

function save() {
  mkdirSync("/tmp/vantio-matrix", { recursive: true });
  writeFileSync(outFile, JSON.stringify(report, null, 2));
}

function openssl(args) {
  execFileSync("openssl", args, { cwd: certs, stdio: "ignore" });
}

function makeCerts() {
  mkdirSync(certs, { recursive: true });
  openssl(["req", "-x509", "-newkey", "rsa:2048", "-keyout", "ca.key", "-out", "ca.pem", "-days", "1", "-nodes", "-subj", "/CN=vantio-test-ca"]);
  writeFileSync(path.join(certs, "san.cnf"), "subjectAltName=DNS:localhost,DNS:host.docker.internal,IP:127.0.0.1\n");
  openssl(["req", "-newkey", "rsa:2048", "-keyout", "server.key", "-out", "server.csr", "-nodes", "-subj", "/CN=localhost"]);
  openssl(["x509", "-req", "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "server.pem", "-days", "1", "-extfile", "san.cnf"]);
  openssl(["req", "-newkey", "rsa:2048", "-keyout", "client.key", "-out", "client.csr", "-nodes", "-subj", "/CN=vantio-export"]);
  openssl(["x509", "-req", "-in", "client.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "client.pem", "-days", "1"]);
  openssl(["req", "-x509", "-newkey", "rsa:2048", "-keyout", "wrong.key", "-out", "wrong.pem", "-days", "1", "-nodes", "-subj", "/CN=wrong"]);
  execFileSync("chmod", ["-R", "a+rX", certs]);
}

function tlsExporter(url, protocol, extra = {}) {
  return makeExporter({
    endpoint: url,
    protocol,
    caFile: path.join(certs, "ca.pem"),
    certFile: path.join(certs, "client.pem"),
    keyFile: path.join(certs, "client.key"),
    timeoutMs: 8000,
    maxDelayMs: 20,
    maxQueue: 64,
    ...extra,
  });
}

async function goodAndBad(name, url, protocol, readStorage) {
  const good = tlsExporter(url, protocol);
  const main = await deliverRows(good, trio(`${name}-tls`));
  const extra = await pushPrivacyAndForged(good, `${name}-tls`);
  good.stop();
  await sleep(800);
  const storage = await readStorage();
  const bad = tlsExporter(url, protocol, {
    caFile: path.join(certs, "wrong.pem"),
    timeoutMs: 2000,
    maxDelayMs: 60000,
    maxQueue: 2,
  });
  send(bad, event(`${name}-badca`));
  await bad.flush();
  const badStatus = bad.status();
  bad.stop();
  const unbound = extra.unbound.reason;
  report.destinations[name] = {
    health: main.status.health,
    sent: main.status.sent,
    last: main.status.lastError,
    schema: storage.includes("1.0.0"),
    block: storage.includes("BLOCK"),
    hits: leakHits(storage),
    forged: extra.forged.reason,
    unbound,
    forged_marker: storage.includes("FORGED-WORKLOAD"),
    bad_ca_sent: badStatus.sent,
    bad_ca_health: badStatus.health,
    bad_ca_error: badStatus.lastError,
  };
  save();
  console.log("DEST", name, JSON.stringify(report.destinations[name]));
}

async function textFetch(url, opts = {}) {
  const buf = await new Promise((resolve, reject) => {
    const lib = url.startsWith("https:") ? https : http;
    const req = lib.get(url, opts, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    });
    req.on("error", reject);
  });
  return buf;
}

makeCerts();
const tlsGet = {
  ca: execFileSync("cat", [path.join(certs, "ca.pem")]),
  cert: execFileSync("cat", [path.join(certs, "client.pem")]),
  key: execFileSync("cat", [path.join(certs, "client.key")]),
  rejectUnauthorized: true,
  servername: "localhost",
};

try {
  docker(["rm", "-f", "vantio-jaeger-tls"]);
} catch { /* none */ }
docker([
  "run", "-d", "--name", "vantio-jaeger-tls",
  "-p", "4320:4318", "-p", "4319:4317", "-p", "16686:16686",
  "-v", `${certs}:/certs:ro`,
  "jaegertracing/all-in-one:1.62.0",
  "--collector.otlp.http.tls.enabled=true",
  "--collector.otlp.http.tls.cert=/certs/server.pem",
  "--collector.otlp.http.tls.key=/certs/server.key",
  "--collector.otlp.http.tls.client-ca=/certs/ca.pem",
  "--collector.otlp.grpc.tls.enabled=true",
  "--collector.otlp.grpc.tls.cert=/certs/server.pem",
  "--collector.otlp.grpc.tls.key=/certs/server.key",
  "--collector.otlp.grpc.tls.client-ca=/certs/ca.pem",
]);
await sleep(2500);
try {
  await goodAndBad("jaeger-http", "https://localhost:4320", "otlp-http-json", async () => {
    const id = (await import("node:crypto")).createHash("sha256").update("jaeger-http-tls").digest("hex").slice(0, 32);
    return textFetch(`http://127.0.0.1:16686/api/traces/${id}`);
  });
  await goodAndBad("jaeger-grpc", "https://localhost:4319", "otlp-grpc", async () => {
    const id = (await import("node:crypto")).createHash("sha256").update("jaeger-grpc-tls").digest("hex").slice(0, 32);
    return textFetch(`http://127.0.0.1:16686/api/traces/${id}`);
  });
  const pace = tlsExporter("https://localhost:4320", "otlp-http-json", { maxQueue: 2000, maxBatch: 32 });
  const cpu = process.cpuUsage();
  const mem = process.memoryUsage();
  const t0 = Date.now();
  let accepted = 0;
  for (let i = 0; i < 300; i += 1) {
    if (send(pace, event(`jaeger-pace-${i}`, { span_id: (i + 1).toString(16).padStart(16, "0") })).accepted) accepted += 1;
  }
  await pace.flush({ drain: true, timeoutMs: 20000 });
  const cpuAfter = process.cpuUsage(cpu);
  report.throughput = {
    destination: "jaeger-http-tls",
    accepted,
    elapsed_ms: Date.now() - t0,
    cpu_user_us: cpuAfter.user,
    cpu_system_us: cpuAfter.system,
    rss_delta_bytes: process.memoryUsage().rss - mem.rss,
    ...pace.status(),
  };
  pace.stop();
  save();
} catch (err) {
  report.destinations.jaeger_error = String(err && err.stack ? err.stack : err);
  save();
}
docker(["rm", "-f", "vantio-jaeger-tls"]);

try {
  docker(["rm", "-f", "vantio-tempo-tls"]);
} catch { /* none */ }
docker([
  "run", "-d", "--name", "vantio-tempo-tls",
  "-p", "4348:4318", "-p", "3201:3200",
  "-v", `${path.join(root, "tempo/tempo-tls.yaml")}:/etc/tempo.yaml:ro`,
  "-v", `${certs}:/certs:ro`,
  "grafana/tempo:2.7.1", "-config.file=/etc/tempo.yaml",
]);
await sleep(2000);
try {
  await goodAndBad("tempo-http", "https://localhost:4348", "otlp-http-json", async () => {
    const id = (await import("node:crypto")).createHash("sha256").update("tempo-http-tls").digest("hex").slice(0, 32);
    return textFetch(`http://127.0.0.1:3201/api/traces/${id}`);
  });
} catch (err) {
  report.destinations.tempo_error = String(err && err.stderr ? err.stderr : err.message || err);
  try { report.destinations.tempo_log = docker(["logs", "vantio-tempo-tls"]).slice(-1500); } catch { /* */ }
  save();
}
docker(["rm", "-f", "vantio-tempo-tls"]);

console.log("TLS_PARTIAL", JSON.stringify(report.destinations));
save();
