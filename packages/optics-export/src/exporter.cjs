"use strict";

const dgram = require("node:dgram");
const fs = require("node:fs");
const http = require("node:http");
const http2 = require("node:http2");
const https = require("node:https");
const net = require("node:net");
const zlib = require("node:zlib");
const { createHash, randomBytes } = require("node:crypto");
const { SCHEMA_VERSION } = require("./schema.cjs");
const { project } = require("./privacy.cjs");
const { logsJson, logsProto, tracesJson, tracesProto } = require("./otlp.cjs");
const { syslogLine } = require("./syslog.cjs");

function producerToken() {
  return randomBytes(16).toString("hex");
}

// Same-process source binding. A copied object is not attested.
// This is not a Phantom Engine signature.
const sourceRegistry = new WeakMap();

function stableEvent(value, seen) {
  if (value === undefined || value === null) return "null";
  const kind = typeof value;
  if (kind === "string" || kind === "number" || kind === "boolean") return JSON.stringify(value);
  if (kind !== "object") return null;
  if (seen.has(value)) return null;
  seen.add(value);
  if (Array.isArray(value)) {
    const parts = [];
    for (const item of value) {
      const encoded = stableEvent(item, seen);
      if (encoded == null) return null;
      parts.push(encoded);
    }
    return `[${parts.join(",")}]`;
  }
  const parts = [];
  for (const key of Object.keys(value).sort()) {
    const encoded = stableEvent(value[key], seen);
    if (encoded == null) return null;
    parts.push(`${JSON.stringify(key)}:${encoded}`);
  }
  return `{${parts.join(",")}}`;
}

function digestEvent(event) {
  const encoded = stableEvent(event, new Set());
  if (encoded == null) return null;
  return createHash("sha256").update(encoded).digest("hex");
}

function freezeDeep(value, seen) {
  if (value === null || typeof value !== "object") return;
  if (seen.has(value)) return;
  seen.add(value);
  if (Array.isArray(value)) {
    for (const item of value) freezeDeep(item, seen);
  } else {
    for (const key of Object.keys(value)) freezeDeep(value[key], seen);
  }
  Object.freeze(value);
}

function plainClone(value, seen) {
  if (value === undefined || value === null) return value;
  const kind = typeof value;
  if (kind === "string" || kind === "number" || kind === "boolean") return value;
  if (kind !== "object") return null;
  if (seen.has(value)) return null;
  seen.add(value);
  if (Array.isArray(value)) {
    const copy = [];
    for (const item of value) {
      const child = plainClone(item, seen);
      if (child === null && item !== null) return null;
      copy.push(child);
    }
    return copy;
  }
  const copy = {};
  for (const key of Object.keys(value)) {
    const child = plainClone(value[key], seen);
    if (child === null && value[key] !== null) return null;
    copy[key] = child;
  }
  return copy;
}

function attestObservation(event) {
  if (event === null || typeof event !== "object" || Array.isArray(event)) {
    return { ok: false, reason: "MALFORMED" };
  }
  let snapshot = null;
  try {
    snapshot = plainClone(event, new Set());
  } catch {
    snapshot = null;
  }
  if (!snapshot || Array.isArray(snapshot)) return { ok: false, reason: "MALFORMED" };
  let digest = null;
  try {
    digest = digestEvent(snapshot);
  } catch {
    digest = null;
  }
  if (!digest) return { ok: false, reason: "MALFORMED" };
  try {
    freezeDeep(snapshot, new Set());
  } catch {
    return { ok: false, reason: "MALFORMED" };
  }
  sourceRegistry.set(event, { digest, snapshot });
  return { ok: true, attestation: "producer" };
}

function observationAttestation(event) {
  if (event === null || typeof event !== "object" || Array.isArray(event)) {
    return { state: "unattested", snapshot: null };
  }
  const stored = sourceRegistry.get(event);
  if (!stored) return { state: "unattested", snapshot: null };
  let live = null;
  try {
    live = plainClone(event, new Set());
  } catch {
    return { state: "mismatch", snapshot: stored.snapshot };
  }
  let digest = null;
  try {
    digest = live ? digestEvent(live) : null;
  } catch {
    digest = null;
  }
  if (!digest || digest !== stored.digest) return { state: "mismatch", snapshot: stored.snapshot };
  return { state: "producer", snapshot: stored.snapshot };
}

