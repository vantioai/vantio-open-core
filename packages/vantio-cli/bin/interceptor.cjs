// [ ∅ VANTIO ] Zero-Line Auto-Interceptor
// Injected at runtime by `vantio run node agent.js` via Node --require.
// Patches globalThis.fetch to auto-trace outbound LLM API calls.
// The developer writes zero code — the CLI handles everything.

"use strict";

// Use require() for crypto — globalThis.crypto is only available in Node 19+.
// We target Node >=18.3.0 so the module path is required.
const { randomUUID } = require("node:crypto");

// Only emit ANSI escape codes when stderr is an interactive terminal.
// Suppresses raw escape sequences in CI, Docker logs, and log aggregators.
const USE_COLOR = process.stderr.isTTY === true;
const c = {
  reset:  USE_COLOR ? "\x1b[0m"  : "",
  dim:    USE_COLOR ? "\x1b[2m"  : "",
  bold:   USE_COLOR ? "\x1b[1m"  : "",
  yellow: USE_COLOR ? "\x1b[33m" : "",
  cyan:   USE_COLOR ? "\x1b[36m" : "",
};

const INGEST_URL  = process.env.VANTIO_INGEST_URL;
const API_KEY     = process.env.VANTIO_API_KEY;
const AUDIT_MODE  = process.env.VANTIO_AUDIT_MODE === "1";
const SUMMARY     = process.env.VANTIO_SUMMARY    === "1";
const FREE_MODE   = !API_KEY;

// Well-known LLM API hostnames to intercept.
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

// In-memory call log for --summary output.
const _calls    = [];
const _startMs  = Date.now();

if (typeof globalThis.fetch !== "function") {
  // Node < 18 or environment without native fetch — skip silently.
  return;
}

const _originalFetch = globalThis.fetch;

globalThis.fetch = async function vantioFetch(input, init) {
  // Always call the original first — Vantio never blocks the agent.
  const response = await _originalFetch(input, init);

  try {
    const url =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;

    const hostname = new URL(url).hostname;

    if (LLM_HOSTS.has(hostname)) {
      const contentLength = response.headers.get("content-length");
      const bytesSevered  = contentLength ? parseInt(contentLength, 10) : null;
      const ts            = new Date().toISOString();

      _calls.push({ hostname, bytesSevered, ts });

      if (FREE_MODE) {
        // ── Free Tier: pretty-print to stderr ──────────────────────────────
        process.stderr.write(
          [
            "",
            `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.yellow}Outbound LLM call intercepted${c.reset}`,
            `  host:    ${c.cyan}${hostname}${c.reset}`,
            `  pid:     ${process.pid}`,
            `  bytes:   ${bytesSevered != null ? bytesSevered.toLocaleString() : "unknown"}`,
            `  time:    ${ts}`,
            `  ${c.dim}→ Set VANTIO_API_KEY to route events to your dashboard.${c.reset}`,
            "",
          ].join("\n")
        );
      } else if (INGEST_URL) {
        // ── Paid Tier: route to cloud ingest ───────────────────────────────
        void _originalFetch(`${INGEST_URL}/api/v1/ingest`, {
          method:  "POST",
          headers: {
            "Content-Type":      "application/json",
            "x-vantio-identity": API_KEY,
          },
          body: JSON.stringify({
            traceId:      process.env.VANTIO_TRACE_ID ?? randomUUID(),
            auditMode:    AUDIT_MODE,
            eventPayload: {
              target_host:   hostname,
              pid:           process.pid,
              timestamp_ns:  Date.now() * 1_000_000,
              bytes_severed: bytesSevered,
              action_taken:  "POLICY_VIOLATION",
            },
          }),
          // Bound the fire-and-forget POST so stalled sockets cannot accumulate.
          signal: AbortSignal.timeout(5000),
        }).catch(() => {});
      }
    }
  } catch {
    // Defensive catch — never surface interceptor errors to the agent.
  }

  return response;
};

// ── Run summary ─────────────────────────────────────────────────────────────
// Printed on process exit when VANTIO_SUMMARY=1 or any calls were detected
// in free mode (so developers always see what was intercepted).

process.on("exit", () => {
  if (_calls.length === 0) return;

  const durationS = ((Date.now() - _startMs) / 1_000).toFixed(1);
  const hosts     = [...new Set(_calls.map((c) => c.hostname))];
  const totalBytes = _calls.reduce((acc, c) => acc + (c.bytesSevered ?? 0), 0);

  if (!SUMMARY && !FREE_MODE) return;

  process.stderr.write(
    [
      "",
      `${c.dim}[ ∅ VANTIO ]${c.reset} ${c.bold}Run Summary${c.reset}`,
      `  LLM calls:    ${c.yellow}${_calls.length}${c.reset}`,
      `  Hosts:        ${c.cyan}${hosts.join(", ")}${c.reset}`,
      `  Total bytes:  ${totalBytes > 0 ? totalBytes.toLocaleString() : "unknown"}`,
      `  Duration:     ${durationS}s`,
      FREE_MODE
        ? `  ${c.dim}→ Upgrade at app.vantio.ai to persist events to your dashboard.${c.reset}`
        : `  ${c.dim}→ Events routed to your Vantio dashboard.${c.reset}`,
      "",
    ].join("\n")
  );
});
