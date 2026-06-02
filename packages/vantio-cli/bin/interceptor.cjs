// [ ∅ VANTIO ] Zero-Line Enforcement Interceptor
// Injected at runtime by `vantio run node agent.js` via Node --require.
// Patches globalThis.fetch to observe (Tier 1) and enforce (Tier 2) outbound
// LLM calls. The developer writes zero code — the CLI handles everything.
//
//   Tier 1 (no API key):  observe + print to terminal
//   Tier 2 (API key):     fetch cloud policy, then redact / cap / block / report

"use strict";

const { randomUUID } = require("node:crypto");

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

const LLM_HOSTS = new Set([
  "api.openai.com",
  "api.anthropic.com",
  "generativelanguage.googleapis.com",
  "api.cohere.ai",
  "api.mistral.ai",
  "api.groq.com",
  "api.together.xyz",
  "api.perplexity.ai",
  "inference.ai.azure.com",
]);

// ── Default policy (fail-open until cloud policy loads) ──────────────────────
const DEFAULT_POLICY = {
  enforce:           false,
  redact_pii:        false,
  pii_types:         ["ssn", "email", "credit_card", "phone"],
  allowed_hosts:     [],      // empty = all in-scope hosts allowed
  blocked_hosts:     [],
  max_request_bytes: 0,       // 0 = no limit
  spend_cap_usd:     0,       // 0 = no cap
};

let policy = { ...DEFAULT_POLICY };

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
        log(`${c.dim}[ ∅ VANTIO ]${c.reset} Policy loaded — enforce=${policy.enforce}, redact=${policy.redact_pii}`);
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

