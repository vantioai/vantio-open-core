// [ ∅ VANTIO ] Open Core Interceptor — Observe Plane
// Injected at runtime by `vantio run node agent.js` via Node --require.
// Patches globalThis.fetch and Node http/https.request|get to intercept
// outbound LLM calls — zero code changes. Raw sockets, curl, and browser
// paths stay outside this wrap.
//
// Layer identity in the Vantio suite:
//   Open Core (this file) = OBSERVE PLANE — sees everything, no blocks on its own.
//   Pro control plane     = ENFORCE PLANE — policy (block/redact/cap) is fetched
//                           from the Pro server and applied locally by this interceptor.
//   Phantom Engine        = KERNEL PLANE  — eBPF enforcement beneath the app layer.
//   Enterprise suite      = all three running simultaneously.
//
//   Standalone (no API key):  observe + print to terminal only
//   With Pro API key:         fetch policy from Pro, then enforce locally (redact / cap / block / report)
//   Enterprise deployment:    this interceptor + Pro + Phantom Engine all active at once

"use strict";

const { randomUUID } = require("node:crypto");
const { mkdirSync, writeFileSync } = require("node:fs");
const { homedir, hostname: osHostname } = require("node:os");
const { join } = require("node:path");
const {
  LLM_HOSTS: BASE_LLM_HOSTS,
  hostListed,
  catalogInScope,
  guessProvider,
} = require("./llm-hosts.cjs");

const USE_COLOR = process.stderr.isTTY === true;
const c = {
  reset:  USE_COLOR ? "\x1b[0m"  : "",
  dim:    USE_COLOR ? "\x1b[2m"  : "",
  bold:   USE_COLOR ? "\x1b[1m"  : "",
  green:  USE_COLOR ? "\x1b[32m" : "",
  yellow: USE_COLOR ? "\x1b[33m" : "",
  red:    USE_COLOR ? "\x1b[31m" : "",
  cyan:   USE_COLOR ? "\x1b[36m" : "",
};

const INGEST_URL = process.env.VANTIO_INGEST_URL || "https://vantio.ai";
const API_KEY    = process.env.VANTIO_API_KEY;
const AUDIT_MODE = process.env.VANTIO_AUDIT_MODE === "1";
const SUMMARY    = process.env.VANTIO_SUMMARY    === "1";
const FREE_MODE  = !API_KEY;
// Stable for the life of this process (set by `vantio run` into child env).
const RUN_TRACE_ID = process.env.VANTIO_TRACE_ID || randomUUID();
// Explicit phantom-box soak only — do NOT infer from localhost (breaks unit tests
// that spin up ephemeral mock control planes on 127.0.0.1).
const SOAK_LOCAL = process.env.VANTIO_SOAK_LOCAL === "1";
// Local Gate control plane (Phantom-Box / dogfood) — never upsell Optics-only.
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

// ── Default policy (fail-open until cloud policy loads) ──────────────────────
const DEFAULT_POLICY = {
  enforce:           false,
  redact_pii:        false,
  pii_types:         ["ssn", "email", "credit_card", "phone"],
  allowed_hosts:     [],      // empty = all in-scope hosts allowed
  blocked_hosts:     [],
  max_request_bytes: 0,       // 0 = no limit
  spend_cap_usd:     0,       // 0 = no cap
  dry_run:           false,   // when true: log enforcement decisions without blocking
};

let policy = { ...DEFAULT_POLICY };

// Whether this key actually unlocks cloud sync. /api/v1/config fails open
// with a permissive policy for EVERY valid key (paid or free) so free users
// are never blocked — but /api/v1/ingest and /api/v1/discover correctly
// 403 for non-PRO/ENTERPRISE tenants. Without tracking tier separately, a
// free-tier user who has merely run `vantio login` looks identical to a paid
// one right up until their events start silently 403ing (report() swallows
// all errors by design, so that failure is otherwise invisible). Checked
// before every report() call and before claiming "routed to your dashboard"
// in the run summary.
let cloudSyncActive = false;
function isPaidTier(tier) {
  return tier === "PRO" || tier === "ENTERPRISE";
}

// ── Policy validation ────────────────────────────────────────────────────────
// A cloud policy is untrusted input. Coerce every field to its expected type so
// a malformed payload (e.g. blocked_hosts:null, pii_types:"email",
// spend_cap_usd:"x") can never make enforcement throw `.includes` / `for..of` /
// numeric errors inside vantioFetch. Bad fields fall back to safe defaults.
function asBool(v, d) {
  return typeof v === "boolean" ? v : d;
}
function asStrArray(v, d) {
  return Array.isArray(v) ? v.filter((x) => typeof x === "string") : d.slice();
}
function asNonNegNum(v, d) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n >= 0 ? n : d;
}
function normalizePolicy(raw) {
  const p = raw && typeof raw === "object" ? raw : {};
  return {
    enforce:           asBool(p.enforce, DEFAULT_POLICY.enforce),
    redact_pii:        asBool(p.redact_pii, DEFAULT_POLICY.redact_pii),
    pii_types:         asStrArray(p.pii_types, DEFAULT_POLICY.pii_types),
    allowed_hosts:     asStrArray(p.allowed_hosts, DEFAULT_POLICY.allowed_hosts),
    blocked_hosts:     asStrArray(p.blocked_hosts, DEFAULT_POLICY.blocked_hosts),
    max_request_bytes: asNonNegNum(p.max_request_bytes, DEFAULT_POLICY.max_request_bytes),
    spend_cap_usd:     asNonNegNum(p.spend_cap_usd, DEFAULT_POLICY.spend_cap_usd),
    dry_run:           asBool(p.dry_run, DEFAULT_POLICY.dry_run),
  };
}

