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
let policy = {
  enforce:           false,
  redact_pii:        false,
  pii_types:         ["ssn", "email", "credit_card", "phone"],
  allowed_hosts:     [],      // empty = all LLM hosts allowed
  blocked_hosts:     [],
  max_request_bytes: 0,       // 0 = no limit
  spend_cap_usd:     0,       // 0 = no cap
};

// ── PII detection patterns ───────────────────────────────────────────────────
const PII_PATTERNS = {
  ssn:         { re: /\b\d{3}-\d{2}-\d{4}\b/g,                                label: "SSN" },
  email:       { re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,   label: "EMAIL" },
  credit_card: { re: /\b(?:\d[ -]?){13,16}\b/g,                              label: "CC" },
  phone:       { re: /\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,             label: "PHONE" },
};

// Rough cost estimate: ~4 chars/token, blended $5 / 1M tokens.
const USD_PER_CHAR = (5 / 1_000_000) / 4;

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
        policy = { ...policy, ...data.policy };
        log(`${c.dim}[ ∅ VANTIO ]${c.reset} Policy loaded — enforce=${policy.enforce}, redact=${policy.redact_pii}`);
      }
    }
  } catch {
    // Policy fetch failed — fail open (observe only). Never block the agent
    // because our control plane is unreachable.
  }
})();

// ── Redaction ─────────────────────────────────────────────────────────────────
function redactBody(text) {
  if (typeof text !== "string" || !policy.redact_pii) return { text, redactions: [] };
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

globalThis.fetch = async function vantioFetch(input, init) {
  let hostname;
  try {
    const url = typeof input === "string" ? input
      : input instanceof URL ? input.href : input.url;
    hostname = new URL(url).hostname;
  } catch {
    return _originalFetch.call(this, input, init);
  }

  // Not an LLM call — pass straight through.
  if (!LLM_HOSTS.has(hostname)) {
    return _originalFetch.call(this, input, init);
  }

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
  await policyReady;

  // 1. Host allow/block policy
  if (policy.enforce) {
    if (policy.blocked_hosts.includes(hostname) ||
        (policy.allowed_hosts.length > 0 && !policy.allowed_hosts.includes(hostname))) {
      _calls.push({ hostname, action: "BLOCKED_HOST" });
      log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — host not permitted by policy`);
      report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_HOST",
               timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
      return blockedResponse("host_not_permitted");
    }
  }

  // 2. Read + optionally redact the request body
  let redactions = [];
  let reqBytes = 0;
  if (init && typeof init.body === "string") {
    reqBytes = Buffer.byteLength(init.body);
    const r = redactBody(init.body);
    redactions = r.redactions;
    if (redactions.length > 0) {
      init = { ...init, body: r.text };
      reqBytes = Buffer.byteLength(r.text);
    }
  }

  // 3. Request size policy
  if (policy.enforce && policy.max_request_bytes > 0 && reqBytes > policy.max_request_bytes) {
    _calls.push({ hostname, action: "BLOCKED_SIZE" });
    log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — request ${reqBytes}B exceeds cap ${policy.max_request_bytes}B`);
    report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SIZE",
             timestamp_ns: Date.now() * 1e6, bytes_severed: reqBytes });
    return blockedResponse("request_too_large");
  }

  // 4. Spend cap policy
  if (policy.enforce && policy.spend_cap_usd > 0 && spentUsd >= policy.spend_cap_usd) {
    _calls.push({ hostname, action: "BLOCKED_SPEND" });
    log(`${c.red}[ ∅ VANTIO ] BLOCKED${c.reset} ${hostname} — spend cap $${policy.spend_cap_usd} reached`);
    report({ target_host: hostname, pid: process.pid, action_taken: "BLOCKED_SPEND",
             timestamp_ns: Date.now() * 1e6, bytes_severed: 0 });
    return blockedResponse("spend_cap_reached");
  }

  // 5. Make the (possibly redacted) call
  const response = await _originalFetch.call(this, input, init);
  const respBytes = parseInt(response.headers.get("content-length") || "0", 10) || 0;
  spentUsd += (reqBytes + respBytes) * USD_PER_CHAR;

  const action = redactions.length > 0 ? "REDACTED" : "ALLOWED";
  _calls.push({ hostname, bytes: respBytes, action, redactions: redactions.length });
  if (redactions.length > 0) {
    log(`${c.green}[ ∅ VANTIO ] REDACTED${c.reset} ${hostname} — stripped ${redactions.length} PII item(s): ${redactions.join(", ")}`);
  }
  report({ target_host: hostname, pid: process.pid, action_taken: action,
           timestamp_ns: Date.now() * 1e6, bytes_severed: respBytes });

  return response;
};

// ── Run summary ─────────────────────────────────────────────────────────────
process.on("exit", () => {
  if (_calls.length === 0) return;

  const hosts      = [...new Set(_calls.map((x) => x.hostname))];
  const redacted   = _calls.filter((x) => x.action === "REDACTED").length;
  const blocked    = _calls.filter((x) => String(x.action).startsWith("BLOCKED")).length;

  // ── Lane 1: anonymous, opt-out usage telemetry ──────────────────────────────
  // Fires for both free and paid runs but stays fully anonymous — only
  // hostnames + counts, never content/PII/keys. Guarded so it can never throw.
  try {
    sendTelemetry({
      event: "summary",
      hosts,
      callCount: _calls.length,
      redactedCount: redacted,
      blockedCount: blocked,
      cliVersion: CLI_VERSION,
    });
  } catch {
    // Telemetry must never affect the agent or its exit.
  }

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
