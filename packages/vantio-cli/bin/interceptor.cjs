// [ ∅ VANTIO ] Open Core Interceptor — Observe Plane
// Injected at runtime by `vantio run node agent.js` via Node --require.
// Patches globalThis.fetch, undici.fetch, undici.request, Client/Pool/Agent
// request() and dispatch(), undici.stream/pipeline/connect/upgrade, Node
// http/https.request|get and ClientRequest, Node http2.connect / session.request,
// Node net.Socket.connect / tls.connect, globalThis.WebSocket / undici.WebSocket
// (host and outbound frame size; payloads are not parsed), undici.upgrade /
// CONNECT tunnel writes, and Node child_process spawn/exec of curl, wget,
// httpie, and aria2c (including env/timeout/nice prefixes, curl -K url=,
// curl -F stat size, wget -i URL lists, and stdin size when stdin is a file.
// File contents and stdin pipes are not read. Optics does not rewrite argv.)
// to in-scope hosts. Browsers stay outside this wrap.
//
// Supported outbound calls are recorded locally: destination, process, size,
// timing, and status. Optics does not block, delay, rewrite, or wait on policy.
// Enforcement is provided by Phantom Engine. A VANTIO_API_KEY does not fetch
// policy and is not sent for enforcement.

"use strict";

const { randomUUID } = require("node:crypto");
const { mkdirSync, writeFileSync, statSync, fstatSync, readFileSync, openSync, readSync, closeSync } = require("node:fs");
const { homedir } = require("node:os");
const { join, basename } = require("node:path");
const { AsyncLocalStorage } = require("node:async_hooks");
const {
  LLM_HOSTS: BASE_LLM_HOSTS,
  hostListed,
  catalogInScope,
  guessProvider,
} = require("./llm-hosts.cjs");
const {
  SCHEMA_STATUS,
  applicationStatusFromHttp,
  humanStatus,
  rollupCalls,
} = require("./optics-cx.cjs");

const USE_COLOR = process.stderr.isTTY === true;
const c = {
  reset:  USE_COLOR ? "\x1b[0m"  : "",
  dim:    USE_COLOR ? "\x1b[2m"  : "",
  bold:   USE_COLOR ? "\x1b[1m"  : "",
  yellow: USE_COLOR ? "\x1b[33m" : "",
  cyan:   USE_COLOR ? "\x1b[36m" : "",
};

const INGEST_URL = process.env.VANTIO_INGEST_URL || "https://vantio.ai";
// Keep the path. Do not reduce the URL to its origin.
function isPublicCloudHost(raw) {
  try {
    const host = new URL(raw).hostname.toLowerCase();
    return host === "vantio.ai" || host === "www.vantio.ai";
  } catch {
    return true;
  }
}
const PUBLIC_CLOUD_HOST = isPublicCloudHost(INGEST_URL);
// Optics is observational. A key in the environment is not an enforcement credential.
if (process.env.VANTIO_API_KEY) {
  process.stderr.write(
    "[ ∅ VANTIO ] VANTIO_API_KEY is set. Enforcement is provided by Phantom Engine. Optics is observational and this call is not blocked.\n"
  );
}
// Stable for the life of this process (set by `vantio run` into child env).
const RUN_TRACE_ID = process.env.VANTIO_TRACE_ID || randomUUID();
// Explicit phantom-box soak only — do NOT infer from localhost (breaks unit tests
// that spin up ephemeral mock control planes on 127.0.0.1).
const SOAK_LOCAL = process.env.VANTIO_SOAK_LOCAL === "1";
// Local control plane (Phantom-Box / dogfood) — never upsell Optics-only.
const LOCAL_GATE = SOAK_LOCAL || /:5001\/?$/.test(String(INGEST_URL || ""));

// ── Lane 1 anonymous telemetry (optional, fire-and-forget) ───────────────────
// Loaded defensively so a missing/broken telemetry module can never break the
// interceptor or the agent it is supervising.
let sendTelemetry = () => {};
let telemetryDisabled = () => false;
try {
  ({ sendTelemetry, telemetryDisabled } = require("./telemetry.cjs"));
} catch {
  // Telemetry module unavailable — observability/enforcement continue unaffected.
}

let CLI_VERSION = "unknown";
try {
  CLI_VERSION = require("../package.json").version || "unknown";
} catch {
  // package.json not resolvable — report an unknown version rather than crash.
}

const LLM_HOSTS = new Set(BASE_LLM_HOSTS);
// Local / extra LLM hosts via env only — never hardcode 127.0.0.1 as a
// blanket catalog entry (would make every localhost call look like LLM traffic).
// Ollama on localhost:11434 is matched by catalogInScope, not this set.
for (const h of String(process.env.VANTIO_EXTRA_LLM_HOSTS || "").split(",")) {
  const t = h.trim();
  if (t) LLM_HOSTS.add(t);
}

/** Safe URL metadata — path only, never query string (may contain keys). */
function extractRequestMeta(input, init) {
  let href = "";
  let method = (init && init.method) || "GET";
  try {
    if (typeof input === "string") href = input;
    else if (input instanceof URL) href = input.href;
    else if (typeof Request !== "undefined" && input instanceof Request) {
      href = input.url;
      method = init?.method || input.method || method;
    } else if (input && input.url) href = input.url;
  } catch {
    href = "";
  }
  let path = "/";
  let scheme = "https";
  try {
    const u = new URL(href);
    path = u.pathname || "/";
    scheme = u.protocol.replace(":", "") || "https";
  } catch {
    /* keep defaults */
  }
  let request_bytes = null;
  try {
    const body = init && init.body;
    if (typeof body === "string") request_bytes = Buffer.byteLength(body);
    else if (Buffer.isBuffer(body)) request_bytes = body.length;
    else if (body instanceof Uint8Array) request_bytes = body.byteLength;
  } catch {
    request_bytes = null;
  }
  return {
    method: String(method || "GET").toUpperCase(),
    path,
    scheme,
    request_bytes,
  };
}

function responseMeta(response) {
  if (!response) {
    return { status: null, ok: null, content_type: null, bytes: null };
  }
  const cl = response.headers?.get?.("content-length");
  const bytes = cl != null && cl !== "" ? parseInt(cl, 10) || 0 : null;
  const ctRaw = response.headers?.get?.("content-type") || "";
  const content_type = ctRaw.split(";")[0].trim() || null;
  return {
    status: typeof response.status === "number" ? response.status : null,
    ok: typeof response.ok === "boolean" ? response.ok : null,
    content_type,
    bytes,
  };
}

// Host lists stay empty. Optics does not load a cloud policy.
const DEFAULT_POLICY = {
  allowed_hosts: [],
  blocked_hosts: [],
};

let policy = { ...DEFAULT_POLICY };

// Rough cost estimate: ~4 bytes/token (≈1 byte/char for ASCII), blended
// $5 / 1M tokens. Applied per byte of request + response throughout, so the
// constant is treated consistently as USD-per-byte.
const USD_PER_BYTE = (5 / 1_000_000) / 4;

let spentUsd = 0;
const _calls = [];
const _pushCall = _calls.push.bind(_calls);
_calls.push = function vantioRecordCall(...items) {
  const result = _pushCall(...items);
  try {
    const last = items.length ? items[items.length - 1] : null;
    const host = last && typeof last === "object" ? last.hostname : undefined;
    sendRunTelemetryOnce(host);
  } catch {
    // Telemetry must never affect the agent.
  }
  return result;
};
const _startMs = Date.now();

if (typeof globalThis.fetch !== "function") {
  return; // Node < 18 — nothing to patch
}

const _originalFetch = globalThis.fetch;

// Fetch and undici.request wrap above dispatcher.dispatch. Increment while those
// wrappers run so the dispatch wrap does not Gate the same call twice.
let undiciWrapDepth = 0;
// HTTP/undici/http2 orig calls mark this store so Socket.connect does not
// ingest a second Gate event for the same request.
const vantioHttpAls = new AsyncLocalStorage();
function launchHttpHandled(fn) {
  return vantioHttpAls.run(true, fn);
}
function httpWrapOwnsConnect() {
  return vantioHttpAls.getStore() === true;
}
function launchUndiciBackend(fn) {
  return launchHttpHandled(() => {
    undiciWrapDepth++;
    let result;
    try {
      result = fn();
    } catch (err) {
      undiciWrapDepth--;
      throw err;
    }
    if (result && typeof result.then === "function") {
      return Promise.resolve(result).finally(() => {
        undiciWrapDepth--;
      });
    }
    undiciWrapDepth--;
    return result;
  });
}

function log(line) {
  process.stderr.write(line + "\n");
}