// ── PII detection patterns ───────────────────────────────────────────────────
const PII_PATTERNS = {
  ssn:         { re: /\b\d{3}-\d{2}-\d{4}\b/g,                                label: "SSN" },
  email:       { re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,   label: "EMAIL" },
  credit_card: { re: /\b(?:\d[ -]?){13,16}\b/g,                              label: "CC" },
  phone:       { re: /\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,             label: "PHONE" },
};

// Rough cost estimate: ~4 bytes/token (≈1 byte/char for ASCII), blended
// $5 / 1M tokens. Applied per byte of request + response throughout, so the
// constant is treated consistently as USD-per-byte.
const USD_PER_BYTE = (5 / 1_000_000) / 4;

let spentUsd = 0;
const _calls = [];
const _startMs = Date.now();

if (typeof globalThis.fetch !== "function") {
  return; // Node < 18 — nothing to patch
}

const _originalFetch = globalThis.fetch;

function log(line) {
  process.stderr.write(line + "\n");
}

// ── Policy load (Tier 2) ──────────────────────────────────────────────────────
const policyReady = (async () => {
  if (FREE_MODE) return;
  try {
    const res = await _originalFetch.call(globalThis, `${INGEST_URL}/api/v1/config`, {
      method: "GET",
      headers: { "x-vantio-identity": API_KEY },
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      if (data && typeof data === "object" && data.policy) {
        // Validate the merged policy rather than trusting it verbatim so a
        // malformed cloud payload can never make enforcement throw.
        policy = normalizePolicy({ ...policy, ...data.policy });
        cloudSyncActive = isPaidTier(data.tier) || SOAK_LOCAL;
        log(`${c.dim}[ ∅ VANTIO ]${c.reset} Policy loaded — enforce=${policy.enforce}, redact=${policy.redact_pii}`);
        if (!cloudSyncActive) {
          log(
            LOCAL_GATE
              ? `${c.dim}[ ∅ VANTIO ] Local Gate — events sync to the on-box control plane (${INGEST_URL}).${c.reset}`
              : `${c.dim}[ ∅ VANTIO ] Free plan — calls observed locally only. Dashboard sync requires Pro or Enterprise (vantio.ai/pricing).${c.reset}`
          );
        } else if (SOAK_LOCAL) {
          log(`${c.dim}[ ∅ VANTIO ] Local Gate mode — syncing events to ${INGEST_URL}${c.reset}`);
        }
      }
    }
  } catch {
    // Policy fetch failed — fail open (observe only). Never block the agent
    // because our control plane is unreachable.
  }
})();

// ── Redaction ─────────────────────────────────────────────────────────────────
// Core regex redactor over a single string. Returns the redacted text and the
// list of PII categories matched (one entry per span).
function redactString(text) {
  let out = text;
  const redactions = [];
  for (const type of policy.pii_types) {
    // Cloud policies may store pii_types in any case (the dashboard persists
    // UPPERCASE, e.g. "EMAIL"); normalize before looking up the lowercase
    // pattern keys so redaction fires regardless of stored case.
    const key = typeof type === "string" ? type.trim().toLowerCase() : type;
    const p = PII_PATTERNS[key];
    if (!p) continue;
    out = out.replace(p.re, () => {
      redactions.push(key);
      return `[VANTIO_REDACTED:${p.label}]`;
    });
  }
  return { text: out, redactions };
}

// Recursively redact only the *string* values of a parsed JSON structure.
// Numbers/booleans/null are left intact so a bare numeric value such as
// {"ids":[1234567890123456]} can never be mangled into invalid JSON by the
// credit-card pattern (which would otherwise match the digits).
function redactJsonValue(value, redactions) {
  if (typeof value === "string") {
    const r = redactString(value);
    for (const k of r.redactions) redactions.push(k);
    return r.text;
  }
  if (Array.isArray(value)) {
    return value.map((v) => redactJsonValue(v, redactions));
  }
  if (value && typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value)) {
      out[key] = redactJsonValue(value[key], redactions);
    }
    return out;
  }
  return value;
}

// JSON-aware body redactor. When the body parses as JSON we walk it and redact
// only string values, then re-serialize so the output stays valid JSON.
// Otherwise we fall back to plain text redaction.
function redactBody(text) {
  if (typeof text !== "string" || !policy.redact_pii) return { text, redactions: [] };
  const trimmed = text.trim();
  if (trimmed && (trimmed[0] === "{" || trimmed[0] === "[")) {
    try {
      const parsed = JSON.parse(text);
      const redactions = [];
      const out = redactJsonValue(parsed, redactions);
      return { text: JSON.stringify(out), redactions };
    } catch {
      // Not valid JSON despite the leading brace/bracket — fall through to text.
    }
  }
  return redactString(text);
}

// Names a body type we deliberately do not scan (streaming/multipart/binary
// blob) so the caller can emit a one-line notice instead of silently passing.
function unscannableBodyLabel(body) {
  if (typeof ReadableStream !== "undefined" && body instanceof ReadableStream) return "ReadableStream";
  if (typeof FormData !== "undefined" && body instanceof FormData) return "FormData";
  if (typeof Blob !== "undefined" && body instanceof Blob) return "Blob";
  return null;
}

// Maximum bytes we will buffer from a ReadableStream to scan for PII.
// Requests larger than this threshold pass through unscanned rather than being
// held in memory, preserving back-pressure for true streaming workloads.
const MAX_STREAM_SCAN_BYTES = 2 * 1024 * 1024; // 2 MB ? max Latch (2026-08-09); was 64 KB

