import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import { attestObservation, createExporter } from "../../../packages/optics-export/src/exporter.cjs";

export const DIGEST = `sha256:${"ab".repeat(32)}`;
export const SCHEMA = "1.0.0";

export const CANARIES = [
  "CANARY-PROMPTTEXT",
  "CANARY-COMPLETION",
  "CANARY-HEADERVALUE",
  "CANARY-BODYTEXT",
  "CANARY-QUERYSTRING",
  "CANARY-HOSTLABEL",
  "CANARY-WORKLOAD",
  "CANARY-PATHTEXT",
  "CANARY-EXECLABEL",
];

export function traceId(tag) {
  const hex = createHash("sha256").update(tag).digest("hex").slice(0, 32);
  return hex.replace(/^0{32}$/, "1".padEnd(32, "0"));
}

export function spanId(tag) {
  const hex = createHash("sha256").update(`span:${tag}`).digest("hex").slice(0, 16);
  return hex.replace(/^0+$/, "1".padEnd(16, "0"));
}

export function encodings(text) {
  const url = [...Buffer.from(text)].map((byte) => `%${byte.toString(16).toUpperCase().padStart(2, "0")}`).join("");
  return {
    raw: text,
    url,
    url2: encodeURIComponent(url),
    b64: Buffer.from(text, "utf8").toString("base64"),
    b64url: Buffer.from(text, "utf8").toString("base64url"),
  };
}

export function event(tag, extra = {}) {
  return {
    kind: "optics.observation",
    trace_id: traceId(tag),
    span_id: spanId(tag),
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
    path: "/v1/chat/completions",
    ...extra,
  };
}

export function trio(tag) {
  const trace = traceId(tag);
  return [
    event(tag, { trace_id: trace, span_id: spanId(`${tag}-o`), kind: "optics.observation" }),
    event(tag, {
      trace_id: trace,
      span_id: spanId(`${tag}-p`),
      kind: "phantom.decision",
      decision: "BLOCK",
      policy_digest: DIGEST,
    }),
    event(tag, {
      trace_id: trace,
      span_id: spanId(`${tag}-e`),
      kind: "enterprise.evidence",
      policy_digest: DIGEST,
    }),
  ];
}

export function makeExporter(extra) {
  return createExporter({
    enabled: true,
    endpoint: "http://127.0.0.1:9",
    protocol: "otlp-http-json",
    headers: {},
    compression: "none",
    maxBatch: 64,
    maxDelayMs: 20,
    maxQueue: 256,
    timeoutMs: 4000,
    jsonlPath: null,
    jsonlMaxBytes: 1024,
    syslog: null,
    webhook: null,
    allowInsecureLocalhost: true,
    ...extra,
  });
}

export function send(exporter, row) {
  const attested = attestObservation(row);
  if (!attested.ok) return { accepted: false, reason: attested.reason || "ATTEST_FAILED" };
  return exporter.offer(row, exporter.token);
}

export async function deliverRows(exporter, rows) {
  const results = rows.map((row) => send(exporter, row));
  await exporter.flush();
  return { results, status: exporter.status() };
}

export function leakHits(blob) {
  const text = String(blob || "");
  const lower = text.toLowerCase();
  const hits = [];
  if (lower.includes("canary")) hits.push("literal:canary");
  if (lower.includes("ry-prompttext")) hits.push("split:ry-prompttext");
  for (const canary of CANARIES) {
    const forms = encodings(canary);
    for (const [name, value] of Object.entries(forms)) {
      if (value && text.includes(value)) hits.push(`${name}:${canary}`);
    }
  }
  return hits;
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function docker(args, opts = {}) {
  return execFileSync("sudo", ["docker", ...args], {
    encoding: "utf8",
    stdio: opts.inherit ? "inherit" : ["ignore", "pipe", "pipe"],
    timeout: opts.timeout || 120000,
  });
}

export function listenHttp(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, "127.0.0.1", () => resolve(server));
  });
}

export async function okSink() {
  const seen = [];
  const server = await listenHttp((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      seen.push({ url: req.url, body: Buffer.concat(chunks).toString("utf8") });
      res.writeHead(200);
      res.end("ok");
    });
  });
  return {
    server,
    seen,
    port: server.address().port,
    url: `http://127.0.0.1:${server.address().port}`,
  };
}

export function cell(result, evidence) {
  return { result, evidence };
}

export function writeResult(dir, name, body) {
  mkdirSync(dir, { recursive: true });
  const path = `${dir}/${name}.json`;
  writeFileSync(path, JSON.stringify(body, null, 2));
  return path;
}