function tlsOptions(config) {
  const options = { rejectUnauthorized: true };
  if (config.caFile) options.ca = fs.readFileSync(config.caFile);
  if (config.certFile) options.cert = fs.readFileSync(config.certFile);
  if (config.keyFile) options.key = fs.readFileSync(config.keyFile);
  return options;
}

function endpointURL(config, suffix) {
  const url = new URL(config.endpoint);
  if (config.protocol === "otlp-grpc") return url;
  if (!url.pathname || url.pathname === "/") url.pathname = suffix;
  return url;
}

function postHTTP(config, suffix, body, contentType) {
  const url = endpointURL(config, suffix);
  const payload = config.compression === "gzip" ? zlib.gzipSync(body) : body;
  const headers = {
    ...config.headers,
    "content-type": contentType,
    "content-length": String(payload.length),
  };
  if (config.compression === "gzip") headers["content-encoding"] = "gzip";
  const lib = url.protocol === "https:" ? https : http;
  const agent = url.protocol === "https:" ? config.httpsAgent : config.httpAgent;
  const options = {
    protocol: url.protocol,
    hostname: url.hostname,
    port: url.port || (url.protocol === "https:" ? 443 : 80),
    path: `${url.pathname}${url.search}`,
    method: "POST",
    headers,
    agent,
    ...(url.protocol === "https:" ? tlsOptions(config) : {}),
  };
  return new Promise((resolve, reject) => {
    let settled = false;
    let req;
    let timer;
    const finish = (err) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (req && !req.destroyed) req.destroy();
      if (err) reject(err);
      else resolve();
    };
    timer = setTimeout(() => {
      finish(Object.assign(new Error("TIMEOUT"), { code: "TIMEOUT" }));
    }, config.timeoutMs);
    req = lib.request(options, (res) => {
      res.resume();
      res.on("aborted", () => finish(Object.assign(new Error("ABORTED"), { code: "ABORTED" })));
      res.on("end", () => {
        if (res.statusCode >= 200 && res.statusCode < 300) finish();
        else finish(Object.assign(new Error("HTTP_STATUS"), { code: `HTTP_${res.statusCode}` }));
      });
    });
    req.on("error", (err) => finish(err));
    req.end(payload);
  });
}

function grpcFrame(message) {
  const payload = message;
  const head = Buffer.alloc(5);
  head[0] = 0;
  head.writeUInt32BE(payload.length, 1);
  return Buffer.concat([head, payload]);
}

function postGRPC(config, service, message) {
  const url = new URL(config.endpoint);
  const origin = `${url.protocol}//${url.host}`;
  const options = url.protocol === "https:" ? tlsOptions(config) : {};
  return new Promise((resolve, reject) => {
    let session;
    let timer;
    let settled = false;
    const finish = (err) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      if (session && !session.destroyed) session.destroy();
      if (err) reject(err);
      else resolve();
    };
    try {
      session = http2.connect(origin, options);
    } catch (err) {
      reject(err);
      return;
    }
    if (typeof session.unref === "function") session.unref();
    timer = setTimeout(() => {
      finish(Object.assign(new Error("TIMEOUT"), { code: "TIMEOUT" }));
    }, config.timeoutMs);
    session.on("error", (err) => finish(err));
    let req;
    try {
      req = session.request({
        ":method": "POST",
        ":path": `/${service}/Export`,
        "content-type": "application/grpc",
        te: "trailers",
        ...config.headers,
      });
    } catch (err) {
      finish(err);
      return;
    }
    let status = "missing";
    let httpStatus = null;
    req.on("trailers", (trailers) => {
      if (trailers["grpc-status"] != null) status = String(trailers["grpc-status"]);
    });
    req.on("response", (headers) => {
      httpStatus = headers[":status"] == null ? null : String(headers[":status"]);
      if (headers["grpc-status"] != null) status = String(headers["grpc-status"]);
      if (httpStatus && Number(httpStatus) >= 400) status = "http";
    });
    req.on("error", (err) => finish(err));
    req.resume();
    req.on("end", () => {
      if (status === "0" || (status === "missing" && httpStatus === "200")) finish();
      else finish(Object.assign(new Error("GRPC_STATUS"), { code: `GRPC_${status}` }));
    });
    req.end(grpcFrame(message));
  });
}