// Redact a concrete request body value, preserving its original type.
// Returns { value, bytes, redactions, replaced, unscanned }:
//   - string / URLSearchParams / Uint8Array / Buffer / ArrayBuffer → decoded to
//     text, redacted, and re-encoded to the same type. `replaced` is true when
//     any redaction happened (so the caller knows to swap the body).
//   - ReadableStream ≤ 64 KB → tee'd, buffered, scanned; redacted copy returned
//     as Uint8Array when PII found, pass-through branch returned unchanged when not.
//   - ReadableStream > 64 KB / FormData / Blob → not scanned; `unscanned` is its label.
// Never throws — on any unexpected shape it returns the body unchanged.
// This function is async because ReadableStream buffering requires awaiting reads.
async function redactRequestBody(body) {
  const none = { value: body, bytes: 0, redactions: [], replaced: false, unscanned: null };
  if (body == null) return none;

  if (typeof body === "string") {
    const r = redactBody(body);
    return { value: r.text, bytes: Buffer.byteLength(r.text), redactions: r.redactions, replaced: r.redactions.length > 0, unscanned: null };
  }

  if (typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams) {
    const r = redactBody(body.toString());
    const value = r.redactions.length > 0 ? new URLSearchParams(r.text) : body;
    return { value, bytes: Buffer.byteLength(r.text), redactions: r.redactions, replaced: r.redactions.length > 0, unscanned: null };
  }

  if (Buffer.isBuffer(body) || body instanceof Uint8Array) {
    const text = Buffer.from(body).toString("utf8");
    const r = redactBody(text);
    const buf = Buffer.from(r.text, "utf8");
    const value = r.redactions.length > 0
      ? (Buffer.isBuffer(body) ? buf : new Uint8Array(buf))
      : body;
    return { value, bytes: buf.length, redactions: r.redactions, replaced: r.redactions.length > 0, unscanned: null };
  }

  if (body instanceof ArrayBuffer) {
    const text = Buffer.from(new Uint8Array(body)).toString("utf8");
    const r = redactBody(text);
    const buf = Buffer.from(r.text, "utf8");
    const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
    return { value: r.redactions.length > 0 ? ab : body, bytes: buf.length, redactions: r.redactions, replaced: r.redactions.length > 0, unscanned: null };
  }

  // ── ReadableStream: tee + buffer up to MAX_STREAM_SCAN_BYTES ─────────────
  // We tee the stream so the pass-through branch (b) always carries the full
  // original content. The scan branch (a) is read until we confirm the body
  // fits within the scan window. If PII is found we return the redacted text as
  // a Uint8Array (the stream was small enough that buffering is safe). If no PII
  // is found we return the pass-through branch so the network call is unaffected.
  // Streams larger than the threshold fall back to unscanned — no bytes consumed
  // on the pass-through branch, preserving back-pressure.
  if (typeof ReadableStream !== "undefined" && body instanceof ReadableStream) {
    try {
      const [scanBranch, passBranch] = body.tee();
      const reader = scanBranch.getReader();
      const chunks = [];
      let total = 0;
      let oversized = false;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const n = value ? (value.byteLength != null ? value.byteLength : value.length || 0) : 0;
        total += n;
        if (total > MAX_STREAM_SCAN_BYTES) { oversized = true; break; }
        if (value) chunks.push(value);
      }
      // Release our scan reader regardless of outcome so GC can clean up.
      try { reader.cancel(); } catch { /* ignore */ }

      if (!oversized) {
        // Full body fits — scan and optionally redact.
        const all = Buffer.concat(chunks.map((c) => Buffer.from(c)));
        const text = all.toString("utf8");
        const r = redactBody(text);
        if (r.redactions.length > 0) {
          // PII found: return the redacted content as a Uint8Array so the
          // caller can substitute it for the original stream.
          const buf = Buffer.from(r.text, "utf8");
          return { value: new Uint8Array(buf), bytes: buf.length, redactions: r.redactions, replaced: true, unscanned: null };
        }
        // No PII: use the pass-through branch (original content, no latency).
        return { value: passBranch, bytes: total, redactions: [], replaced: false, unscanned: null };
      }
      // Oversized — use pass-through branch unmodified; log as unscanned.
      return { value: passBranch, bytes: 0, redactions: [], replaced: false, unscanned: "ReadableStream" };
    } catch {
      // tee() / read failed (e.g. stream already locked) — fall through below.
    }
    return { value: body, bytes: 0, redactions: [], replaced: false, unscanned: "ReadableStream" };
  }

  const label = unscannableBodyLabel(body);
  if (label) return { value: body, bytes: 0, redactions: [], replaced: false, unscanned: label };

  return none;
}

// ── Synthetic blocked response ────────────────────────────────────────────────
function blockedResponse(reason) {
  return new Response(
    JSON.stringify({ error: "blocked_by_vantio", reason }),
    { status: 403, headers: { "content-type": "application/json", "x-vantio-blocked": reason } }
  );
}

function report(metadata) {
  if (FREE_MODE || !INGEST_URL || !cloudSyncActive) return;
  // Additive Optics Sight Loop fields — Gate stores opaque JSON; PE joins on traceId.
  const host = metadata && metadata.target_host;
  const eventPayload = {
    ...metadata,
    provider: metadata.provider || (host ? guessProvider(host) : undefined),
    mediation: metadata.mediation || "sight_loop",
    plane: metadata.plane || "optics_gate",
  };
  void _originalFetch.call(globalThis, `${INGEST_URL}/api/v1/ingest`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-vantio-identity": API_KEY,
      "x-vantio-trace-id": RUN_TRACE_ID,
    },
    body: JSON.stringify({
      traceId:   RUN_TRACE_ID,
      auditMode: AUDIT_MODE,
      eventPayload,
    }),
    signal: AbortSignal.timeout(5000),
  }).catch(() => {});
}