// Free Optics only. Paid control-plane lines stay on their own path.
function logFreeObservation(info) {
  const httpStatus = info.httpStatus == null ? null : info.httpStatus;
  const applicationStatus = applicationStatusFromHttp(httpStatus);
  const opticsStatus = "SUCCESS";
  if (process.env.VANTIO_JSON === "1") {
    log(JSON.stringify({
      schema_status: SCHEMA_STATUS,
      event: "observation",
      opticsStatus,
      applicationStatus,
      httpStatus,
      host: info.host || null,
      provider: info.provider || null,
      method: info.method || null,
      path: info.path || null,
      detail: info.detail || null,
      duration_ms: info.duration_ms ?? null,
      bytes: info.bytes ?? null,
    }));
    return;
  }
  const lines = [
    "",
    `${c.dim}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus(opticsStatus)}`,
    `  Application outcome: ${humanStatus(applicationStatus)}`,
    `  http_status: ${httpStatus == null ? "none" : httpStatus}`,
  ];
  if (info.host) lines.push(`  host:     ${c.cyan}${info.host}${c.reset}`);
  if (info.provider) lines.push(`  provider: ${info.provider}`);
  if (info.method) lines.push(`  method:   ${info.method}${info.path ? " " + info.path : ""}`);
  if (info.detail) lines.push(`  detail:   ${info.detail}`);
  if (info.duration_ms != null) lines.push(`  duration: ${info.duration_ms}ms`);
  if (info.bytes != null) lines.push(`  bytes:    ${typeof info.bytes === "number" ? info.bytes.toLocaleString() : info.bytes}`);
  lines.push(`  pid:      ${process.pid}`);
  lines.push(`  ${c.dim}Observed locally. Prompts and completions are never stored.${c.reset}`);
  lines.push(`  ${c.dim}Next: vantio tail${c.reset}`);
  log(lines.join("\n"));
}

function report() {
  // Optics records locally. It does not post enforcement events.
}

// A host is in scope when it is a known LLM host. Hosts outside this set pass
// through untouched. Optics does not block, redact, or meter unrelated traffic.
function inScope(hostname, port) {
  return (
    catalogInScope(hostname, port, LLM_HOSTS) ||
    hostListed(hostname, policy.blocked_hosts) ||
    hostListed(hostname, policy.allowed_hosts)
  );
}

// Anonymous opt-in telemetry, once per process, after the first recorded call.
// Disabled unless VANTIO_TELEMETRY=1. VANTIO_TELEMETRY_DISABLED=1 and
// DO_NOT_TRACK=1 override that opt-in.
let _runTelemetrySent = false;
function sendRunTelemetryOnce(hostname) {
  if (_runTelemetrySent) return;
  _runTelemetrySent = true;
  try {
    sendTelemetry({
      event: "run",
      hosts: hostname ? [hostname] : [],
      callCount: _calls.length,
      cliVersion: CLI_VERSION,
    });
  } catch {
    // Telemetry must never affect the agent.
  }
}

function destFromHref(href) {
  const u = new URL(href);
  const port = u.port || (u.protocol === "https:" ? "443" : "80");
  return { hostname: u.hostname, port };
}

async function wrapFetch(backend, input, init) {
  let hostname;
  let port;
  try {
    const url = typeof input === "string" ? input
      : input instanceof URL ? input.href
      : (typeof Request !== "undefined" && input instanceof Request) ? input.url
      : input.url;
    const dest = destFromHref(url);
    hostname = dest.hostname;
    port = dest.port;
  } catch {
    return launchUndiciBackend(() => backend.call(globalThis, input, init));
  }

  // Out of scope (not a known LLM host and not named in policy) — pass straight
  // through, untouched. Optics does not block, redact, or meter unrelated traffic.
  if (!inScope(hostname, port)) {
    return launchUndiciBackend(() => backend.call(globalThis, input, init));
  }

  const reqMeta = extractRequestMeta(input, init);
  const provider = guessProvider(hostname, port);
  const t0 = Date.now();
  let response;
  try {
    response = await launchUndiciBackend(() => backend.call(globalThis, input, init));
  } catch (err) {
    const ts = new Date().toISOString();
    const duration_ms = Date.now() - t0;
    _calls.push({
      hostname,
      provider,
      method: reqMeta.method,
      path: reqMeta.path,
      scheme: reqMeta.scheme,
      request_bytes: reqMeta.request_bytes,
      bytes: null,
      status: null,
      ok: false,
      content_type: null,
      duration_ms,
      ts,
      action: "OBSERVED",
      error_class: err && err.name ? String(err.name) : "Error",
      error: "network_error",
    });
    logFreeObservation({
      httpStatus: null,
      host: hostname,
      provider,
      method: reqMeta.method,
      path: reqMeta.path,
      detail: err && err.name ? err.name : "Error",
      duration_ms,
      bytes: null,
    });
    throw err;
  }
  const resp = responseMeta(response);
  const duration_ms = Date.now() - t0;
  const ts = new Date().toISOString();
  _calls.push({
    hostname,
    provider,
    method: reqMeta.method,
    path: reqMeta.path,
    scheme: reqMeta.scheme,
    request_bytes: reqMeta.request_bytes,
    bytes: resp.bytes,
    status: resp.status,
    ok: resp.ok,
    content_type: resp.content_type,
    duration_ms,
    ts,
    action: "OBSERVED",
  });
  logFreeObservation({
    httpStatus: resp.status,
    host: hostname,
    provider,
    method: reqMeta.method,
    path: reqMeta.path,
    duration_ms,
    bytes: resp.bytes != null ? resp.bytes : null,
  });
  return response;
}

globalThis.fetch = function vantioFetch(input, init) {
  return wrapFetch(_originalFetch, input, init);
};

