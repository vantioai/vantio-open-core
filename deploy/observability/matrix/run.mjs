import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  CANARIES,
  DIGEST,
  SCHEMA,
  cell,
  deliverRows,
  docker,
  encodings,
  event,
  hostileProbe,
  leakHits,
  makeExporter,
  prepareDir,
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
mkdirSync(outDir, { recursive: true });

const STRING_FIELDS = ["destination_host", "executable", "workload_id", "path", "optics_status", "application_status"];

function privacyRows(tag) {
  const rows = [];
  const dirty = event(`${tag}-dirty`, {
    path: "/v1/chat/completions?CANARY-QUERYSTRING=1",
    prompt: "CANARY-PROMPTTEXT",
    completion: "CANARY-COMPLETION",
    body: "CANARY-BODYTEXT",
    headers: { authorization: "CANARY-HEADERVALUE" },
  });
  rows.push(dirty);
  for (const field of STRING_FIELDS) {
    for (const form of Object.values(encodings("CANARY-PROMPTTEXT"))) {
      const value = field === "path" ? `/${form}` : form;
      rows.push(event(`${tag}-${field}`, { [field]: value, span_id: undefined }));
    }
  }
  rows.push(event(`${tag}-split`, { workload_id: "cana", path: "ry-prompttext" }));
  rows.push(event(`${tag}-split3`, { workload_id: "can", executable: "ary", path: "-prompttext" }));
  return rows;
}

function forgedEvent(tag) {
  return event(`${tag}-forged`, {
    workload_id: "FORGED-WORKLOAD-9f3a",
    destination_host: "forged.example",
  });
}

async function pushPrivacyAndForged(exporter, tag) {
  const privacy = [];
  for (const row of privacyRows(tag)) {
    if (row.span_id == null) row.span_id = event(`${tag}-pad`).span_id;
    privacy.push(send(exporter, row));
  }
  const forged = exporter.offer(forgedEvent(tag), "not-the-token");
  const unbound = exporter.offer(forgedEvent(`${tag}-unbound`), exporter.token);
  await exporter.flush();
  return { privacy, forged, unbound, status: exporter.status() };
}

function judgeStorage(name, blob, tag, extra) {
  const trace = traceId(tag);
  const hits = leakHits(blob);
  const hasSchema = blob.includes(SCHEMA) && blob.includes(trace);
  const hasKinds = blob.includes("optics.observation") && blob.includes("phantom.decision") && blob.includes("enterprise.evidence");
  const hasBlock = blob.includes("BLOCK") && blob.includes(DIGEST);
  const forgedAbsent = !blob.includes("FORGED-WORKLOAD-9f3a");
  const stored = hasSchema && blob.includes("api.openai.com");
  return {
    destination: name,
    bind: "attestObservation+token",
    rows: {
      1: cell(hasSchema ? "PASS" : "FAIL", hasSchema ? `schema ${SCHEMA} and trace ${trace} found` : "schema or trace missing"),
      2: cell(hasKinds && blob.includes(trace) ? "PASS" : "FAIL", "shared trace across optics, phantom.decision, enterprise.evidence"),
      3: cell(hasBlock ? "PASS" : "FAIL", `BLOCK and ${DIGEST}`),
      4: cell(
        stored && hits.length === 0 ? "PASS" : (stored ? "FAIL" : "GAP"),
        stored ? (hits.length ? hits.slice(0, 12).join(",") : "stored event present and no canary literal, encoding, or split half") : "storage had no successful event, so privacy was not checked there",
      ),
      10: cell(
        stored && forgedAbsent && extra.forged.reason === "UNATTESTED" && extra.unbound.reason === "UNATTESTED" ? "PASS" : (stored ? "FAIL" : "GAP"),
        `forged ${extra.forged.reason}; unbound ${extra.unbound.reason}; marker absent=${forgedAbsent}; stored=${stored}`,
      ),
    },
    hits,
  };
}