// ── Host scope ────────────────────────────────────────────────────────────────
// A host is "in scope" for enforcement when it is a known LLM host OR is named
// in the policy (blocked_hosts ∪ allowed_hosts). Hosts outside this set are
// passed straight through untouched — we never block, redact, or meter general
// (OS / package-manager / unrelated) traffic merely because a policy exists.
function inScope(hostname, port) {
  return (
    catalogInScope(hostname, port, LLM_HOSTS) ||
    hostListed(hostname, policy.blocked_hosts) ||
    hostListed(hostname, policy.allowed_hosts)
  );
}

// ── Response byte accounting (spend cap) ───────────────────────────────────────
// Streaming SSE responses (the common LLM case) omit content-length, so output
// bytes — the dominant cost — would otherwise never be counted. When there is no
// content-length we read a response.clone() body stream in the background and
// add bytes to spentUsd as they arrive. The clone is independent, so this never
// consumes or delays the body the agent receives.
//
// NOTE: the spend cap is best-effort and per-process. It cannot block a call
// mid-stream (bytes are counted after the fact) and does not aggregate across
// processes; it gates *subsequent* calls once the running total crosses the cap.
function trackStreamBytes(response, onDone) {
  let body;
  try {
    body = response.clone().body;
  } catch {
    return; // Clone unsupported / already disturbed — skip best-effort metering.
  }
  if (!body || typeof body.getReader !== "function") return;
  (async () => {
    try {
      const reader = body.getReader();
      let total = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        const n = value ? (value.byteLength != null ? value.byteLength : value.length || 0) : 0;
        total += n;
        spentUsd += n * USD_PER_BYTE;
      }
      if (typeof onDone === "function") onDone(total);
    } catch {
      // Best-effort — a read error must never affect the agent's own response.
    }
  })();
}

// ── Lane 1 run telemetry (anonymous, opt-out, once-per-process) ─────────────────
// fetch scheduled inside a process "exit" handler never actually flushes, so the
// summary ping was effectively dead. Instead we fire a single anonymous "run"
// ping on the first intercepted in-scope call (mirroring the Python SDK's
// send_run_telemetry_once). Fire-and-forget, non-blocking, opt-out honored.
let _runTelemetrySent = false;
function sendRunTelemetryOnce(hostname) {
  if (_runTelemetrySent) return;
  _runTelemetrySent = true;
  try {
    sendTelemetry({
      event: "run",
      hosts: hostname ? [hostname] : [],
      callCount: 0,
      cliVersion: CLI_VERSION,
    });
  } catch {
    // Telemetry must never affect the agent.
  }
}