// Redact a concrete request body value, preserving its original type.
// Returns { value, bytes, redactions, replaced, unscanned }:
//   - string / URLSearchParams / Uint8Array / Buffer / ArrayBuffer → decoded to
//     text, redacted, and re-encoded to the same type. `replaced` is true when
//     any redaction happened (so the caller knows to swap the body).
//   - ReadableStream / FormData / Blob → not scanned; `unscanned` is its label.
// Never throws — on any unexpected shape it returns the body unchanged.
function redactRequestBody(body) {
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
  if (FREE_MODE || !INGEST_URL) return;
  void _originalFetch.call(globalThis, `${INGEST_URL}/api/v1/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-vantio-identity": API_KEY },
    body: JSON.stringify({
      traceId:   process.env.VANTIO_TRACE_ID ?? randomUUID(),
      auditMode: AUDIT_MODE,
      eventPayload: metadata,
    }),
    signal: AbortSignal.timeout(5000),
  }).catch(() => {});
}

// ── Host scope ────────────────────────────────────────────────────────────────
// A host is "in scope" for enforcement when it is a known LLM host OR is named
// in the policy (blocked_hosts ∪ allowed_hosts). Hosts outside this set are
// passed straight through untouched — we never block, redact, or meter general
// (OS / package-manager / unrelated) traffic merely because a policy exists.
function inScope(hostname) {
  return (
    LLM_HOSTS.has(hostname) ||
    policy.blocked_hosts.includes(hostname) ||
    policy.allowed_hosts.includes(hostname)
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
async function enforceRequest(hostname, input, init) {
  // 1. Host allow/block policy. blocked_hosts blocks ANY in-scope host; a
  //    non-empty allow-list blocks any in-scope host not on it. (Out-of-scope
  //    hosts never reach here — they pass through before enforcement.)
  if (policy.enforce) {
    if (policy.blocked_hosts.includes(hostname)) return blockHost(hostname);
    if (policy.allowed_hosts.length > 0 && !policy.allowed_hosts.includes(hostname)) {
      return blockHost(hostname);
    }
  }

  // 2. Read + optionally redact the request body (any body type or location).
  let redactions = [];
  let reqBytes = 0;
  let newInput = input;
  let newInit = init;

  if (init && init.body != null) {
    const r = redactRequestBody(init.body);
    reqBytes = r.bytes;
    redactions = r.redactions;
    if (r.unscanned) {
      log(`${c.dim}[ ∅ VANTIO ] ${hostname} — ${r.unscanned} request body not scanned for PII (passed through)${c.reset}`);
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
    }
  }

  // 3. Request size policy
  if (policy.enforce && policy.max_request_bytes > 0 && reqBytes > policy.max_request_bytes) {
    return blockSize(hostname, reqBytes);
  }

  // 4. Spend cap policy
  if (policy.enforce && policy.spend_cap_usd > 0 && spentUsd >= policy.spend_cap_usd) {
    return blockSpend(hostname);
  }

  return { blocked: false, input: newInput, init: newInit, reqBytes, redactions };
}

globalThis.fetch = async function vantioFetch(input, init) {
  let hostname;
  try {
    const url = typeof input === "string" ? input
      : input instanceof URL ? input.href
      : (typeof Request !== "undefined" && input instanceof Request) ? input.url
      : input.url;
    hostname = new URL(url).hostname;
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
  if (!inScope(hostname)) {
    return _originalFetch.call(this, input, init);
  }

  // Anonymous, opt-out, once-per-process usage ping (fire-and-forget).
  sendRunTelemetryOnce(hostname);

  // ── FREE TIER — observe only ────────────────────────────────────────────────
  if (FREE_MODE) {
    const response = await _originalFetch.call(this, input, init);
    const bytes = parseInt(response.headers.get("content-length") || "0", 10) || null;
    const ts = new Date().toISOString();
    _calls.push({ hostname, bytes, ts, action: "OBSERVED" });
    log([
      "",
      `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.yellow}Outbound LLM call intercepted${c.reset}`,
      `  host:    ${c.cyan}${hostname}${c.reset}`,
      `  pid:     ${process.pid}`,
      `  bytes:   ${bytes != null ? bytes.toLocaleString() : "unknown"}`,
      `  time:    ${ts}`,
      `  ${c.dim}→ Set VANTIO_API_KEY to enforce policy and route to your dashboard.${c.reset}`,
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
  const response = await _originalFetch.call(this, plan.input, plan.init);

  // Post-call accounting + reporting — guarded so a metering error never
  // surfaces to the agent, which already holds a valid response.
  try {
    const action = plan.redactions.length > 0 ? "REDACTED" : "ALLOWED";
    const callRec = { hostname, bytes: 0, action, redactions: plan.redactions.length };
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
    report({ target_host: hostname, pid: process.pid, action_taken: action,
             timestamp_ns: Date.now() * 1e6, bytes_severed: callRec.bytes });
  } catch {
    // Accounting/reporting must never break the agent's call.
  }

  return response;
};

// ── Run summary ─────────────────────────────────────────────────────────────
process.on("exit", () => {
  if (_calls.length === 0) return;

  const hosts      = [...new Set(_calls.map((x) => x.hostname))];
  const redacted   = _calls.filter((x) => x.action === "REDACTED").length;
  const blocked    = _calls.filter((x) => String(x.action).startsWith("BLOCKED")).length;

  // NOTE: anonymous Lane 1 usage telemetry is NOT sent here. A fetch scheduled
  // inside a process "exit" handler never flushes (the event loop is already
  // draining), so the ping is emitted once on the first intercepted call via
  // sendRunTelemetryOnce() instead. This handler only prints the local summary.

  if (!SUMMARY && !FREE_MODE) return;

  const durationS  = ((Date.now() - _startMs) / 1000).toFixed(1);
  const totalBytes = _calls.reduce((a, x) => a + (x.bytes || 0), 0);

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
    lines.push(`  ${c.dim}→ Events routed to your Vantio dashboard.${c.reset}`);
  } else {
    lines.push(`  ${c.dim}→ Upgrade at vantio.ai to enforce policy and persist events.${c.reset}`);
    if (!telemetryDisabled()) {
      lines.push(`  ${c.dim}Anonymous usage telemetry helps improve Vantio. Opt out with VANTIO_TELEMETRY_DISABLED=1.${c.reset}`);
    }
  }
  lines.push("");
  process.stderr.write(lines.join("\n"));
});