// undici.fetch, undici.request, Dispatcher.prototype.request, and
// DispatcherBase.dispatch (covers stream / pipeline / connect / upgrade / raw Client.dispatch).
// Fetch and .request wrap above dispatch; undiciWrapDepth skips a second Gate.
(function patchUndici() {
  function headerGet(headers, name) {
    if (!headers) return null;
    const want = String(name).toLowerCase();
    try {
      if (typeof headers.get === "function") {
        return headers.get(name) || headers.get(want) || null;
      }
      if (Array.isArray(headers)) {
        for (let i = 0; i < headers.length - 1; i += 2) {
          if (String(headers[i]).toLowerCase() === want) return headers[i + 1];
        }
        return null;
      }
      for (const k of Object.keys(headers)) {
        if (k.toLowerCase() === want) {
          const v = headers[k];
          return Array.isArray(v) ? v[0] : v;
        }
      }
    } catch {
      return null;
    }
    return null;
  }

  function isControlPlaneHref(href) {
    try {
      const ingest = new URL(INGEST_URL);
      const u = new URL(href);
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      const reqPort = u.port || (u.protocol === "https:" ? "443" : "80");
      return u.hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && reqPort === ingestPort
        && u.pathname.startsWith("/api/v1/");
    } catch {
      return false;
    }
  }

  function hrefFromDispatcher(dispatcher, opts) {
    opts = opts || {};
    try {
      if (opts.origin) {
        const path = opts.path || "/";
        return new URL(String(path).startsWith("http") ? path : path, String(opts.origin)).href;
      }
    } catch { /* fall through */ }
    try {
      for (const sym of Object.getOwnPropertySymbols(dispatcher || {})) {
        const v = dispatcher[sym];
        if (v && typeof v === "object" && typeof v.hostname === "string" && (v.origin || v.href)) {
          const origin = v.origin || new URL(v.href).origin;
          return new URL(opts.path || "/", origin).href;
        }
      }
    } catch { /* ignore */ }
    return null;
  }

  function hrefFromTopLevel(url, opts) {
    try {
      if (typeof url === "string") return url;
      if (typeof URL !== "undefined" && url instanceof URL) return url.href;
      if (url && typeof url === "object" && url.href) return String(url.href);
      if (url && typeof url === "object" && url.origin) {
        return new URL((opts && opts.path) || "/", String(url.origin)).href;
      }
    } catch { /* ignore */ }
    return null;
  }

  async function wrapUndiciHttp(href, opts, launch) {
    let hostname;
    let port;
    try {
      const dest = destFromHref(href);
      hostname = dest.hostname;
      port = dest.port;
    } catch {
      return launchUndiciBackend(() => launch(opts));
    }

    if (isControlPlaneHref(href) || !inScope(hostname, port)) {
      return launchUndiciBackend(() => launch(opts));
    }

    const method = (opts && opts.method) || (opts && opts.body ? "PUT" : "GET");
    const init = { method, headers: opts && opts.headers, body: opts && opts.body };

    const reqMeta = extractRequestMeta(href, init);
    const provider = guessProvider(hostname, port);
    const t0 = Date.now();
    let result;
    try {
      result = await launchUndiciBackend(() => launch(opts));
    } catch (err) {
      const duration_ms = Date.now() - t0;
      _calls.push({
        hostname, provider, method: reqMeta.method, path: reqMeta.path, scheme: reqMeta.scheme,
        request_bytes: reqMeta.request_bytes, bytes: null, status: null, ok: false,
        content_type: null, duration_ms, ts: new Date().toISOString(), action: "OBSERVED",
        error_class: err && err.name ? String(err.name) : "Error", error: "network_error",
        mediation: "undici_request",
      });
      throw err;
    }
    const duration_ms = Date.now() - t0;
    const cl = headerGet(result && result.headers, "content-length");
    _calls.push({
      hostname, provider, method: reqMeta.method, path: reqMeta.path, scheme: reqMeta.scheme,
      request_bytes: reqMeta.request_bytes,
      bytes: cl != null && cl !== "" ? (parseInt(cl, 10) || 0) : 0,
      status: result && result.statusCode,
      ok: result && result.statusCode >= 200 && result.statusCode < 400,
      content_type: headerGet(result && result.headers, "content-type"),
      duration_ms, ts: new Date().toISOString(), action: "OBSERVED",
      mediation: "undici_request",
    });
    return result;
  }

  function isUpgradeOrConnect(opts) {
    if (!opts) return false;
    const method = String(opts.method || "").toUpperCase();
    return method === "CONNECT" || Boolean(opts.upgrade);
  }

  function chunkByteLength(chunk, encoding) {
    if (chunk == null) return 0;
    if (Buffer.isBuffer(chunk)) return chunk.length;
    if (typeof Uint8Array !== "undefined" && chunk instanceof Uint8Array) return chunk.byteLength;
    if (typeof chunk === "string") {
      return Buffer.byteLength(chunk, typeof encoding === "string" ? encoding : "utf8");
    }
    try {
      return Buffer.byteLength(String(chunk));
    } catch {
      return 0;
    }
  }

  function parseSocketWriteArgs(chunk, encoding, cb) {
    if (typeof chunk === "function") return { chunk: undefined, encoding: undefined, cb: chunk };
    if (typeof encoding === "function") return { chunk, encoding: undefined, cb: encoding };
    return { chunk, encoding, cb };
  }

  // After undici.upgrade / CONNECT, Gate already decided the host. Frame
  // payloads are not parsed (Optics never reads the conversation). Outbound
  // bytes are observed. Optics does not stop the write.
  function wrapTunnelSocket(socket, hostname) {
    if (!socket || typeof socket.write !== "function" || socket.__vantioWsPatched) return;
    socket.__vantioWsPatched = true;
    const origWrite = socket.write.bind(socket);
    const origEnd = typeof socket.end === "function" ? socket.end.bind(socket) : null;
    let written = 0;
    let frameReported = false;
    const provider = guessProvider(hostname, null);

    function gateBytes(n) {
      if (n <= 0) return;
      written += n;
      spentUsd += n * USD_PER_BYTE;
      if (!frameReported) {
        frameReported = true;
        _calls.push({
          hostname, provider, method: "UPGRADE", path: null, scheme: "ws",
          request_bytes: n, bytes: n, status: null, ok: true,
          content_type: null, duration_ms: 0, ts: new Date().toISOString(),
          action: "OBSERVED", mediation: "undici_ws",
        });
        report({
          target_host: hostname, pid: process.pid, action_taken: "OBSERVED",
          timestamp_ns: Date.now() * 1e6, bytes_severed: 0, bytes_observed: n,
          request_bytes: n, mediation: "undici_ws", plane: "optics_gate",
        });
        log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — tunnel frames`);
      }
    }

    socket.write = function vantioTunnelWrite(chunk, encoding, cb) {
      const args = parseSocketWriteArgs(chunk, encoding, cb);
      try {
        gateBytes(chunkByteLength(args.chunk, args.encoding));
      } catch {
        /* fail open */
      }
      return origWrite(chunk, encoding, cb);
    };
    if (origEnd) {
      socket.end = function vantioTunnelEnd(chunk, encoding, cb) {
        const args = parseSocketWriteArgs(chunk, encoding, cb);
        try {
          if (args.chunk != null) gateBytes(chunkByteLength(args.chunk, args.encoding));
        } catch {
          /* fail open */
        }
        return origEnd(chunk, encoding, cb);
      };
    }
  }

  function attachTunnelHandler(handler, hostname) {
    if (!handler || handler.__vantioTunnelWrapped) return handler;
    handler.__vantioTunnelWrapped = true;
    if (typeof handler.onUpgrade === "function") {
      const orig = handler.onUpgrade.bind(handler);
      handler.onUpgrade = function vantioOnUpgrade(statusCode, headers, socket) {
        try { wrapTunnelSocket(socket, hostname); } catch { /* fail open */ }
        return orig(statusCode, headers, socket);
      };
    }
    return handler;
  }

  function launchDispatch(dispatcher, orig, opts, handler, hostname) {
    if (isUpgradeOrConnect(opts)) {
      handler = attachTunnelHandler(handler, hostname);
    }
    return launchUndiciBackend(() => orig.call(dispatcher, opts, handler));
  }

  function applyDispatchGate(dispatcher, orig, opts, handler) {
    const href = hrefFromDispatcher(dispatcher, opts);
    if (!href) return orig.call(dispatcher, opts, handler);
    let hostname;
    let port;
    try {
      const dest = destFromHref(href);
      hostname = dest.hostname;
      port = dest.port;
    } catch {
      return orig.call(dispatcher, opts, handler);
    }
    if (isControlPlaneHref(href) || !inScope(hostname, port)) {
      return launchUndiciBackend(() => orig.call(dispatcher, opts, handler));
    }

    const method = (opts && opts.method) || (opts && opts.body ? "PUT" : "GET");
    const init = { method, headers: opts && opts.headers, body: opts && opts.body };
    const reqMeta = extractRequestMeta(href, init);
    const provider = guessProvider(hostname, port);
    const baseCall = {
      hostname, provider, method: reqMeta.method, path: reqMeta.path, scheme: reqMeta.scheme,
      request_bytes: reqMeta.request_bytes, bytes: 0, status: null, ok: true,
      content_type: null, duration_ms: 0, ts: new Date().toISOString(),
      mediation: "undici_dispatch",
    };

    _calls.push(Object.assign({}, baseCall, { action: "OBSERVED" }));
    report({
      target_host: hostname, pid: process.pid, action_taken: "OBSERVED",
      timestamp_ns: Date.now() * 1e6, bytes_severed: 0, mediation: "undici_dispatch",
    });
    return launchDispatch(dispatcher, orig, opts, handler, hostname);
  }

  function wrapDispatchCall(dispatcher, orig, opts, handler) {
    if (undiciWrapDepth > 0) return orig.call(dispatcher, opts, handler);
    try {
      return applyDispatchGate(dispatcher, orig, opts, handler);
    } catch {
      return orig.call(dispatcher, opts, handler);
    }
  }

  function patchDispatch(mod) {
    if (!mod) return;
    let base = null;
    try {
      if (mod.Client && mod.Client.prototype) {
        const proto = Object.getPrototypeOf(mod.Client.prototype);
        if (proto && typeof proto.dispatch === "function") base = proto;
      }
    } catch { /* fall through */ }
    if (!base && mod.Dispatcher && mod.Dispatcher.prototype && typeof mod.Dispatcher.prototype.dispatch === "function") {
      base = mod.Dispatcher.prototype;
    }
    if (!base || typeof base.dispatch !== "function" || base.dispatch.__vantioDispatchPatched) return;
    const orig = base.dispatch;
    base.dispatch = function vantioDispatcherDispatch(opts, handler) {
      return wrapDispatchCall(this, orig, opts, handler);
    };
    base.dispatch.__vantioDispatchPatched = true;
  }

  function patchDispatcherInstance(dispatcher) {
    if (!dispatcher || typeof dispatcher.dispatch !== "function") return;
    if (dispatcher.dispatch.__vantioDispatchPatched) return;
    const orig = dispatcher.dispatch;
    dispatcher.dispatch = function vantioInstanceDispatch(opts, handler) {
      return wrapDispatchCall(this, orig, opts, handler);
    };
    dispatcher.dispatch.__vantioDispatchPatched = true;
  }

  function patchGlobalDispatcher(mod) {
    try {
      if (mod && typeof mod.getGlobalDispatcher === "function") {
        patchDispatcherInstance(mod.getGlobalDispatcher());
      }
    } catch { /* fail open */ }
    try {
      patchDispatcherInstance(globalThis[Symbol.for("undici.globalDispatcher.1")]);
    } catch { /* fail open */ }
    if (mod && typeof mod.setGlobalDispatcher === "function" && !mod.__vantioSetGlobalPatched) {
      const origSet = mod.setGlobalDispatcher;
      mod.setGlobalDispatcher = function vantioSetGlobalDispatcher(agent) {
        const ret = origSet.apply(this, arguments);
        try { patchDispatcherInstance(agent); } catch { /* fail open */ }
        return ret;
      };
      mod.__vantioSetGlobalPatched = true;
    }
  }

  function patchFetch(mod) {
    if (!mod || typeof mod.fetch !== "function") return;
    if (mod.__vantioFetchPatched) return;
    const orig = mod.fetch;
    if (orig === globalThis.fetch) {
      mod.__vantioFetchPatched = true;
      return;
    }
    const backend = typeof orig.bind === "function" ? orig.bind(mod) : orig;
    mod.fetch = function vantioUndiciFetch(input, init) {
      return wrapFetch(backend, input, init);
    };
    mod.__vantioFetchPatched = true;
  }

  function patchRequest(mod) {
    if (!mod || mod.__vantioRequestPatched) return;

    if (typeof mod.request === "function") {
      const origRequest = mod.request;
      mod.request = function vantioUndiciRequest(url, opts, handler) {
        if (typeof opts === "function") {
          handler = opts;
          opts = null;
        }
        if (handler) return origRequest.call(this, url, opts, handler);
        const href = hrefFromTopLevel(url, opts);
        if (!href) return origRequest.call(this, url, opts);
        return wrapUndiciHttp(href, opts || {}, (o) => origRequest.call(this, url, o));
      };
    }

    const proto = mod.Dispatcher && mod.Dispatcher.prototype;
    if (proto && typeof proto.request === "function" && !proto.__vantioRequestPatched) {
      const origProto = proto.request;
      proto.request = function vantioDispatcherRequest(opts, callback) {
        const href = hrefFromDispatcher(this, opts);
        if (!href) return origProto.call(this, opts, callback);
        if (typeof callback === "function") {
          wrapUndiciHttp(href, opts || {}, (o) => new Promise((resolve, reject) => {
            origProto.call(this, o, (err, data) => (err ? reject(err) : resolve(data)));
          })).then((data) => callback(null, data), (err) => callback(err));
          return;
        }
        return wrapUndiciHttp(href, opts || {}, (o) => origProto.call(this, o));
      };
      proto.__vantioRequestPatched = true;
    }

    mod.__vantioRequestPatched = true;
  }

  function patchMod(mod) {
    if (!mod) return;
    try { patchFetch(mod); } catch { /* fail open */ }
    try { patchRequest(mod); } catch { /* fail open */ }
    try { patchDispatch(mod); } catch { /* fail open */ }
    try { patchGlobalDispatcher(mod); } catch { /* fail open */ }
  }

  try {
    const Module = require("module");
    const origLoad = Module._load;
    Module._load = function vantioLoad(request, parent, isMain) {
      const exported = origLoad.apply(this, arguments);
      if (request === "undici" || request === "node:undici") {
        try {
          patchMod(exported);
        } catch {
          /* fail open */
        }
      }
      return exported;
    };
  } catch {
    /* Module._load unavailable — still try an immediate require below */
  }

  for (const spec of ["node:undici", "undici"]) {
    try {
      patchMod(require(spec));
    } catch {
      /* optional — not installed until the agent requires it */
    }
  }
})();

// ── Run summary ─────────────────────────────────────────────────────────────


// Node http/https — same Optics wrap rules as fetch, last-known policy
// (request() is sync; fail-open until policy loads). Out-of-scope hosts and
// the ingest control plane pass through untouched. Node-spawned curl is
// wrapped separately. Browsers stay residual.
(function patchNodeHttpHttps() {

  function isControlPlaneRequest(args) {
    try {
      const ingest = new URL(INGEST_URL);
      const a0 = args && args[0];
      let u = null;
      if (typeof a0 === "string" || (typeof URL !== "undefined" && a0 instanceof URL)) {
        u = new URL(String(a0));
      } else if (a0 && typeof a0 === "object") {
        const host = a0.hostname || (a0.host ? String(a0.host).split(":")[0] : "");
        if (!host) return false;
        const port = String(a0.port || (a0.protocol === "https:" ? 443 : 80));
        const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
        const path = String(a0.path || a0.pathname || "");
        return host.toLowerCase() === ingest.hostname.toLowerCase()
          && port === String(ingestPort)
          && path.startsWith("/api/v1/");
      }
      if (!u) return false;
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      const reqPort = u.port || (u.protocol === "https:" ? "443" : "80");
      return u.hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && reqPort === ingestPort
        && u.pathname.startsWith("/api/v1/");
    } catch {
      return false;
    }
  }

  function destFromArgs(args) {
    try {
      if (!args || !args.length) return { hostname: null, port: null };
      const a0 = args[0];
      if (typeof a0 === "string" || (typeof URL !== "undefined" && a0 instanceof URL)) {
        try {
          return destFromHref(String(a0));
        } catch { return { hostname: null, port: null }; }
      }
      if (a0 && typeof a0 === "object") {
        let hostname = null;
        if (typeof a0.hostname === "string") hostname = a0.hostname;
        else if (typeof a0.host === "string") hostname = a0.host.split(":")[0];
        else if (typeof a0.href === "string") {
          try { hostname = new URL(a0.href).hostname; } catch { hostname = null; }
        }
        let port = a0.port;
        if ((port == null || port === "") && a0.host && String(a0.host).includes(":")) {
          port = String(a0.host).split(":").pop();
        }
        if (port == null || port === "") {
          port = a0.protocol === "https:" ? 443 : 80;
        }
        return { hostname, port: String(port) };
      }
    } catch { /* ignore */ }
    return { hostname: null, port: null };
  }

  function decideHttp(hostname, port, args) {
    if (!hostname || isControlPlaneRequest(args)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    return "observe";
  }

  function wrapModule(mod, scheme) {
    if (!mod || typeof mod.request !== "function") return;
    if (mod.__vantioPatched) return;
    const origRequest = mod.request.bind(mod);
    const origGet = typeof mod.get === "function" ? mod.get.bind(mod) : null;

    function wrapLaunch(args, launch) {
      const dest = destFromArgs(args);
      const hostname = dest.hostname;
      const port = dest.port;
      const decision = decideHttp(hostname, port, args);
      if (decision === "pass") return launchHttpHandled(launch);

      const provider = guessProvider(hostname, port);
      const ts = new Date().toISOString();
      const baseCall = {
        hostname, provider, method: "REQUEST", path: null, scheme,
        request_bytes: null, bytes: 0, status: null, ok: true,
        content_type: null, duration_ms: 0, ts, optics_plane: "app_http",
      };

      _calls.push({ ...baseCall, action: "OBSERVED" });
      report({
        target_host: hostname, pid: process.pid,
        action_taken: "OBSERVED",
        timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
        mediation: "node_http", plane: "optics_gate",
      });
      log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — Node ${scheme}.request`);

      const req = launchHttpHandled(launch);
      if (req && typeof req.on === "function") {
        req.on("response", (res) => {
          try {
            const cl = parseInt(res && res.headers && res.headers["content-length"], 10);
            if (Number.isFinite(cl) && cl > 0) spentUsd += cl * USD_PER_BYTE;
          } catch { /* ignore */ }
        });
      }
      return req;
    }

    mod.request = function (...args) {
      try {
        return wrapLaunch(args, () => origRequest(...args));
      } catch {
        return origRequest(...args);
      }
    };
    if (origGet) {
      mod.get = function (...args) {
        try {
          return wrapLaunch(args, () => origGet(...args));
        } catch {
          return origGet(...args);
        }
      };
    }
    const OrigCR = mod.ClientRequest;
    if (typeof OrigCR === "function" && !OrigCR.__vantioPatched) {
      function VantioClientRequest(...args) {
        if (httpWrapOwnsConnect()) {
          return new OrigCR(...args);
        }
        try {
          return wrapLaunch(args, () => new OrigCR(...args));
        } catch {
          return new OrigCR(...args);
        }
      }
      Object.setPrototypeOf(VantioClientRequest, OrigCR);
      VantioClientRequest.prototype = OrigCR.prototype;
      VantioClientRequest.__vantioPatched = true;
      mod.ClientRequest = VantioClientRequest;
    }
    mod.__vantioPatched = true;
  }

  try { wrapModule(require("node:http"), "http"); } catch { try { wrapModule(require("http"), "http"); } catch { /* ignore */ } }
  try { wrapModule(require("node:https"), "https"); } catch { try { wrapModule(require("https"), "https"); } catch { /* ignore */ } }
})();

