// [ ∅ VANTIO ] Lane 1 — anonymous, opt-out usage telemetry.
//
// Sends ONLY anonymous, aggregate metadata: a random anonymous id, the
// runtime/os strings, an event name, the set of LLM hostnames contacted, and
// a few counts. It NEVER sends prompts, completions, API keys, emails, or any
// content/PII — that is the entire privacy contract. Fire-and-forget with a
// hard timeout so it can never block, slow, or crash the agent.
//
// Opt out: VANTIO_TELEMETRY_DISABLED=1  or  DO_NOT_TRACK=1

"use strict";

const os = require("node:os");
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");

const TELEMETRY_BASE = process.env.VANTIO_INGEST_URL || "https://vantio.ai";

// Fields explicitly allowed onto the wire. Anything not in this whitelist is
// never transmitted — a deliberate guard against accidentally leaking content.
function telemetryDisabled() {
  return (
    process.env.VANTIO_TELEMETRY_DISABLED === "1" ||
    process.env.DO_NOT_TRACK === "1"
  );
}

// Read (or lazily create) a persistent random anonymous id. On any FS failure
// we fall back to an ephemeral per-run id — this function never throws.
function getAnonymousId() {
  try {
    const dir = path.join(os.homedir(), ".vantio");
    const idFile = path.join(dir, "telemetry-id");
    try {
      const existing = fs.readFileSync(idFile, "utf8").trim();
      if (existing) return existing;
    } catch {
      // Not created yet — fall through and create it.
    }
    const id = randomUUID();
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(idFile, id + "\n", { mode: 0o600 });
    } catch {
      // Home dir not writable — use an ephemeral id for this run only.
    }
    return id;
  } catch {
    return randomUUID(); // Never throw.
  }
}

// Fire-and-forget. Returns immediately; the request is bounded by a 3s timeout
// and all errors are swallowed. Never prints, never blocks, never crashes.
function sendTelemetry(payload = {}) {
  try {
    if (telemetryDisabled()) return;
    if (typeof fetch !== "function") return; // Node < 18 — nothing to send with.

    const body = {
      anonymousId: getAnonymousId(),
      runtime: "node",
      runtimeVersion: process.version,
      os: process.platform,
      event: payload.event === "run" ? "run" : "summary",
      hosts: Array.isArray(payload.hosts)
        ? payload.hosts.slice(0, 50).map(String)
        : [],
      callCount: Number.isFinite(payload.callCount) ? payload.callCount : 0,
    };

    // Optional, still anonymous fields — added only when present.
    if (payload.sdkVersion != null) body.sdkVersion = String(payload.sdkVersion);
    if (payload.cliVersion != null) body.cliVersion = String(payload.cliVersion);
    if (Number.isFinite(payload.redactedCount)) body.redactedCount = payload.redactedCount;
    if (Number.isFinite(payload.blockedCount)) body.blockedCount = payload.blockedCount;
    if (payload.framework != null) body.framework = String(payload.framework);

    void fetch(`${TELEMETRY_BASE}/api/v1/telemetry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }, // No api key. No auth header.
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(3000),
    }).catch(() => {});
  } catch {
    // Telemetry must never affect the agent — swallow everything silently.
  }
}

module.exports = { sendTelemetry, telemetryDisabled };
