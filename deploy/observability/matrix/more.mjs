import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  DIGEST,
  SCHEMA,
  cell,
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
  writeResult,
} from "./lib.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = "/tmp/vantio-matrix";

function judge(name, blob, tag, extra) {
  const trace = traceId(tag);
  const hits = leakHits(blob);
  const hasSchema = blob.includes(SCHEMA) && blob.includes(trace);
  const hasKinds = blob.includes("optics.observation") && blob.includes("phantom.decision") && blob.includes("enterprise.evidence");
  const hasBlock = blob.includes("BLOCK") && blob.includes(DIGEST);
  const stored = hasSchema && (blob.includes("api.openai.com") || blob.includes("BLOCK"));
  const forgedAbsent = !blob.includes("FORGED-WORKLOAD-9f3a");
  return {
    destination: name,
    bind: "attestObservation+token",
    rows: {
      1: cell(hasSchema ? "PASS" : "FAIL", hasSchema ? `schema and trace ${trace}` : "schema or trace missing"),
      2: cell(hasKinds && blob.includes(trace) ? "PASS" : "FAIL", "shared trace across three kinds"),
      3: cell(hasBlock ? "PASS" : "FAIL", "BLOCK and policy digest"),
      4: cell(stored && hits.length === 0 ? "PASS" : (stored ? "FAIL" : "GAP"), stored ? (hits.join(",") || "no canary in storage") : "storage empty"),
      10: cell(stored && forgedAbsent && extra.forged.reason === "UNATTESTED" && extra.unbound.reason === "UNATTESTED" ? "PASS" : "GAP", `forged ${extra.forged.reason} unbound ${extra.unbound.reason} absent ${forgedAbsent}`),
    },
    hits,
    bytes: blob.length,
  };
}

async function resetCollectorOut() {
  const out = path.join(root, "collector/out");
  rmSync(out, { recursive: true, force: true });
  prepareDir(out);
  writeFileSync(path.join(out, "traces.json"), "");
  writeFileSync(path.join(out, "logs.json"), "");
  execFileSync("chmod", ["0666", path.join(out, "traces.json"), path.join(out, "logs.json")]);
  return out;
}