// globalThis.WebSocket / undici.WebSocket — observe the handshake.
// Outbound frame size only; conversation bytes are not parsed or rewritten.
// HTTP/undici already marked via AsyncLocalStorage so those sockets are not
// ingested twice. Residual: browsers / Chromium / CDP.
(function patchWebSocket() {
  function destFromWsUrl(url) {
    try {
      const u = new URL(String(url));
      const port = u.port || (u.protocol === "wss:" || u.protocol === "https:" ? "443" : "80");
      return { hostname: u.hostname, port: String(port), href: u.href };
    } catch {
      return { hostname: null, port: null, href: null };
    }
  }

  function isControlPlaneWs(url) {
    try {
      const ingest = new URL(INGEST_URL);
      const u = new URL(String(url));
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      const reqPort = u.port || (u.protocol === "wss:" || u.protocol === "https:" ? "443" : "80");
      return u.hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && reqPort === ingestPort
        && u.pathname.startsWith("/api/v1/");
    } catch {
      return false;
    }
  }

  function sendByteLength(data) {
    try {
      if (data == null) return 0;
      if (typeof data === "string") return Buffer.byteLength(data);
      if (Buffer.isBuffer(data)) return data.length;
      if (typeof ArrayBuffer !== "undefined" && data instanceof ArrayBuffer) return data.byteLength;
      if (typeof ArrayBuffer !== "undefined" && ArrayBuffer.isView(data)) return data.byteLength;
      if (typeof Blob !== "undefined" && data instanceof Blob) return data.size || 0;
      return Buffer.byteLength(String(data));
    } catch {
      return 0;
    }
  }

  function decideWs(hostname, port, url) {
    if (!hostname || isControlPlaneWs(url)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    return "observe";
  }

  function wrapWsSend(ws, hostname) {
    if (!ws || typeof ws.send !== "function" || ws.__vantioWsSendPatched) return;
    ws.__vantioWsSendPatched = true;
    const origSend = ws.send.bind(ws);
    let written = 0;
    let frameReported = false;
    const provider = guessProvider(hostname, null);

    ws.send = function vantioWsSend(data) {
      const n = sendByteLength(data);
      written += n;
      if (n > 0) spentUsd += n * USD_PER_BYTE;
      if (!frameReported && n > 0) {
        frameReported = true;
        _calls.push({
          hostname, provider, method: "WS", path: null, scheme: "ws",
          request_bytes: n, bytes: 0, status: null, ok: true,
          content_type: null, duration_ms: 0, ts: new Date().toISOString(),
          action: "OBSERVED", mediation: "node_ws",
        });
        report({
          target_host: hostname, pid: process.pid, action_taken: "OBSERVED",
          timestamp_ns: Date.now() * 1e6, bytes_severed: 0, bytes_observed: n,
          request_bytes: n, mediation: "node_ws", plane: "optics_gate",
        });
      }
      return origSend.apply(this, arguments);
    };
  }

  function wrapWsCtor(Orig) {
    if (typeof Orig !== "function" || Orig.__vantioPatched) return Orig;
    function VantioWebSocket(url, protocols) {
      if (httpWrapOwnsConnect()) {
        return protocols !== undefined ? new Orig(url, protocols) : new Orig(url);
      }
      const dest = destFromWsUrl(url);
      const hostname = dest.hostname;
      const port = dest.port;
      const decision = decideWs(hostname, port, url);
      if (decision === "pass") {
        return launchHttpHandled(() => (protocols !== undefined ? new Orig(url, protocols) : new Orig(url)));
      }

      const provider = guessProvider(hostname, port);
      const ts = new Date().toISOString();
      const baseCall = {
        hostname, provider, method: "WS", path: null, scheme: "ws",
        request_bytes: null, bytes: 0, status: null, ok: true,
        content_type: null, duration_ms: 0, ts, optics_plane: "app_ws",
      };

      _calls.push({ ...baseCall, action: "OBSERVED" });
      report({
        target_host: hostname, pid: process.pid,
        action_taken: "OBSERVED",
        timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
        mediation: "node_ws", plane: "optics_gate",
      });
      log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — WebSocket`);

      const ws = launchHttpHandled(() => (protocols !== undefined ? new Orig(url, protocols) : new Orig(url)));
      try { wrapWsSend(ws, hostname); } catch { /* fail open */ }
      return ws;
    }
    Object.setPrototypeOf(VantioWebSocket, Orig);
    VantioWebSocket.prototype = Orig.prototype;
    VantioWebSocket.__vantioPatched = true;
    return VantioWebSocket;
  }

  try {
    const origGlobal = typeof globalThis.WebSocket === "function" ? globalThis.WebSocket : null;
    if (origGlobal) globalThis.WebSocket = wrapWsCtor(origGlobal);
    try {
      const undici = require("undici");
      if (undici && typeof undici.WebSocket === "function") {
        if (origGlobal && (undici.WebSocket === origGlobal || undici.WebSocket === globalThis.WebSocket)) {
          undici.WebSocket = globalThis.WebSocket;
        } else {
          undici.WebSocket = wrapWsCtor(undici.WebSocket);
        }
      }
    } catch { /* ignore */ }
  } catch { /* fail open — native WebSocket stays unwrapped */ }
})();

// Node http2.connect / session.request — same Optics wrap rules as
// Node http. In-scope sessions are observed. Residual: browsers.
(function patchNodeHttp2() {
  let http2;
  try { http2 = require("node:http2"); } catch { try { http2 = require("http2"); } catch { return; } }
  if (!http2 || typeof http2.connect !== "function" || http2.__vantioPatched) return;

  const origConnect = http2.connect.bind(http2);

  function destFromAuthority(authority, options) {
    try {
      if (authority && typeof authority === "object") {
        if (typeof authority.href === "string") return destFromHref(authority.href);
        if (typeof authority.hostname === "string") {
          const proto = authority.protocol || (options && options.protocol) || "https:";
          const port = authority.port || (options && options.port)
            || (String(proto).includes("https") ? 443 : 80);
          return { hostname: authority.hostname, port: String(port) };
        }
      }
      const s = String(authority || "");
      if (s.includes("://")) return destFromHref(s);
      const proto = (options && options.protocol) || "http:";
      return destFromHref(`${proto}//${s}`);
    } catch {
      const hostname = options && (options.hostname || options.host);
      const port = options && options.port;
      return { hostname: hostname || null, port: port != null ? String(port) : "443" };
    }
  }

  function isControlPlaneHost(hostname, port) {
    try {
      const ingest = new URL(INGEST_URL);
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      return hostname
        && hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && String(port) === String(ingestPort);
    } catch {
      return false;
    }
  }

  function decideHttp2(hostname, port) {
    if (!hostname || isControlPlaneHost(hostname, port)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    return "observe";
  }

  function reportH2(hostname, action, extra) {
    report({
      target_host: hostname,
      pid: process.pid,
      action_taken: action,
      timestamp_ns: Date.now() * 1e6,
      bytes_severed: (extra && extra.bytes) || 0,
      mediation: "node_http2",
      plane: "optics_gate",
      ...(extra || {}),
    });
  }

  function wrapH2Write(stream) {
    return stream;
  }

  function wrapSession(session, hostname, port) {
    if (!session || typeof session.request !== "function" || session.__vantioPatched) return session;
    const origRequest = session.request.bind(session);
    session.request = function vantioH2Request(headers, options) {
      const ts = new Date().toISOString();
      const provider = guessProvider(hostname, port);
      const baseCall = {
        hostname, provider, method: "REQUEST", path: null, scheme: "http2",
        request_bytes: null, bytes: 0, status: null, ok: true,
        content_type: null, duration_ms: 0, ts, optics_plane: "app_http2",
      };

      _calls.push({ ...baseCall, action: "OBSERVED" });
      reportH2(hostname, "OBSERVED");
      log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — Node http2.request`);

      const stream = origRequest(headers, options);
      if (stream && typeof stream.on === "function") {
        stream.on("response", (hdrs) => {
          try {
            const cl = parseInt(hdrs && (hdrs["content-length"] || hdrs["Content-Length"]), 10);
            if (Number.isFinite(cl) && cl > 0) spentUsd += cl * USD_PER_BYTE;
          } catch { /* ignore */ }
        });
      }
      return wrapH2Write(stream, hostname);
    };
    session.__vantioPatched = true;
    return session;
  }

  function launchConnect(authority, options, listener, hostname, port) {
    const session = launchHttpHandled(() => origConnect(authority, options, listener));
    return wrapSession(session, hostname, port);
  }

  http2.connect = function vantioH2Connect(authority, options, listener) {
    try {
      if (typeof options === "function") {
        listener = options;
        options = undefined;
      }
      const dest = destFromAuthority(authority, options);
      const hostname = dest.hostname;
      const port = dest.port;
      const decision = decideHttp2(hostname, port);
      if (decision === "pass") return launchHttpHandled(() => origConnect(authority, options, listener));
      return launchConnect(authority, options, listener, hostname, port);
    } catch {
      return launchHttpHandled(() => origConnect(authority, options, listener));
    }
  };
  http2.__vantioPatched = true;
})();

// Node net.Socket.connect / tls.connect — observe raw TCP
// to in-scope hosts. HTTP/undici/http2 already marked via AsyncLocalStorage
// so those sockets are not ingested twice. No TLS payload redaction.
(function patchNodeNetTls() {
  let net;
  try { net = require("node:net"); } catch { try { net = require("net"); } catch { return; } }
  if (!net || !net.Socket || !net.Socket.prototype) return;

  function destFromNetArgs(args) {
    let list = args;
    // net.Socket.connect sometimes receives Node's normalized tuple as a
    // single array argument: [options, cb] or [port, host, cb].
    if (list && list.length === 1 && Array.isArray(list[0])) {
      list = list[0];
    }
    const a0 = list && list[0];
    if (typeof a0 === "string" && (a0.includes("/") || a0.startsWith("\0"))) {
      return { ipc: true, hostname: null, port: null };
    }
    if (a0 && typeof a0 === "object" && !Array.isArray(a0)) {
      if (a0.path) return { ipc: true, hostname: null, port: null };
      const hostname = a0.servername || a0.host || a0.hostname || null;
      const port = a0.port;
      return {
        hostname: hostname ? String(hostname).replace(/^\[/, "").replace(/\]$/, "").split("%")[0] : null,
        port: port != null && port !== "" ? String(port) : null,
      };
    }
    if (typeof a0 === "number" || (typeof a0 === "string" && /^\d+$/.test(a0))) {
      const host = typeof list[1] === "string" ? list[1] : "localhost";
      return { hostname: host, port: String(a0) };
    }
    return { hostname: null, port: null };
  }

  function isControlPlaneHost(hostname, port) {
    try {
      const ingest = new URL(INGEST_URL);
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      return hostname
        && hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && String(port || ingestPort) === String(ingestPort);
    } catch {
      return false;
    }
  }

  function decideNet(hostname, port) {
    if (!hostname || isControlPlaneHost(hostname, port)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    return "observe";
  }

  function gateConnect(socket, orig, args) {
    if (httpWrapOwnsConnect()) return orig.apply(socket, args);
    const dest = destFromNetArgs(args);
    if (dest.ipc) return orig.apply(socket, args);
    const hostname = dest.hostname;
    const port = dest.port;
    const decision = decideNet(hostname, port);
    if (decision === "pass") return orig.apply(socket, args);

    const provider = guessProvider(hostname, port);
    const ts = new Date().toISOString();
    const baseCall = {
      hostname, provider, method: "CONNECT", path: null, scheme: "tcp",
      request_bytes: null, bytes: 0, status: null, ok: true,
      content_type: null, duration_ms: 0, ts, optics_plane: "app_net",
    };

    _calls.push({ ...baseCall, action: "OBSERVED" });
    report({
      target_host: hostname, pid: process.pid,
      action_taken: "OBSERVED",
      timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
      mediation: "node_net", plane: "optics_gate",
    });
    log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — Node net.connect`);
    return orig.apply(socket, args);
  }

  function wrapConnectProto(proto) {
    if (!proto || typeof proto.connect !== "function" || proto.__vantioConnectPatched) return;
    const orig = proto.connect;
    proto.connect = function vantioSocketConnect(...args) {
      try {
        return gateConnect(this, orig, args);
      } catch {
        return orig.apply(this, args);
      }
    };
    proto.__vantioConnectPatched = true;
  }

  wrapConnectProto(net.Socket.prototype);
  try {
    const tls = require("node:tls");
    if (tls && tls.TLSSocket) wrapConnectProto(tls.TLSSocket.prototype);
  } catch {
    try {
      const tls = require("tls");
      if (tls && tls.TLSSocket) wrapConnectProto(tls.TLSSocket.prototype);
    } catch { /* optional */ }
  }
})();

// Node child_process spawn/exec of curl, wget, httpie, and aria2c —
// observe before the child starts. File-body and curl -F size come from
// stat; contents and stdin pipes are not read. Argv is not rewritten. Residual: browsers.
(function patchCurlSpawn() {
  let cp;
  try { cp = require("node:child_process"); } catch { try { cp = require("child_process"); } catch { return; } }
  if (!cp || typeof cp.spawn !== "function" || cp.__vantioCurlPatched) return;

  const origSpawn = cp.spawn.bind(cp);
  const origSpawnSync = typeof cp.spawnSync === "function" ? cp.spawnSync.bind(cp) : null;
  const origExecFile = typeof cp.execFile === "function" ? cp.execFile.bind(cp) : null;
  const origExecFileSync = typeof cp.execFileSync === "function" ? cp.execFileSync.bind(cp) : null;
  const origExec = typeof cp.exec === "function" ? cp.exec.bind(cp) : null;
  const origExecSync = typeof cp.execSync === "function" ? cp.execSync.bind(cp) : null;

  function cmdBase(file) {
    try {
      return String(basename(String(file || ""))).toLowerCase().replace(/\.exe$/, "");
    } catch {
      return "";
    }
  }

  function tokenizeShell(s) {
    const out = [];
    let cur = "";
    let quote = "";
    const str = String(s || "");
    for (let i = 0; i < str.length; i++) {
      const ch = str[i];
      if (quote) {
        if (ch === quote) quote = "";
        else cur += ch;
        continue;
      }
      if (ch === "'" || ch === '"') {
        quote = ch;
        continue;
      }
      if (/\s/.test(ch)) {
        if (cur) {
          out.push(cur);
          cur = "";
        }
        continue;
      }
      cur += ch;
    }
    if (cur) out.push(cur);
    return out;
  }

  function splitSpawnArgs(args) {
    const command = args[0];
    let argv = [];
    let options = null;
    if (Array.isArray(args[1])) {
      argv = args[1];
      if (args[2] && typeof args[2] === "object") options = args[2];
    } else if (args[1] && typeof args[1] === "object") {
      options = args[1];
    }
    return { command, argv, options };
  }

  function stripSpawnPrefixes(tokens) {
    const list = Array.isArray(tokens) ? tokens.map((t) => String(t)) : [];
    let i = 0;
    while (i < list.length) {
      const base = cmdBase(list[i]);
      if (base !== "env" && base !== "timeout" && base !== "nice") return list.slice(i);
      i += 1;
      if (base === "env") {
        while (i < list.length) {
          const t = list[i];
          if (t.startsWith("-")) {
            if ((t === "-u" || t === "--unset") && i + 1 < list.length) i += 2;
            else i += 1;
            continue;
          }
          if (t.includes("=")) {
            i += 1;
            continue;
          }
          break;
        }
        continue;
      }
      if (base === "timeout") {
        while (i < list.length && list[i].startsWith("-")) {
          if ((list[i] === "-s" || list[i] === "--signal" || list[i] === "-k" || list[i] === "--kill-after")
              && i + 1 < list.length) i += 2;
          else i += 1;
        }
        if (i < list.length) i += 1;
        continue;
      }
      if (base === "nice") {
        if (i < list.length && (list[i] === "-n" || list[i] === "--adjustment") && i + 1 < list.length) i += 2;
        else if (i < list.length && list[i].startsWith("-") && /^-?\d+$/.test(list[i].replace(/^-/, "") || "x")) i += 1;
      }
    }
    return list.slice(i);
  }

  function canonicalCliTool(base) {
    if (base === "curl") return "curl";
    if (base === "wget") return "wget";
    if (base === "http" || base === "https" || base === "httpie") return "httpie";
    if (base === "aria2c" || base === "aria2") return "aria2c";
    return null;
  }

  function cliFromTokens(tokens) {
    const stripped = stripSpawnPrefixes(tokens);
    if (!stripped.length) return null;
    const direct = canonicalCliTool(cmdBase(stripped[0]));
    if (direct) return { tool: direct, argv: stripped.slice(1) };
    const base = cmdBase(stripped[0]);
    if (base !== "sh" && base !== "bash" && base !== "dash" && base !== "zsh") return null;
    const args = stripped.slice(1);
    const cIdx = args.indexOf("-c");
    if (cIdx < 0 || args[cIdx + 1] == null) return null;
    const inner = stripSpawnPrefixes(tokenizeShell(args[cIdx + 1]));
    if (!inner.length) return null;
    const tool = canonicalCliTool(cmdBase(inner[0]));
    if (!tool) return null;
    return { tool, argv: inner.slice(1) };
  }

  function httpCliFromSpawn(command, argv, options) {
    const args = Array.isArray(argv) ? argv.map((a) => String(a)) : [];
    if (options && options.shell) {
      return httpCliFromExec([String(command || ""), ...args].join(" "));
    }
    return cliFromTokens([String(command || ""), ...args]);
  }

  function httpCliFromExec(command) {
    const tokens = tokenizeShell(command);
    if (!tokens.length) return null;
    return cliFromTokens(tokens);
  }

  function stdinByteLength(options) {
    if (options && options.input != null) {
      try {
        if (Buffer.isBuffer(options.input)) return options.input.length;
        if (typeof options.input === "string") return Buffer.byteLength(options.input);
      } catch { /* ignore */ }
    }
    try {
      let fd = null;
      const stdio = options && options.stdio;
      if (stdio == null) return 0;
      const s0 = Array.isArray(stdio) ? stdio[0] : stdio;
      if (s0 === "pipe" || s0 === "ignore" || s0 === "ipc") return 0;
      if (s0 === "inherit") fd = 0;
      else if (typeof s0 === "number") fd = s0;
      else if (s0 && typeof s0.fd === "number") fd = s0.fd;
      else return 0;
      const st = fstatSync(fd);
      return st.isFile() ? Number(st.size) || 0 : 0;
    } catch {
      return 0;
    }
  }

  function fileByteLength(rel, stdinSize) {
    const p = String(rel || "");
    if (!p) return 0;
    if (p === "-") return Number(stdinSize) || 0;
    try {
      const st = statSync(p);
      return st.isFile() ? Number(st.size) || 0 : 0;
    } catch {
      return 0;
    }
  }

  function bytesFromAtOrLiteral(value, atMeansFile, stdinSize) {
    const v = String(value ?? "");
    if (atMeansFile && v.startsWith("@")) return fileByteLength(v.slice(1), stdinSize);
    return Buffer.byteLength(v);
  }

  function bytesFromCurlFormValue(value, treatAtAsFile, stdinSize) {
    const v = String(value ?? "");
    const eq = v.indexOf("=");
    const rhs = eq >= 0 ? v.slice(eq + 1) : v;
    if (!treatAtAsFile) return Buffer.byteLength(rhs);
    if (rhs.startsWith("@") || rhs.startsWith("<")) {
      let path = rhs.slice(1);
      const semi = path.indexOf(";");
      if (semi >= 0) path = path.slice(0, semi);
      return fileByteLength(path, stdinSize);
    }
    return Buffer.byteLength(rhs);
  }

  function urlsFromListFile(path, stdinSize, options) {
    const cap = 65536;
    const maxUrls = 32;
    let text = "";
    try {
      if (String(path || "") === "-") {
        if (options && options.input != null) {
          const raw = Buffer.isBuffer(options.input)
            ? options.input
            : Buffer.from(String(options.input), "utf8");
          text = raw.slice(0, cap).toString("utf8");
        } else {
          if (!stdinSize) return [];
          let fd = 0;
          const stdio = options && options.stdio;
          if (stdio != null) {
            const s0 = Array.isArray(stdio) ? stdio[0] : stdio;
            if (typeof s0 === "number") fd = s0;
            else if (s0 && typeof s0.fd === "number") fd = s0.fd;
            else if (s0 !== "inherit") return [];
          }
          const buf = Buffer.alloc(Math.min(Number(stdinSize) || 0, cap));
          const n = readSync(fd, buf, 0, buf.length, 0);
          text = buf.slice(0, n).toString("utf8");
        }
      } else {
        const st = statSync(path);
        if (!st.isFile()) return [];
        const fd = openSync(String(path), "r");
        try {
          const buf = Buffer.alloc(Math.min(Number(st.size) || 0, cap));
          const n = readSync(fd, buf, 0, buf.length, 0);
          text = buf.slice(0, n).toString("utf8");
        } finally {
          closeSync(fd);
        }
      }
    } catch {
      return [];
    }
    const urls = [];
    for (const line of String(text).split(/\r?\n/)) {
      const s = line.trim();
      if (!s || s.startsWith("#")) continue;
      const token = s.split(/\s+/)[0];
      if (/^https?:\/\//i.test(token)) urls.push(token);
      if (urls.length >= maxUrls) break;
    }
    return urls;
  }

  const CURL_DATA_AT_FILE = {
    "-d": true,
    "--data": true,
    "--data-binary": true,
    "--data-ascii": true,
    "--data-urlencode": true,
    "--json": true,
    "--data-raw": false,
  };

  function urlFromCurlConfig(path) {
    try {
      const text = readFileSync(String(path || ""), "utf8");
      for (const line of text.split(/\r?\n/)) {
        const s = line.trim();
        if (!s || s.startsWith("#")) continue;
        if (!s.toLowerCase().startsWith("url")) continue;
        let rest = s.slice(3).trim();
        if (rest.startsWith("=")) rest = rest.slice(1).trim();
        rest = rest.replace(/^["']|["']$/g, "");
        if (/^https?:\/\//i.test(rest)) return rest;
      }
    } catch { /* missing config — pass through */ }
    return null;
  }

  function parseCurlArgv(argv, stdinSize) {
    let url = null;
    let dataBytes = 0;
    const configPaths = [];
    const args = Array.isArray(argv) ? argv : [];
    for (let i = 0; i < args.length; i++) {
      const a = String(args[i]);
      if (a === "--url" || a === "-url") {
        url = args[i + 1] != null ? String(args[i + 1]) : null;
        i += 1;
        continue;
      }
      if (a.startsWith("--url=")) {
        url = a.slice("--url=".length);
        continue;
      }
      if (a === "-K" || a === "--config") {
        if (args[i + 1] != null) configPaths.push(String(args[i + 1]));
        i += 1;
        continue;
      }
      if (a.startsWith("--config=")) {
        configPaths.push(a.slice("--config=".length));
        continue;
      }
      if (Object.prototype.hasOwnProperty.call(CURL_DATA_AT_FILE, a)) {
        const v = args[i + 1] != null ? String(args[i + 1]) : "";
        dataBytes += bytesFromAtOrLiteral(v, CURL_DATA_AT_FILE[a], stdinSize);
        i += 1;
        continue;
      }
      let eqHandled = false;
      for (const flag of Object.keys(CURL_DATA_AT_FILE)) {
        if (flag.startsWith("--") && a.startsWith(flag + "=")) {
          dataBytes += bytesFromAtOrLiteral(a.slice(flag.length + 1), CURL_DATA_AT_FILE[flag], stdinSize);
          eqHandled = true;
          break;
        }
      }
      if (eqHandled) continue;
      if (a.startsWith("-d") && a.length > 2 && !a.startsWith("--")) {
        dataBytes += bytesFromAtOrLiteral(a.slice(2), true, stdinSize);
        continue;
      }
      if (a === "-F" || a === "--form") {
        dataBytes += bytesFromCurlFormValue(args[i + 1] != null ? String(args[i + 1]) : "", true, stdinSize);
        i += 1;
        continue;
      }
      if (a.startsWith("--form=")) {
        dataBytes += bytesFromCurlFormValue(a.slice("--form=".length), true, stdinSize);
        continue;
      }
      if (a.startsWith("-F") && a.length > 2 && !a.startsWith("--")) {
        dataBytes += bytesFromCurlFormValue(a.slice(2), true, stdinSize);
        continue;
      }
      if (a === "--form-string") {
        dataBytes += bytesFromCurlFormValue(args[i + 1] != null ? String(args[i + 1]) : "", false, stdinSize);
        i += 1;
        continue;
      }
      if (a.startsWith("--form-string=")) {
        dataBytes += bytesFromCurlFormValue(a.slice("--form-string=".length), false, stdinSize);
        continue;
      }
      if (a === "-T" || a === "--upload-file") {
        dataBytes += fileByteLength(args[i + 1] != null ? String(args[i + 1]) : "", stdinSize);
        i += 1;
        continue;
      }
      if (a.startsWith("--upload-file=")) {
        dataBytes += fileByteLength(a.slice("--upload-file=".length), stdinSize);
        continue;
      }
      if (a.startsWith("-T") && a.length > 2 && !a.startsWith("--")) {
        dataBytes += fileByteLength(a.slice(2), stdinSize);
        continue;
      }
      if (!url && /^https?:\/\//i.test(a)) url = a;
    }
    if (!url) {
      for (const p of configPaths) {
        const fromCfg = urlFromCurlConfig(p);
        if (fromCfg) {
          url = fromCfg;
          break;
        }
      }
    }
    return { urls: url ? [url] : [], dataBytes };
  }

  function takeInputFileArg(args, i, a) {
    if (a === "-i" || a === "--input-file") {
      return { path: args[i + 1] != null ? String(args[i + 1]) : "", next: i + 2 };
    }
    if (a.startsWith("--input-file=")) {
      return { path: a.slice("--input-file=".length), next: i + 1 };
    }
    return null;
  }

  function parseWgetArgv(argv, stdinSize, options) {
    let url = null;
    let dataBytes = 0;
    const listPaths = [];
    const args = Array.isArray(argv) ? argv : [];
    for (let i = 0; i < args.length; i++) {
      const a = String(args[i]);
      if (a === "--post-data" || a === "--body-data") {
        const v = args[i + 1] != null ? String(args[i + 1]) : "";
        dataBytes += Buffer.byteLength(v);
        i += 1;
        continue;
      }
      if (a.startsWith("--post-data=")) {
        dataBytes += Buffer.byteLength(a.slice("--post-data=".length));
        continue;
      }
      if (a.startsWith("--body-data=")) {
        dataBytes += Buffer.byteLength(a.slice("--body-data=".length));
        continue;
      }
      if (a === "--post-file" || a === "--body-file") {
        dataBytes += fileByteLength(args[i + 1] != null ? String(args[i + 1]) : "", stdinSize);
        i += 1;
        continue;
      }
      if (a.startsWith("--post-file=")) {
        dataBytes += fileByteLength(a.slice("--post-file=".length), stdinSize);
        continue;
      }
      if (a.startsWith("--body-file=")) {
        dataBytes += fileByteLength(a.slice("--body-file=".length), stdinSize);
        continue;
      }
      const inputFile = takeInputFileArg(args, i, a);
      if (inputFile) {
        if (inputFile.path) listPaths.push(inputFile.path);
        i = inputFile.next - 1;
        continue;
      }
      if (!url && /^https?:\/\//i.test(a)) url = a;
    }
    const urls = [];
    if (url) urls.push(url);
    for (const p of listPaths) {
      for (const u of urlsFromListFile(p, stdinSize, options)) {
        if (!urls.includes(u)) urls.push(u);
      }
    }
    return { urls, dataBytes };
  }

  function parseUrlOnlyArgv(argv, stdinSize, options) {
    const urls = [];
    const listPaths = [];
    const args = Array.isArray(argv) ? argv : [];
    for (let i = 0; i < args.length; i++) {
      const a = String(args[i]);
      const inputFile = takeInputFileArg(args, i, a);
      if (inputFile) {
        if (inputFile.path) listPaths.push(inputFile.path);
        i = inputFile.next - 1;
        continue;
      }
      if (/^https?:\/\//i.test(a) && !urls.includes(a)) urls.push(a);
    }
    for (const p of listPaths) {
      for (const u of urlsFromListFile(p, stdinSize, options)) {
        if (!urls.includes(u)) urls.push(u);
      }
    }
    return { urls, dataBytes: 0 };
  }

  function parseCliArgv(tool, argv, options) {
    const stdinSize = stdinByteLength(options);
    if (tool === "wget") return parseWgetArgv(argv, stdinSize, options);
    if (tool === "httpie" || tool === "aria2c") return parseUrlOnlyArgv(argv, stdinSize, options);
    return parseCurlArgv(argv, stdinSize);
  }

  function destFromCurlUrl(url) {
    try {
      const u = new URL(String(url));
      const port = u.port || (u.protocol === "https:" ? "443" : "80");
      return { hostname: u.hostname, port: String(port) };
    } catch {
      return { hostname: null, port: null };
    }
  }

  function isControlPlaneCurlUrl(url) {
    try {
      const ingest = new URL(INGEST_URL);
      const u = new URL(String(url));
      const ingestPort = ingest.port || (ingest.protocol === "https:" ? "443" : "80");
      const reqPort = u.port || (u.protocol === "https:" ? "443" : "80");
      return u.hostname.toLowerCase() === ingest.hostname.toLowerCase()
        && reqPort === ingestPort
        && u.pathname.startsWith("/api/v1/");
    } catch {
      return false;
    }
  }

  function decideCurl(url, hostname, port, _dataBytes) {
    if (!hostname || isControlPlaneCurlUrl(url)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    return "observe";
  }

  function cliMeta(tool) {
    if (tool === "wget") return { mediation: "node_wget", label: "wget", method: "WGET", plane: "app_wget" };
    if (tool === "httpie") return { mediation: "node_httpie", label: "httpie", method: "HTTPIE", plane: "app_httpie" };
    if (tool === "aria2c") return { mediation: "node_aria2c", label: "aria2c", method: "ARIA2C", plane: "app_aria2c" };
    return { mediation: "node_curl", label: "curl", method: "CURL", plane: "app_curl" };
  }

  function recordCli(tool, hostname, port, dataBytes) {
    const provider = guessProvider(hostname, port);
    const meta = cliMeta(tool);
    _calls.push({
      hostname, provider, method: meta.method, path: null, scheme: "http",
      request_bytes: dataBytes, bytes: dataBytes, status: null,
      ok: true,
      content_type: null, duration_ms: 0, ts: new Date().toISOString(),
      action: "OBSERVED", mediation: meta.mediation, optics_plane: meta.plane,
      redactions: 0,
    });
    report({
      target_host: hostname, pid: process.pid, action_taken: "OBSERVED",
      timestamp_ns: Date.now() * 1e6,
      bytes_severed: 0,
      bytes_observed: dataBytes,
      request_bytes: dataBytes,
      mediation: meta.mediation, plane: "optics_gate",
      redactions: 0,
    });
    log(`${c.cyan}[ ∅ VANTIO ]${c.reset} Optics status: ${humanStatus("SUCCESS")} — ${hostname} — ${meta.label}`);
  }

  function applyCliGate(tool, argv, options) {
    const parsed = parseCliArgv(tool, argv, options);
    const urls = Array.isArray(parsed.urls) ? parsed.urls : [];
    for (const url of urls) {
      const dest = destFromCurlUrl(url);
      if (decideCurl(url, dest.hostname, dest.port, parsed.dataBytes) !== "observe") continue;
      recordCli(tool, dest.hostname, dest.port, parsed.dataBytes);
      spentUsd += (parsed.dataBytes || 0) * USD_PER_BYTE;
    }
  }

  cp.spawn = function vantioSpawn(...args) {
    try {
      const { command, argv, options } = splitSpawnArgs(args);
      const cli = httpCliFromSpawn(command, argv, options);
      if (!cli) return origSpawn(...args);
      applyCliGate(cli.tool, cli.argv, options);
      return origSpawn(...args);
    } catch {
      return origSpawn(...args);
    }
  };

  if (origSpawnSync) {
    cp.spawnSync = function vantioSpawnSync(...args) {
      try {
        const { command, argv, options } = splitSpawnArgs(args);
        const cli = httpCliFromSpawn(command, argv, options);
        if (!cli) return origSpawnSync(...args);
        applyCliGate(cli.tool, cli.argv, options);
        return origSpawnSync(...args);
      } catch {
        return origSpawnSync(...args);
      }
    };
  }

  if (origExecFile) {
    cp.execFile = function vantioExecFile(...args) {
      try {
        const { command: file, argv, options } = splitSpawnArgs(args);
        const cli = httpCliFromSpawn(file, argv, options);
        if (!cli) return origExecFile(...args);
        applyCliGate(cli.tool, cli.argv, options);
        return origExecFile(...args);
      } catch {
        return origExecFile(...args);
      }
    };
  }

  if (origExecFileSync) {
    cp.execFileSync = function vantioExecFileSync(...args) {
      try {
        const { command: file, argv, options } = splitSpawnArgs(args);
        const cli = httpCliFromSpawn(file, argv, options);
        if (cli) {
          applyCliGate(cli.tool, cli.argv, options);
        }
      } catch {
        /* observation must not stop the child */
      }
      return origExecFileSync(...args);
    };
  }

  if (origExec) {
    cp.exec = function vantioExec(...args) {
      try {
        const command = args[0];
        const cli = httpCliFromExec(command);
        if (!cli) return origExec(...args);
        const options = args[1] && typeof args[1] === "object" ? args[1] : null;
        applyCliGate(cli.tool, cli.argv, options);
        return origExec(...args);
      } catch {
        return origExec(...args);
      }
    };
  }

  if (origExecSync) {
    cp.execSync = function vantioExecSync(...args) {
      try {
        const command = args[0];
        const cli = httpCliFromExec(command);
        if (cli) {
          const options = args[1] && typeof args[1] === "object" ? args[1] : null;
          applyCliGate(cli.tool, cli.argv, options);
        }
      } catch {
        /* observation must not stop the child */
      }
      return origExecSync(...args);
    };
  }

  cp.__vantioCurlPatched = true;
})();

process.on("exit", () => {
  // `vantio run --summary` sets VANTIO_SUMMARY=1. Recorded calls already print
  // this local summary. The flag does not hide it and does not invent one
  // when the run recorded nothing.
  const summaryRequested = process.env.VANTIO_SUMMARY === "1";
  const hosts      = [...new Set(_calls.map((x) => x.hostname))];
  const now        = Date.now();
  const totalBytes = _calls.reduce((a, x) => a + (x.bytes || 0), 0);

  // NOTE: anonymous Lane 1 usage telemetry is NOT sent here. A fetch scheduled
  // inside a process "exit" handler never flushes (the event loop is already
  // draining), so the ping is emitted once after the first completed in-scope
  // call is recorded. This handler only prints the local summary.

  // ── Write a local run log for `vantio prove` / `vantio discover --local` ──
  // Always written on every vantio run, regardless of call count, tier, or
  // SUMMARY flag. Non-fatal — run log write must never crash the agent exit.
  try {
    const vantioHome = process.env.VANTIO_HOME || join(homedir(), ".vantio");
    const runsDir = join(vantioHome, "runs");
    mkdirSync(runsDir, { recursive: true, mode: 0o700 });
    const providers = [...new Set(_calls.map((x) => x.provider).filter(Boolean))];
    const errors = _calls.filter((x) => x.error || x.ok === false).length;
    const by_host = {};
    const by_provider = {};
    for (const call of _calls) {
      const h = call.hostname || "unknown";
      const p = call.provider || "unknown";
      by_host[h] = by_host[h] || { calls: 0, bytes: 0, errors: 0 };
      by_host[h].calls += 1;
      by_host[h].bytes += call.bytes || 0;
      if (call.error || call.ok === false) by_host[h].errors += 1;
      by_provider[p] = by_provider[p] || { calls: 0, bytes: 0 };
      by_provider[p].calls += 1;
      by_provider[p].bytes += call.bytes || 0;
    }
    const log = {
      vantio_run_log: "1",
      schema_version: 2,
      plane: "optics",
      data_note: "Developer egress data log — metadata only; never prompts or completions.",
      trace_id:    RUN_TRACE_ID,
      pid:         process.pid,
      ppid:        typeof process.ppid === "number" ? process.ppid : null,
      node_version: process.version,
      platform:    process.platform,
      arch:        process.arch,
      started_at:  new Date(_startMs).toISOString(),
      generated_at: new Date(now).toISOString(),
      duration_ms: now - _startMs,
      cli_version: CLI_VERSION,
      free_mode:   true,
      calls: _calls.map((call) => ({
        hostname:      call.hostname,
        provider:      call.provider || guessProvider(call.hostname),
        method:        call.method || null,
        path:          call.path || null,
        scheme:        call.scheme || null,
        request_bytes: call.request_bytes != null ? call.request_bytes : null,
        bytes:         call.bytes || 0,
        status:        call.status != null ? call.status : null,
        ok:            call.ok != null ? call.ok : null,
        content_type:  call.content_type || null,
        duration_ms:   call.duration_ms != null ? call.duration_ms : null,
        action:        call.action,
        ts:            call.ts || null,
        redactions:    call.redactions || 0,
        error:         call.error || null,
        error_class:   call.error_class || null,
      })),
      summary: {
        total_calls:   _calls.length,
        total_bytes:   totalBytes,
        hosts:         hosts,
        providers,
        errors,
        by_host,
        by_provider,
        redacted:      0,
        blocked:       0,
        est_spend_usd: null,
      },
      residual: {
        note: "Metadata only. Supported Node outbound calls to in-scope hosts are recorded locally. Prompts and completions are never stored. Browsers stay outside this wrap.",
      },
    };
    const safeid   = RUN_TRACE_ID.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
    const logPath  = join(runsDir, `${safeid}.json`);
    writeFileSync(logPath, JSON.stringify(log, null, 2) + "\n", { mode: 0o600 });
  } catch {
    // Non-fatal — never let log writing affect the exiting agent.
  }

  if (_calls.length === 0) {
    if (summaryRequested) {
      // No recorded calls. The summary flag does not print an empty banner.
    }
    return;
  }

  if (process.env.VANTIO_JSON === "1") {
    const rollup = rollupCalls(_calls);
    process.stderr.write(JSON.stringify({
      schema_status: SCHEMA_STATUS,
      event: "run_summary",
      opticsStatus: rollup.opticsStatus,
      applicationStatus: rollup.applicationStatus,
      calls: _calls.length,
      hosts,
      total_bytes: totalBytes,
      duration_ms: now - _startMs,
    }) + "\n");
    return;
  }

  const durationS  = ((now - _startMs) / 1000).toFixed(1);

  const lines = [
    "",
    `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.bold}Run Summary${c.reset}`,
    `  LLM calls:    ${c.yellow}${_calls.length}${c.reset}`,
    `  Hosts:        ${c.cyan}${hosts.join(", ")}${c.reset}`,
    `  Total bytes:  ${totalBytes > 0 ? totalBytes.toLocaleString() : "unknown"}`,
    `  Duration:     ${durationS}s`,
  ];
  lines.push(`  ${c.dim}→ Run \`vantio prove\` to export a local proof artifact from this run.${c.reset}`);
  lines.push("");
  process.stderr.write(lines.join("\n"));
});