function writeJsonl(config, events) {
  if (!config.jsonlPath) return;
  const lines = events.map((event) => JSON.stringify({ schema_version: SCHEMA_VERSION, ...event })).join("\n") + "\n";
  const dir = require("node:path").dirname(config.jsonlPath);
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  let size = 0;
  try {
    size = fs.statSync(config.jsonlPath).size;
  } catch {
    size = 0;
  }
  if (size + Buffer.byteLength(lines) > config.jsonlMaxBytes) {
    fs.writeFileSync(config.jsonlPath, lines, { mode: 0o600 });
    return;
  }
  fs.appendFileSync(config.jsonlPath, lines, { mode: 0o600 });
}

function sendSyslog(config, events) {
  if (!config.syslog) return Promise.resolve();
  const target = new URL(config.syslog);
  const lines = events.map((event) => syslogLine(event, target.hostname));
  if (target.protocol === "udp:") {
    return new Promise((resolve, reject) => {
      const socket = dgram.createSocket("udp4");
      let settled = false;
      let left = lines.length;
      const finish = (err) => {
        if (settled) return;
        settled = true;
        socket.close();
        if (err) reject(err);
        else resolve();
      };
      socket.once("error", finish);
      if (left === 0) {
        finish();
        return;
      }
      for (const line of lines) {
        socket.send(line, Number(target.port || 514), target.hostname, (err) => {
          if (err) finish(err);
          left -= 1;
          if (left === 0) finish();
        });
      }
    });
  }
  return new Promise((resolve, reject) => {
    let settled = false;
    const socket = net.connect(Number(target.port || 514), target.hostname, () => {
      socket.end(`${lines.join("\n")}\n`);
    });
    const finish = (err) => {
      if (settled) return;
      settled = true;
      if (!socket.destroyed) socket.destroy();
      if (err) reject(err);
      else resolve();
    };
    socket.setTimeout(config.timeoutMs, () => finish(Object.assign(new Error("TIMEOUT"), { code: "TIMEOUT" })));
    socket.on("error", finish);
    socket.on("close", () => finish());
  });
}

function sendWebhook(config, events) {
  if (!config.webhook) return Promise.resolve();
  const body = Buffer.from(JSON.stringify({ schema_version: SCHEMA_VERSION, events }));
  return postHTTP({ ...config, endpoint: config.webhook, protocol: "otlp-http-json", compression: "none" }, "", body, "application/json");
}

async function postOptionalLogs(send) {
  try {
    await send();
  } catch (err) {
    if (err && (err.code === "HTTP_404" || err.code === "GRPC_12" || err.code === "GRPC_UNIMPLEMENTED")) return;
    throw err;
  }
}

