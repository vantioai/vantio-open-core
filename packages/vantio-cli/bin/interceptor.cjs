// [ ∅ VANTIO ] Zero-Line Auto-Interceptor
// Injected at runtime by `vantio run node agent.js` via Node --require.
// Patches globalThis.fetch to auto-trace outbound LLM API calls.
// The developer writes zero code — the CLI handles everything.

"use strict";

const INGEST_URL = process.env.VANTIO_INGEST_URL;
const API_KEY    = process.env.VANTIO_API_KEY;
const AUDIT_MODE = process.env.VANTIO_AUDIT_MODE === "1";

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

// Only activate if the customer has set their API key.
if (!INGEST_URL || !API_KEY) {
  // Silent — no credentials, no-op.
  return;
}

const _originalFetch = globalThis.fetch;

if (typeof _originalFetch !== "function") {
  // Node < 18 or environment without native fetch — skip.
  return;
}

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

      // Fire-and-forget — never await, never block the agent.
      void _originalFetch(`${INGEST_URL}/api/v1/ingest`, {
        method: "POST",
        headers: {
          "Content-Type":      "application/json",
          "x-vantio-identity": API_KEY,
        },
        body: JSON.stringify({
          traceId:      crypto.randomUUID(),
          auditMode:    AUDIT_MODE,
          eventPayload: {
            target_host:   hostname,
            pid:           process.pid,
            timestamp_ns:  Date.now() * 1_000_000,
            bytes_severed: contentLength ? parseInt(contentLength, 10) : null,
            action_taken:  "POLICY_VIOLATION",
          },
        }),
      }).catch(() => {
        // Non-fatal — telemetry failures must never crash the agent.
      });
    }
  } catch {
    // Defensive catch — never surface interceptor errors to the agent.
  }

  return response;
};