// ── Block builders ──────────────────────────────────────────────────────────
// Each records the call, prints the action, reports it, and returns a synthetic
// 403 — preserving the original block/redact/report actions and labels.
function blockHost(hostname) {
  _calls.push({ hostname, action: "BLOCKED_HOST" });
  log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — host not permitted by policy`);
  report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_HOST",
           timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
  return { blocked: true, response: blockedResponse("host_not_permitted") };
}
function blockSize(hostname, reqBytes) {
  _calls.push({ hostname, action: "BLOCKED_SIZE" });
  log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — request ${reqBytes}B exceeds cap ${policy.max_request_bytes}B`);
  report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SIZE",
           timestamp_ns: Date.now() * 1e6, bytes_severed: reqBytes });
  return { blocked: true, response: blockedResponse("request_too_large") };
}
function blockSpend(hostname) {
  _calls.push({ hostname, action: "BLOCKED_SPEND" });
  log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — spend cap $${policy.spend_cap_usd} reached`);
  report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SPEND",
           timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
  return { blocked: true, response: blockedResponse("spend_cap_reached") };
}

// ── Request enforcement decision ──────────────────────────────────────────────
// Applies host allow/block, body redaction (all body shapes + Request objects),
// and size/spend gates. Returns either { blocked, response } or
// { blocked:false, input, init, reqBytes, redactions } describing the
// (possibly redacted) request to send. Pure decision logic — any throw here is
// caught by the caller and fails OPEN.
//
// dry_run mode: when policy.dry_run=true, enforcement decisions are logged and
// reported as DRY_RUN_* events but the call is never blocked. Use this to
// validate a new policy against live traffic before enabling hard enforcement.
async function enforceRequest(hostname, input, init) {
  // 1. Host allow/block policy. blocked_hosts blocks ANY in-scope host; a
  //    non-empty allow-list blocks any in-scope host not on it. (Out-of-scope
  //    hosts never reach here — they pass through before enforcement.)
  if (policy.enforce) {
    if (hostListed(hostname, policy.blocked_hosts)) {
      if (policy.dry_run) {
        _calls.push({ hostname, action: "DRY_RUN_BLOCKED_HOST" });
        log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK (host_not_permitted); dry_run=true passes through`);
        report({ target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_HOST",
                 timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
        // Fall through — allow call in dry_run mode
      } else {
        return blockHost(hostname);
      }
    } else if (policy.allowed_hosts.length > 0 && !hostListed(hostname, policy.allowed_hosts)) {
      if (policy.dry_run) {
        _calls.push({ hostname, action: "DRY_RUN_BLOCKED_HOST" });
        log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK (not_in_allowed_hosts); dry_run=true passes through`);
        report({ target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_HOST",
                 timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
      } else {
        return blockHost(hostname);
      }
    }
  }

  // 2. Read + optionally redact the request body (any body type or location).
  let redactions = [];
  let reqBytes = 0;
  let newInput = input;
  let newInit = init;

  if (init && init.body != null) {
    const r = await redactRequestBody(init.body);
    reqBytes = r.bytes;
    redactions = r.redactions;
    if (r.unscanned) {
      log(`${c.dim}[ ∅ VANTIO ] ${hostname} — ${r.unscanned} request body not scanned for PII (passed through)${c.reset}`);
      // Emit enforcement gap: Pro cannot redact streaming/opaque bodies.
      // These events feed /api/v1/residual-risk and surface the Enterprise upgrade path.
      if (policy.redact_pii) {
        report({ target_host: hostname, pid: process.pid, action_taken: "ENFORCEMENT_GAP",
                 gap_type: "unscanned_body", body_type: r.unscanned,
                 timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
      }
    } else if (r.replaced) {
      newInit = { ...init, body: r.value };
    }
  } else if (typeof Request !== "undefined" && input instanceof Request) {
    // The body rides on the Request object. Read a clone so the original stays
    // usable, redact, and rebuild the Request with the redacted body.
    let text = "";
    try {
      text = await input.clone().text();
    } catch {
      text = "";
    }
    if (text) {
      const r = redactBody(text);
      reqBytes = Buffer.byteLength(r.text);
      redactions = r.redactions;
      if (r.redactions.length > 0) {
        newInput = new Request(input, { body: r.text });
      }
    } else if (input.body) {
      // A streaming body on the Request that text() could not materialize.
      log(`${c.dim}[ ∅ VANTIO ] ${hostname} — streaming request body not scanned for PII (passed through)${c.reset}`);
      if (policy.redact_pii) {
        report({ target_host: hostname, pid: process.pid, action_taken: "ENFORCEMENT_GAP",
                 gap_type: "unscanned_body", body_type: "ReadableStream",
                 timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
      }
    }
  }

  // 3. Request size policy
  if (policy.enforce && policy.max_request_bytes > 0 && reqBytes > policy.max_request_bytes) {
    if (policy.dry_run) {
      _calls.push({ hostname, action: "DRY_RUN_BLOCKED_SIZE" });
      log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK (${reqBytes}B > cap ${policy.max_request_bytes}B); dry_run=true passes through`);
      report({ target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_SIZE",
               timestamp_ns: Date.now() * 1e6, bytes_severed: reqBytes });
    } else {
      return blockSize(hostname, reqBytes);
    }
  }

  // 4. Spend cap policy
  if (policy.enforce && policy.spend_cap_usd > 0 && spentUsd >= policy.spend_cap_usd) {
    if (policy.dry_run) {
      _calls.push({ hostname, action: "DRY_RUN_BLOCKED_SPEND" });
      log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK (spend cap $${policy.spend_cap_usd} reached); dry_run=true passes through`);
      report({ target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_SPEND",
               timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
    } else {
      return blockSpend(hostname);
    }
  }

  return { blocked: false, input: newInput, init: newInit, reqBytes, redactions };
}

function destFromHref(href) {
  const u = new URL(href);
  const port = u.port || (u.protocol === "https:" ? "443" : "80");
  return { hostname: u.hostname, port };
}

globalThis.fetch = async function vantioFetch(input, init) {
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
    return _originalFetch.call(this, input, init);
  }

  // In paid mode the in-scope set depends on the cloud policy's
  // blocked_hosts/allowed_hosts, so the policy MUST be loaded before we decide
  // scope — otherwise an early call to a policy-named host would race past
  // enforcement. policyReady is bounded (5s) and fails open, and resolves
  // instantly once loaded, so later calls pay no cost.
  if (!FREE_MODE) {
    await policyReady;
  }

  // Out of scope (not a known LLM host and not named in policy) — pass straight
  // through, untouched. We never block/redact/meter unrelated traffic.
  if (!inScope(hostname, port)) {
    return _originalFetch.call(this, input, init);
  }

  // Anonymous, opt-out, once-per-process usage ping (fire-and-forget).
  sendRunTelemetryOnce(hostname);

  // ── FREE TIER — observe only ────────────────────────────────────────────────
  if (FREE_MODE) {
    const reqMeta = extractRequestMeta(input, init);
    const provider = guessProvider(hostname, port);
    const t0 = Date.now();
    let response;
    try {
      response = await _originalFetch.call(this, input, init);
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
      log([
        "",
        `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.red}Outbound LLM call failed${c.reset}`,
        `  host:     ${c.cyan}${hostname}${c.reset}`,
        `  provider: ${provider}`,
        `  method:   ${reqMeta.method} ${reqMeta.path}`,
        `  error:    ${err && err.name ? err.name : "Error"}`,
        `  duration: ${duration_ms}ms`,
        `  pid:      ${process.pid}`,
        `  time:     ${ts}`,
      ].join("\n"));
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
    log([
      "",
      `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.yellow}Outbound LLM call intercepted${c.reset}`,
      `  host:     ${c.cyan}${hostname}${c.reset}`,
      `  provider: ${provider}`,
      `  method:   ${reqMeta.method} ${reqMeta.path}`,
      `  status:   ${resp.status != null ? resp.status : "unknown"}`,
      `  duration: ${duration_ms}ms`,
      `  bytes:    ${resp.bytes != null ? resp.bytes.toLocaleString() : "unknown"}`,
      `  pid:      ${process.pid}`,
      `  time:     ${ts}`,
      LOCAL_GATE
        ? `  ${c.dim}→ Local Gate attached — observe now; run with VANTIO_API_KEY for Policy Latch enforce.${c.reset}`
        : `  ${c.dim}→ Optics data log (your machine). See docs/sight-loop.md · Gate enforces on this path.${c.reset}`,
    ].join("\n"));
    return response;
  }

  // ── PAID TIER — enforce policy ──────────────────────────────────────────────
  // (policyReady already awaited above.)

  // Decide + transform the request. Any UNEXPECTED error here fails OPEN: we
  // fall through to a plain pass-through fetch rather than rejecting the agent's
  // call. (The real network call below is intentionally outside this guard so a
  // genuine network rejection propagates instead of being silently re-tried.)
  let plan;
  try {
    plan = await enforceRequest(hostname, input, init);
  } catch {
    return _originalFetch.call(this, input, init);
  }
  if (plan.blocked) return plan.response;

  // Make the (possibly redacted) call. A rejection here is the agent's own
  // network error and propagates unchanged.
  const t0 = Date.now();
  const response = await _originalFetch.call(this, plan.input, plan.init);
  const duration_ms = Math.max(0, Date.now() - t0);

  // Post-call accounting + reporting — guarded so a metering error never
  // surfaces to the agent, which already holds a valid response.
  try {
    const action = plan.redactions.length > 0 ? "REDACTED" : "ALLOWED";
    const reqMeta = extractRequestMeta(plan.input, plan.init);
    const resp = responseMeta(response);
    const callRec = {
      hostname,
      provider: guessProvider(hostname, port),
      method: reqMeta.method,
      path: reqMeta.path,
      scheme: reqMeta.scheme,
      request_bytes: plan.reqBytes || reqMeta.request_bytes,
      bytes: 0,
      status: resp.status,
      ok: resp.ok,
      content_type: resp.content_type,
      duration_ms,
      action,
      redactions: plan.redactions.length,
      ts: new Date().toISOString(),
    };
    _calls.push(callRec);

    const len = response.headers.get("content-length");
    if (len != null && len !== "") {
      const respBytes = parseInt(len, 10) || 0;
      callRec.bytes = respBytes;
      spentUsd += (plan.reqBytes + respBytes) * USD_PER_BYTE;
    } else {
      // Streaming SSE (no content-length): count request bytes now and the
      // response bytes in the background from an independent clone.
      spentUsd += plan.reqBytes * USD_PER_BYTE;
      trackStreamBytes(response, (total) => { callRec.bytes = total; });
    }

    if (plan.redactions.length > 0) {
      log(`${c.green}[ ∅ VANTIO ] REDACTED${c.reset} ${hostname} — stripped ${plan.redactions.length} PII item(s): ${plan.redactions.join(", ")}`);
    }
    report({
      target_host: hostname,
      pid: process.pid,
      action_taken: action,
      timestamp_ns: Date.now() * 1e6,
      bytes_severed: callRec.bytes,
      provider: callRec.provider,
      method: callRec.method,
      path: callRec.path,
      status: callRec.status,
      content_type: callRec.content_type,
      request_bytes: callRec.request_bytes,
      duration_ms: callRec.duration_ms,
      ok: callRec.ok,
    });
  } catch {
    // Accounting/reporting must never break the agent's call.
  }

  return response;
};

// ── Run summary ─────────────────────────────────────────────────────────────


// Node http/https — same Sight Loop / Gate rules as fetch, last-known policy
// (request() is sync; fail-open until policy loads). Out-of-scope hosts and
// the ingest control plane pass through untouched. Raw sockets / curl / browsers
// stay residual.
(function patchNodeHttpHttps() {
  const { EventEmitter } = require("node:events");

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

  function blockedClientRequest(err) {
    const fake = new EventEmitter();
    fake.end = () => fake;
    fake.write = () => true;
    fake.abort = () => {};
    fake.destroy = () => {};
    fake.setTimeout = () => fake;
    fake.setHeader = () => {};
    fake.getHeader = () => undefined;
    fake.removeHeader = () => {};
    process.nextTick(() => fake.emit("error", err));
    return fake;
  }

  let policySettled = FREE_MODE;
  if (!FREE_MODE && policyReady && typeof policyReady.then === "function") {
    policyReady.then(() => { policySettled = true; }).catch(() => { policySettled = true; });
  }

  function decideHttp(hostname, port, args) {
    if (!hostname || isControlPlaneRequest(args)) return "pass";
    if (!inScope(hostname, port)) return "pass";
    if (FREE_MODE) return "observe";
    if (policy.enforce) {
      const blocked = hostListed(hostname, policy.blocked_hosts) ||
        (policy.allowed_hosts.length > 0 && !hostListed(hostname, policy.allowed_hosts));
      if (blocked) return policy.dry_run ? "dry_block" : "block";
    }
    return "observe";
  }

  function wrapModule(mod, scheme) {
    if (!mod || typeof mod.request !== "function") return;
    if (mod.__vantioPatched) return;
    const origRequest = mod.request.bind(mod);
    const origGet = typeof mod.get === "function" ? mod.get.bind(mod) : null;

    function pendingRequest(args, launch) {
      const pending = new EventEmitter();
      const buffer = [];
      pending.write = (c, e, cb) => { buffer.push(["write", c, e, cb]); return true; };
      pending.end = (c, e, cb) => { buffer.push(["end", c, e, cb]); return pending; };
      pending.abort = () => {};
      pending.destroy = () => {};
      pending.setTimeout = () => pending;
      pending.setHeader = () => {};
      pending.getHeader = () => undefined;
      pending.removeHeader = () => {};
      policyReady.then(() => {
        policySettled = true;
        try {
          const real = wrapLaunch(args, launch);
          if (real && typeof real.on === "function") {
            real.on("error", (err) => pending.emit("error", err));
            real.on("response", (res) => pending.emit("response", res));
            real.on("socket", (sock) => pending.emit("socket", sock));
            real.on("timeout", () => pending.emit("timeout"));
            real.on("close", () => pending.emit("close"));
          }
          for (const [op, c, e, cb] of buffer) {
            if (op === "write" && real && real.write) real.write(c, e, cb);
            if (op === "end" && real && real.end) real.end(c, e, cb);
          }
        } catch (err) {
          pending.emit("error", err);
        }
      }).catch((err) => pending.emit("error", err));
      return pending;
    }

    function wrapLaunch(args, launch) {
      if (!FREE_MODE && !policySettled) {
        return pendingRequest(args, launch);
      }
      const dest = destFromArgs(args);
      const hostname = dest.hostname;
      const port = dest.port;
      const decision = decideHttp(hostname, port, args);
      if (decision === "pass") return launch();

      sendRunTelemetryOnce(hostname);
      const provider = guessProvider(hostname, port);
      const ts = new Date().toISOString();
      const baseCall = {
        hostname, provider, method: "REQUEST", path: null, scheme,
        request_bytes: null, bytes: 0, status: null, ok: true,
        content_type: null, duration_ms: 0, ts, optics_plane: "app_http",
      };

      if (decision === "block") {
        _calls.push({ ...baseCall, action: "BLOCKED_HOST", ok: false });
        report({
          target_host: hostname, pid: process.pid, action_taken: "BLOCKED_HOST",
          timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
          mediation: "node_http", plane: "optics_gate",
        });
        log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — Node ${scheme}.request`);
        const err = new Error(`Vantio Gate blocked host: ${hostname}`);
        err.code = "VANTIO_GATE_BLOCKED";
        return blockedClientRequest(err);
      }

      if (!FREE_MODE && policy.enforce && policy.spend_cap_usd > 0 && spentUsd >= policy.spend_cap_usd) {
        if (policy.dry_run) {
          _calls.push({ ...baseCall, action: "DRY_RUN_BLOCKED_SPEND" });
          report({
            target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_SPEND",
            timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
            mediation: "node_http", plane: "optics_gate",
          });
          log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK Node ${scheme} spend cap $${policy.spend_cap_usd}; dry_run=true passes through`);
        } else {
          _calls.push({ ...baseCall, action: "BLOCKED_SPEND", ok: false });
          report({
            target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SPEND",
            timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
            mediation: "node_http", plane: "optics_gate",
          });
          log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — Node ${scheme} spend cap $${policy.spend_cap_usd} reached`);
          const err = new Error("Vantio Gate blocked request: spend_cap_reached");
          err.code = "VANTIO_GATE_BLOCKED";
          return blockedClientRequest(err);
        }
      }

      if (decision === "dry_block") {
        _calls.push({ ...baseCall, action: "DRY_RUN_BLOCKED_HOST" });
        report({
          target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_HOST",
          timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
          mediation: "node_http", plane: "optics_gate",
        });
        log(`${c.yellow}[ ∅ VANTIO ] DRY_RUN${c.reset} ${hostname} — would BLOCK Node ${scheme}.request; dry_run=true passes through`);
      } else {
        _calls.push({ ...baseCall, action: FREE_MODE ? "OBSERVED" : "ALLOWED" });
        report({
          target_host: hostname, pid: process.pid,
          action_taken: FREE_MODE ? "OBSERVED" : "ALLOWED",
          timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
          mediation: "node_http", plane: "optics_gate",
        });
        if (FREE_MODE) {
          log(`${c.cyan}[ ∅ VANTIO ] OBSERVED${c.reset} ${hostname} — Node ${scheme}.request`);
        }
      }

      const req = launch();
      if (req && typeof req.on === "function") {
        req.on("response", (res) => {
          try {
            const cl = parseInt(res && res.headers && res.headers["content-length"], 10);
            if (Number.isFinite(cl) && cl > 0) spentUsd += cl * USD_PER_BYTE;
          } catch { /* ignore */ }
        });
      }
      if (!req || typeof req.write !== "function") return req;
      if (FREE_MODE || (!policy.redact_pii && !(policy.enforce && policy.max_request_bytes > 0))) {
        return req;
      }

      const origWrite = req.write.bind(req);
      let written = 0;
      req.write = function vantioHttpWrite(chunk, encoding, cb) {
        try {
          const buf = chunk == null ? Buffer.alloc(0)
            : Buffer.isBuffer(chunk) ? chunk
            : Buffer.from(String(chunk), typeof encoding === "string" ? encoding : "utf8");
          written += buf.length;
          if (policy.enforce && policy.max_request_bytes > 0 && written > policy.max_request_bytes) {
            if (policy.dry_run) {
              report({
                target_host: hostname, pid: process.pid, action_taken: "DRY_RUN_BLOCKED_SIZE",
                timestamp_ns: Date.now() * 1e6, bytes_severed: written,
                mediation: "node_http",
              });
              return origWrite(chunk, encoding, cb);
            }
            report({
              target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SIZE",
              timestamp_ns: Date.now() * 1e6, bytes_severed: written,
              mediation: "node_http",
            });
            log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — Node ${scheme} request ${written}B exceeds cap`);
            const err = new Error("Vantio Gate blocked request: request_too_large");
            err.code = "VANTIO_GATE_BLOCKED";
            process.nextTick(() => req.emit("error", err));
            return false;
          }
          if (policy.redact_pii && buf.length) {
            const r = redactBody(buf.toString("utf8"));
            if (r.redactions.length) {
              report({
                target_host: hostname, pid: process.pid, action_taken: "REDACTED",
                timestamp_ns: Date.now() * 1e6, bytes_severed: 0,
                mediation: "node_http",
              });
              log(`${c.green}[ ∅ VANTIO ] REDACTED${c.reset} ${hostname} — Node ${scheme}.request stripped ${r.redactions.length} PII item(s)`);
              return origWrite(Buffer.from(r.text, "utf8"), undefined, cb);
            }
          }
        } catch {
          // Fail open — never break the agent's write.
        }
        return origWrite(chunk, encoding, cb);
      };
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
    mod.__vantioPatched = true;
  }

  try { wrapModule(require("node:http"), "http"); } catch { try { wrapModule(require("http"), "http"); } catch { /* ignore */ } }
  try { wrapModule(require("node:https"), "https"); } catch { try { wrapModule(require("https"), "https"); } catch { /* ignore */ } }
})();

process.on("exit", () => {
  if (_calls.length === 0) return;

  const hosts      = [...new Set(_calls.map((x) => x.hostname))];
  const redacted   = _calls.filter((x) => x.action === "REDACTED").length;
  const blocked    = _calls.filter((x) => String(x.action).startsWith("BLOCKED")).length;
  const now        = Date.now();
  const totalBytes = _calls.reduce((a, x) => a + (x.bytes || 0), 0);

  // NOTE: anonymous Lane 1 usage telemetry is NOT sent here. A fetch scheduled
  // inside a process "exit" handler never flushes (the event loop is already
  // draining), so the ping is emitted once on the first intercepted call via
  // sendRunTelemetryOnce() instead. This handler only prints the local summary.

  // ── Write a local run log for `vantio prove` / `vantio discover --local` ──
  // Always written when LLM calls were observed, regardless of tier or SUMMARY
  // flag. Non-fatal — run log write must never crash the agent exit.
  try {
    const vantioHome = process.env.VANTIO_HOME || join(homedir(), ".vantio");
    const runsDir = join(vantioHome, "runs");
    mkdirSync(runsDir, { recursive: true, mode: 0o700 });
    const machineHost = (() => { try { return osHostname(); } catch { return "unknown"; } })();
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
      workflow: "sight_loop",
      data_note: "Developer egress data log — metadata only; never prompts or completions.",
      trace_id:    RUN_TRACE_ID,
      pid:         process.pid,
      ppid:        typeof process.ppid === "number" ? process.ppid : null,
      node_version: process.version,
      platform:    process.platform,
      arch:        process.arch,
      cwd:         (() => { try { return process.cwd(); } catch { return null; } })(),
      machine:     machineHost,
      started_at:  new Date(_startMs).toISOString(),
      generated_at: new Date(now).toISOString(),
      duration_ms: now - _startMs,
      cli_version: CLI_VERSION,
      free_mode:   FREE_MODE,
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
        redacted:      redacted,
        blocked:       blocked,
        est_spend_usd: FREE_MODE ? null : Number(spentUsd.toFixed(6)),
      },
      residual: {
        note: "App plane covers fetch + Node http/https. Host Sight covers host egress observe. curl/raw sockets without Host Sight still dark until PE.",
        upgrade_gate: "https://vantio.ai/gate",
        upgrade_enterprise: "https://vantio.ai/enterprise",
      },
    };
    const safeid   = RUN_TRACE_ID.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
    const logPath  = join(runsDir, `${safeid}.json`);
    writeFileSync(logPath, JSON.stringify(log, null, 2) + "\n", { mode: 0o600 });
  } catch {
    // Non-fatal — never let log writing affect the exiting agent.
  }

  if (!SUMMARY && !FREE_MODE) return;

  const durationS  = ((now - _startMs) / 1000).toFixed(1);

  const lines = [
    "",
    `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.bold}Run Summary${c.reset}`,
    `  LLM calls:    ${c.yellow}${_calls.length}${c.reset}`,
    `  Hosts:        ${c.cyan}${hosts.join(", ")}${c.reset}`,
    `  Total bytes:  ${totalBytes > 0 ? totalBytes.toLocaleString() : "unknown"}`,
    `  Duration:     ${durationS}s`,
  ];
  if (!FREE_MODE) {
    lines.push(`  Redacted:     ${redacted > 0 ? c.green : ""}${redacted}${c.reset}`);
    lines.push(`  Blocked:      ${blocked > 0 ? c.red : ""}${blocked}${c.reset}`);
    lines.push(`  Est. spend:   $${spentUsd.toFixed(4)}`);
    lines.push(
      cloudSyncActive
        ? `  ${c.dim}→ Events routed to your Vantio dashboard.${c.reset}`
        : (LOCAL_GATE
            ? `  ${c.dim}→ Local Gate — events stay on this control plane (${INGEST_URL}).${c.reset}`
            : `  ${c.dim}→ Free plan — observed locally only. Upgrade at vantio.ai/pricing to sync your dashboard.${c.reset}`)
    );
  } else {
    lines.push(`  ${c.dim}→ Run \`vantio prove\` to export an auditor-ready artifact from this run.${c.reset}`);
    lines.push(
      LOCAL_GATE
        ? `  ${c.dim}→ Local Gate control plane detected — set VANTIO_API_KEY=soak-pro for enforce on this box.${c.reset}`
        : `  ${c.dim}→ Optics observes only — upgrade to Vantio Gate (Pro) to enforce policy.${c.reset}`
    );
    if (!telemetryDisabled()) {
      lines.push(`  ${c.dim}Anonymous usage telemetry helps improve Vantio. Opt out with VANTIO_TELEMETRY_DISABLED=1.${c.reset}`);
    }
  }
  lines.push("");
  process.stderr.write(lines.join("\n"));
});