export function prepareDir(dir) {
  mkdirSync(dir, { recursive: true });
  try {
    execFileSync("chmod", ["0777", dir]);
  } catch {
    /* best effort */
  }
}

export function readText(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    try {
      return execFileSync("sudo", ["cat", path], { encoding: "utf8" });
    } catch {
      return "";
    }
  }
}

export async function waitForPort(port, host = "127.0.0.1", attempts = 40) {
  for (let i = 0; i < attempts; i += 1) {
    const open = await new Promise((resolve) => {
      const socket = net.connect(port, host);
      socket.once("connect", () => {
        socket.end();
        resolve(true);
      });
      socket.once("error", () => resolve(false));
      socket.setTimeout(200, () => {
        socket.destroy();
        resolve(false);
      });
    });
    if (open) return true;
    await sleep(250);
  }
  return false;
}

const STRING_FIELDS = ["destination_host", "executable", "workload_id", "path", "optics_status", "application_status"];

export function privacyRows(tag) {
  const rows = [event(`${tag}-dirty`, {
    path: "/v1/chat/completions?CANARY-QUERYSTRING=1",
    prompt: "CANARY-PROMPTTEXT",
    completion: "CANARY-COMPLETION",
    body: "CANARY-BODYTEXT",
    headers: { authorization: "CANARY-HEADERVALUE" },
  })];
  for (const field of STRING_FIELDS) {
    for (const form of Object.values(encodings("CANARY-PROMPTTEXT"))) {
      const value = field === "path" ? `/${form}` : form;
      rows.push(event(`${tag}-${field}-${form.length}`, { [field]: value }));
    }
  }
  rows.push(event(`${tag}-split`, { workload_id: "cana", path: "ry-prompttext" }));
  rows.push(event(`${tag}-split3`, { workload_id: "can", executable: "ary", path: "-prompttext" }));
  return rows;
}

export async function pushPrivacyAndForged(exporter, tag) {
  const privacy = privacyRows(tag).map((row) => send(exporter, row));
  const forged = exporter.offer(event(`${tag}-forged`, { workload_id: "FORGED-WORKLOAD-9f3a", destination_host: "forged.example" }), "not-the-token");
  const unbound = exporter.offer(event(`${tag}-unbound`, { workload_id: "FORGED-WORKLOAD-9f3a" }), exporter.token);
  await exporter.flush();
  return { privacy, forged, unbound, status: exporter.status() };
}

export async function hostileProbe(label) {
  const slow = await listenHttp((_req, res) => {
    setTimeout(() => res.writeHead(500).end("no"), 5000);
  });
  const bad = await listenHttp((req, res) => {
    req.resume();
    res.writeHead(500, { "content-type": "text/plain" });
    res.end("hostile");
  });
  const reset = net.createServer((socket) => socket.destroy());
  await new Promise((resolve) => reset.listen(0, "127.0.0.1", resolve));
  const started = Date.now();
  const exporter = makeExporter({
    endpoint: `http://127.0.0.1:${slow.address().port}`,
    protocol: "otlp-http-json",
    timeoutMs: 80,
    maxDelayMs: 10,
    maxQueue: 4,
  });
  const offered = send(exporter, event(`${label}-slow`));
  await exporter.flush();
  const slowMs = Date.now() - started;
  const slowStatus = exporter.status();
  exporter.stop();

  const badExporter = makeExporter({
    endpoint: `http://127.0.0.1:${bad.address().port}`,
    protocol: "otlp-http-json",
    timeoutMs: 500,
    maxDelayMs: 10,
  });
  send(badExporter, event(`${label}-500`));
  await badExporter.flush();
  const badStatus = badExporter.status();
  badExporter.stop();

  const resetExporter = makeExporter({
    endpoint: `http://127.0.0.1:${reset.address().port}`,
    protocol: "otlp-http-json",
    timeoutMs: 400,
    maxDelayMs: 10,
  });
  send(resetExporter, event(`${label}-reset`));
  await resetExporter.flush();
  const resetStatus = resetExporter.status();
  resetExporter.stop();

  slow.close();
  bad.close();
  reset.close();
  const crashed = false;
  const blocked = slowMs >= 2000 || offered.accepted !== true;
  return {
    slowMs,
    slowHealth: slowStatus.health,
    badHealth: badStatus.health,
    resetHealth: resetStatus.health,
    crashed,
    blocked,
    pass: !crashed && !blocked && slowStatus.health !== "healthy" && badStatus.health !== "healthy",
  };
}