async function makeCerts() {
  const dir = "/tmp/vantio-matrix/certs";
  mkdirSync(dir, { recursive: true });
  const openssl = (args) => execFileSync("openssl", args, { cwd: dir, stdio: "ignore" });
  openssl(["req", "-x509", "-newkey", "rsa:2048", "-keyout", "ca.key", "-out", "ca.pem", "-days", "1", "-nodes", "-subj", "/CN=vantio-test-ca"]);
  openssl(["req", "-newkey", "rsa:2048", "-keyout", "server.key", "-out", "server.csr", "-nodes", "-subj", "/CN=localhost"]);
  writeFileSync(path.join(dir, "san.cnf"), "subjectAltName=DNS:localhost,IP:127.0.0.1\n");
  openssl(["x509", "-req", "-in", "server.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "server.pem", "-days", "1", "-extfile", "san.cnf"]);
  openssl(["req", "-newkey", "rsa:2048", "-keyout", "client.key", "-out", "client.csr", "-nodes", "-subj", "/CN=vantio-export"]);
  openssl(["x509", "-req", "-in", "client.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "client.pem", "-days", "1"]);
  openssl(["req", "-x509", "-newkey", "rsa:2048", "-keyout", "wrong.key", "-out", "wrong.pem", "-days", "1", "-nodes", "-subj", "/CN=wrong"]);
  execFileSync("chmod", ["-R", "a+rX", dir]);
  return dir;
}

const phase = process.argv[2] || "";
if (!phase) {
  console.error("phase required");
  process.exit(1);
}

if (phase === "tls") {
  await makeCerts();
  docker(["compose", "-p", "collector", "-f", path.join(root, "collector/compose.yaml"), "down"], { inherit: true });
  const out = await resetCollectorOut();
  docker(["compose", "-p", "vantio-tls", "-f", path.join(root, "collector/compose-tls.yaml"), "up", "-d", "--force-recreate"], { inherit: true });
  if (!(await waitForPort(4318))) throw new Error(docker(["logs", "--tail", "30", "vantio-tls-collector-1"]));
  let ready = false;
  for (let i = 0; i < 20 && !ready; i += 1) {
    const probe = makeExporter({
      endpoint: "https://127.0.0.1:4318",
      protocol: "otlp-http-json",
      caFile: "/tmp/vantio-matrix/certs/ca.pem",
      timeoutMs: 800,
      maxDelayMs: 10,
    });
    send(probe, event(`collector-tls-probe-${i}`));
    await probe.flush();
    ready = probe.status().health === "healthy";
    probe.stop();
    if (!ready) await sleep(250);
  }
  if (!ready) throw new Error(docker(["logs", "--tail", "30", "vantio-tls-collector-1"]));
  const exporter = makeExporter({
    endpoint: "https://127.0.0.1:4318",
    protocol: "otlp-http-json",
    caFile: "/tmp/vantio-matrix/certs/ca.pem",
    compression: "gzip",
  });
  const main = await deliverRows(exporter, trio("collector-tls"));
  const extra = await pushPrivacyAndForged(exporter, "collector-tls");
  exporter.stop();
  await sleep(1200);
  const blob = `${readText(path.join(out, "traces.json"))}\n${readText(path.join(out, "logs.json"))}`;
  const judged = judge("collector-tls", blob, "collector-tls", extra);
  let plain = 0;
  const plainServer = net.createServer(() => { plain += 1; });
  await new Promise((resolve) => plainServer.listen(4321, "127.0.0.1", resolve));
  const bad = makeExporter({
    endpoint: "https://127.0.0.1:4318",
    protocol: "otlp-http-json",
    caFile: "/tmp/vantio-matrix/certs/missing-ca.pem",
    timeoutMs: 800,
  });
  send(bad, event("collector-tls-badca"));
  await bad.flush();
  const badStatus = bad.status();
  bad.stop();
  plainServer.close();
  judged.rows[8] = cell(
    main.status.health === "healthy" && badStatus.health !== "healthy" && plain === 0 && blob.includes("1.0.0") ? "PASS" : "FAIL",
    `tls health ${main.status.health} sent ${main.status.sent}; bad-ca ${badStatus.health} ${badStatus.lastError}; plaintext connections ${plain}`,
  );
  writeResult(outDir, "collector-tls", judged);
  console.log(JSON.stringify(judged.rows, null, 2));
}

if (phase === "mtls") {
  docker(["compose", "-p", "vantio-tls", "-f", path.join(root, "collector/compose-tls.yaml"), "down"], { inherit: true });
  const out = await resetCollectorOut();
  docker(["compose", "-p", "vantio-mtls", "-f", path.join(root, "collector/compose-mtls.yaml"), "up", "-d", "--force-recreate"], { inherit: true });
  if (!(await waitForPort(4318))) throw new Error(docker(["logs", "--tail", "40", "vantio-mtls-collector-1"]));
  const wrong = makeExporter({
    endpoint: "https://127.0.0.1:4318",
    protocol: "otlp-http-json",
    caFile: "/tmp/vantio-matrix/certs/ca.pem",
    certFile: "/tmp/vantio-matrix/certs/wrong.pem",
    keyFile: "/tmp/vantio-matrix/certs/wrong.key",
    timeoutMs: 1500,
  });
  send(wrong, event("collector-mtls-wrong"));
  await wrong.flush();
  const wrongStatus = wrong.status();
  wrong.stop();
  const good = makeExporter({
    endpoint: "https://127.0.0.1:4318",
    protocol: "otlp-http-json",
    caFile: "/tmp/vantio-matrix/certs/ca.pem",
    certFile: "/tmp/vantio-matrix/certs/client.pem",
    keyFile: "/tmp/vantio-matrix/certs/client.key",
    compression: "gzip",
  });
  const main = await deliverRows(good, trio("collector-mtls"));
  good.stop();
  await sleep(1200);
  const blob = readText(path.join(out, "traces.json"));
  const pass = wrongStatus.health !== "healthy" && main.status.health === "healthy" && blob.includes("1.0.0") && !blob.includes(event("collector-mtls-wrong").trace_id);
  writeResult(outDir, "collector-mtls", {
    rows: { 8: cell(pass ? "PASS" : "FAIL", `wrong ${wrongStatus.health} ${wrongStatus.lastError}; good ${main.status.health} sent ${main.status.sent}`) },
    wrong: wrongStatus,
    good: main.status,
  });
  console.log("mtls", pass, wrongStatus, main.status);
}

if (phase === "old") {
  docker(["compose", "-p", "vantio-mtls", "down"], { inherit: true });
  docker(["compose", "-p", "vantio-tls", "down"], { inherit: true });
  const out = await resetCollectorOut();
  docker(["compose", "-p", "vantio-old", "-f", path.join(root, "collector/compose-old.yaml"), "up", "-d", "--force-recreate"], { inherit: true });
  if (!(await waitForPort(4418))) throw new Error(docker(["logs", "--tail", "40", "vantio-old-collector-1"]));
  let ready = false;
  for (let i = 0; i < 20 && !ready; i += 1) {
    const probe = makeExporter({ endpoint: "http://127.0.0.1:4418", protocol: "otlp-http-json", timeoutMs: 800, maxDelayMs: 10 });
    send(probe, event(`collector-old-probe-${i}`));
    await probe.flush();
    ready = probe.status().health === "healthy";
    probe.stop();
    if (!ready) await sleep(250);
  }
  if (!ready) throw new Error("older collector did not accept a probe");
  const exporter = makeExporter({ endpoint: "http://127.0.0.1:4418", protocol: "otlp-http-json", compression: "gzip" });
  const main = await deliverRows(exporter, trio("collector-old"));
  exporter.stop();
  await sleep(1200);
  const blob = `${readText(path.join(out, "traces.json"))}\n${readText(path.join(out, "logs.json"))}`;
  const pass = main.status.health === "healthy" && blob.includes("1.0.0") && blob.includes("BLOCK");
  writeResult(outDir, "collector-old", { rows: { 9: cell(pass ? "PASS" : "FAIL", `0.103.0 health ${main.status.health} sent ${main.status.sent} bytes ${blob.length}`) } });
  console.log("old", pass, main.status.health, blob.length);
}

if (phase === "jaeger") {
  docker(["start", "vantio-jaeger"], { inherit: true });
  if (!(await waitForPort(4320))) throw new Error("jaeger http closed");
  if (!(await waitForPort(16686))) throw new Error("jaeger query closed");
  const exporter = makeExporter({ endpoint: "http://127.0.0.1:4320", protocol: "otlp-http-json", compression: "gzip" });
  const main = await deliverRows(exporter, trio("jaeger-http"));
  const extra = await pushPrivacyAndForged(exporter, "jaeger-http");
  exporter.stop();
  const grpc = makeExporter({ endpoint: "http://127.0.0.1:4319", protocol: "otlp-grpc" });
  const grpcMain = await deliverRows(grpc, trio("jaeger-grpc"));
  grpc.stop();
  await sleep(1500);
  const trace = (await import("./lib.mjs")).traceId("jaeger-http");
  const body = await fetch(`http://127.0.0.1:16686/api/traces/${trace}`).then((res) => res.text());
  const grpcTrace = (await import("./lib.mjs")).traceId("jaeger-grpc");
  const grpcBody = await fetch(`http://127.0.0.1:16686/api/traces/${grpcTrace}`).then((res) => res.text());
  const blob = `${body}\n${grpcBody}`;
  const judged = judge("jaeger", blob, "jaeger-http", extra);
  if (!grpcBody.includes(grpcTrace)) judged.rows[2] = cell("GAP", "http trace stored; grpc trace query did not include the grpc trace id");
  judged.grpcHealth = grpcMain.status;
  judged.httpHealth = main.status;
  writeResult(outDir, "jaeger", judged);
  console.log(JSON.stringify({ http: main.status, grpc: grpcMain.status, rows: judged.rows }, null, 2));
}

if (phase === "syslog") {
  const logDir = path.join(root, "rsyslog/out");
  docker(["start", "vantio-rsyslog"], { inherit: true });
  docker(["exec", "vantio-rsyslog", "sh", "-c", ": > /out/syslog.log"]);
  if (!(await waitForPort(5515))) throw new Error("syslog tcp closed");
  const sink = await okSink();
  for (const target of [`tcp://127.0.0.1:5515`, `udp://127.0.0.1:5514`]) {
    const tag = target.startsWith("tcp") ? "syslog-tcp" : "syslog-udp";
    const exporter = makeExporter({ endpoint: sink.url, protocol: "otlp-http-json", syslog: target, timeoutMs: 2000 });
    await deliverRows(exporter, trio(tag));
    const extra = await pushPrivacyAndForged(exporter, tag);
    exporter.stop();
    await sleep(800);
    const blob = readText(path.join(logDir, "syslog.log"));
    const judged = judge(tag, blob, tag, extra);
    writeResult(outDir, tag, { ...judged, syslogBytes: blob.length });
    console.log(tag, JSON.stringify(judged.rows));
  }
  sink.server.close();
}

if (phase === "webhook") {
  const seen = [];
  const { listenHttp } = await import("./lib.mjs");
  const server = await listenHttp((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      seen.push(Buffer.concat(chunks).toString("utf8"));
      res.writeHead(200);
      res.end("ok");
    });
  });
  const sink = await okSink();
  const exporter = makeExporter({
    endpoint: sink.url,
    protocol: "otlp-http-json",
    webhook: `http://127.0.0.1:${server.address().port}/hook`,
  });
  const main = await deliverRows(exporter, trio("webhook"));
  const extra = await pushPrivacyAndForged(exporter, "webhook");
  exporter.stop();
  const blob = seen.join("\n");
  const judged = judge("webhook", blob, "webhook", extra);
  judged.health = main.status;
  writeResult(outDir, "webhook", judged);
  console.log(JSON.stringify(judged.rows, null, 2));
  server.close();
  sink.server.close();
}