async function collectorOnce(protocol, endpoint, tag) {
  const out = path.join(root, "collector/out");
  rmSync(out, { recursive: true, force: true });
  prepareDir(out);
  writeFileSync(path.join(out, "traces.json"), "");
  writeFileSync(path.join(out, "logs.json"), "");
  execFileSync("chmod", ["0666", path.join(out, "traces.json"), path.join(out, "logs.json")]);
  docker(["compose", "-f", path.join(root, "collector/compose.yaml"), "up", "-d", "--force-recreate"], { inherit: true });
  const port = endpoint.includes("4317") ? 4317 : 4318;
  if (!(await waitForPort(port))) throw new Error(`collector port ${port} closed`);
  const running = docker(["inspect", "-f", "{{.State.Running}}", "collector-collector-1"]).trim();
  if (running !== "true") throw new Error(`collector not running: ${docker(["logs", "--tail", "20", "collector-collector-1"])}`);
  await sleep(500);
  const exporter = makeExporter({ endpoint, protocol, compression: "gzip" });
  const main = await deliverRows(exporter, trio(tag));
  const extra = await pushPrivacyAndForged(exporter, tag);
  exporter.stop();
  await sleep(1500);
  const blob = `${readText(path.join(out, "traces.json"))}\n${readText(path.join(out, "logs.json"))}`;
  const judged = judgeStorage(`collector:${protocol}`, blob, tag, extra);
  judged.mainStatus = main.status;
  judged.bytes = blob.length;
  if (main.status.health !== "healthy" || main.status.sent < 3) {
    judged.rows[1] = cell("FAIL", `health ${main.status.health} sent ${main.status.sent} ${main.status.lastError || ""}`);
  }
  return judged;
}

async function throughput(endpoint, protocol, tag) {
  const exporter = makeExporter({
    endpoint,
    protocol,
    compression: "gzip",
    maxBatch: 100,
    maxQueue: 2000,
    timeoutMs: 8000,
  });
  const before = process.cpuUsage();
  const rss0 = process.memoryUsage().rss;
  const started = process.hrtime.bigint();
  for (let i = 0; i < 1000; i += 1) {
    send(exporter, event(`${tag}-${i}`, { span_id: (0x1000000000000000n + BigInt(i)).toString(16).slice(0, 16) }));
  }
  await exporter.flush();
  const ms = Number(process.hrtime.bigint() - started) / 1e6;
  const cpu = process.cpuUsage(before);
  const status = exporter.status();
  exporter.stop();
  return {
    ms: Number(ms.toFixed(1)),
    cpu_user_us: cpu.user,
    cpu_system_us: cpu.system,
    rss_delta: process.memoryUsage().rss - rss0,
    sent: status.sent,
    health: status.health,
    dropped: status.dropped,
  };
}

async function runCollector() {
  const protocols = [
    ["otlp-http-json", "http://127.0.0.1:4318", "collector-json"],
    ["otlp-http-protobuf", "http://127.0.0.1:4318", "collector-proto"],
    ["otlp-grpc", "http://127.0.0.1:4317", "collector-grpc"],
  ];
  const reports = [];
  for (const [protocol, endpoint, tag] of protocols) {
    const judged = await collectorOnce(protocol, endpoint, tag);
    const hostile = await hostileProbe(tag);
    judged.rows[6] = cell(
      hostile.pass ? "GAP" : "FAIL",
      `local stand-in slow ${hostile.slowMs}ms health ${hostile.slowHealth}; 500 ${hostile.badHealth}; reset ${hostile.resetHealth}. Not induced from the collector process.`,
    );
    if (hostile.pass) {
      judged.rows[6].evidence += " Stand-in did not crash the sender. Destination row stays GAP.";
    }
    reports.push(judged);
    console.log(protocol, JSON.stringify(judged.rows));
  }
  const speed = await throughput("http://127.0.0.1:4318", "otlp-http-json", "collector-speed");
  const speedPass = speed.sent === 1000 && speed.health === "healthy" && speed.dropped === 0;
  const summary = {
    destination: "collector",
    reports,
    throughput: speed,
    rows: {
      7: cell(speedPass ? "PASS" : "FAIL", JSON.stringify(speed)),
      5: cell("GAP", "10-minute down plus recovery is a separate phase"),
      8: cell("GAP", "TLS not configured on this collector yet"),
      9: cell("GAP", "older collector image not run yet"),
    },
  };
  const file = writeResult(outDir, "collector", summary);
  console.log("WROTE", file);
}

const phase = process.argv[2] || "collector";
if (phase === "collector") {
  await runCollector();
} else {
  console.error("unknown phase", phase);
  process.exit(1);
}