async function deliver(config, events) {
  const now = BigInt(Date.now()) * 1_000_000n;
  if (config.protocol === "otlp-http-json") {
    await postHTTP(config, "/v1/traces", Buffer.from(JSON.stringify(tracesJson(events, now))), "application/json");
    await postOptionalLogs(() => postHTTP(config, "/v1/logs", Buffer.from(JSON.stringify(logsJson(events, now))), "application/json"));
  } else if (config.protocol === "otlp-http-protobuf") {
    await postHTTP(config, "/v1/traces", tracesProto(events, now), "application/x-protobuf");
    await postOptionalLogs(() => postHTTP(config, "/v1/logs", logsProto(events, now), "application/x-protobuf"));
  } else if (config.protocol === "otlp-grpc") {
    await postGRPC(config, "opentelemetry.proto.collector.trace.v1.TraceService", tracesProto(events, now));
    await postOptionalLogs(() => postGRPC(config, "opentelemetry.proto.collector.logs.v1.LogsService", logsProto(events, now)));
  }
  writeJsonl(config, events);
  await sendSyslog(config, events);
  await sendWebhook(config, events);
}

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function createExporter(config) {
  const token = producerToken();
  const httpAgent = new http.Agent({ keepAlive: false, maxSockets: 8 });
  const httpsAgent = new https.Agent({ keepAlive: false, maxSockets: 8 });
  const runtime = { ...config, httpAgent, httpsAgent };
  const queue = [];
  const state = {
    health: config.enabled ? "idle" : "disabled",
    dropped: 0,
    rejected: 0,
    sent: 0,
    lastError: null,
    backoff: 200,
  };
  let timer = null;
  let pumpPromise = null;
  let stopped = false;

  function snapshot() {
    return {
      health: state.health,
      queued: queue.length,
      dropped: state.dropped,
      rejected: state.rejected,
      sent: state.sent,
      lastError: state.lastError,
      schema_version: SCHEMA_VERSION,
    };
  }

  function enqueue(event) {
    const bytes = Buffer.byteLength(JSON.stringify(event));
    if (queue.length >= config.maxQueue) {
      state.dropped += 1;
      state.health = "degraded";
      return false;
    }
    queue.push({ event, bytes });
    return true;
  }

  function restore(batch) {
    const room = config.maxQueue - queue.length;
    const keep = batch.slice(0, Math.max(room, 0));
    const lost = batch.length - keep.length;
    for (let i = keep.length - 1; i >= 0; i -= 1) queue.unshift({ event: keep[i], bytes: 0 });
    state.dropped += lost;
  }

  function pump() {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (pumpPromise || !config.enabled || stopped) return pumpPromise || Promise.resolve();
    pumpPromise = (async () => {
      while (queue.length && !stopped) {
        const batch = queue.splice(0, config.maxBatch).map((row) => row.event);
        try {
          await deliver(runtime, batch);
          state.sent += batch.length;
          state.health = "healthy";
          state.backoff = 200;
          state.lastError = null;
        } catch (err) {
          restore(batch);
          state.health = "down";
          state.lastError = err && err.code ? String(err.code) : "SEND_FAILED";
          state.backoff = Math.min(state.backoff * 2, 30000);
          await wait(Math.min(state.backoff, config.maxDelayMs));
          break;
        }
      }
    })().finally(() => {
      pumpPromise = null;
      if (queue.length && !stopped) schedule();
    });
    return pumpPromise;
  }

  function schedule() {
    if (timer || !config.enabled || stopped) return;
    timer = setTimeout(() => {
      timer = null;
      pump().catch(() => {
        state.health = "down";
      });
    }, config.maxDelayMs);
    if (typeof timer.unref === "function") timer.unref();
  }

  async function flush(options = {}) {
    const drain = options.drain === true;
    const timeoutMs = Number(options.timeoutMs) > 0 ? Number(options.timeoutMs) : 5000;
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      await pump();
      if (!queue.length || stopped || !drain) return;
      if (Date.now() >= deadline) return;
      await wait(Math.min(state.backoff, config.maxDelayMs));
    }
  }

  function offer(input, tokenValue) {
    try {
      if (!config.enabled) return { accepted: false, reason: "DISABLED" };
      if (tokenValue !== token) {
        state.rejected += 1;
        return { accepted: false, reason: "UNATTESTED" };
      }
      const bound = observationAttestation(input);
      if (bound.state !== "producer") {
        state.rejected += 1;
        return {
          accepted: false,
          reason: bound.state === "mismatch" ? "ATTESTATION_MISMATCH" : "UNATTESTED",
        };
      }
      const projected = project(bound.snapshot);
      if (!projected.ok) {
        state.rejected += 1;
        return { accepted: false, reason: projected.reason };
      }
      const ok = enqueue(projected.event);
      if (!ok) return { accepted: false, reason: "DROPPED" };
      if (queue.length >= config.maxBatch) {
        if (timer) clearTimeout(timer);
        timer = null;
        pump().catch(() => {
          state.health = "down";
        });
      } else schedule();
      return { accepted: true };
    } catch {
      state.dropped += 1;
      return { accepted: false, reason: "INTERNAL" };
    }
  }

  return {
    token,
    offer,
    status: snapshot,
    flush,
    stop() {
      stopped = true;
      if (timer) clearTimeout(timer);
      timer = null;
      httpAgent.destroy();
      httpsAgent.destroy();
    },
  };
}

module.exports = {
  attestObservation,
  createExporter,
  deliver,
  producerToken,
};
