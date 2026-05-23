import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

export interface VantioContext {
  readonly traceId: string;
}

export interface WithVantioOptions {
  traceId?: string;
  /**
   * When set, anomaly events are POSTed to this URL via /api/v1/ingest.
   * Typically your Vantio control plane URL, e.g. https://app.vantio.ai
   * Set VANTIO_CLOUD_INGEST=true to activate via the CLI supervisor.
   */
  ingestUrl?: string;
  /**
   * Identity header sent with every ingest request.
   * Defaults to the VANTIO_IDENTITY env var.
   */
  identity?: string;
}

export interface VantioEventPayload {
  bytes_severed?: number;
  pid?: number;
  timestamp_ns?: number;
  target_host?: string;
  action_taken?: string;
}

const _storage = new AsyncLocalStorage<VantioContext>();

/**
 * Wraps an async agent callback in a Vantio execution context.
 * Generates (or accepts) a VANTIO_TRACE_ID and propagates it through
 * the full async call-tree via AsyncLocalStorage.
 */
export async function withVantio<T>(
  callback: () => Promise<T>,
  options: WithVantioOptions = {},
): Promise<T> {
  const traceId = options.traceId ?? randomUUID();
  const ctx: VantioContext = { traceId };
  return _storage.run(ctx, callback);
}

/**
 * Returns the VANTIO_TRACE_ID for the current async execution context,
 * or undefined when called outside a withVantio frame.
 */
export function getCurrentTraceId(): string | undefined {
  return _storage.getStore()?.traceId;
}

/**
 * Returns the full VantioContext for the current async execution context.
 */
export function getCurrentContext(): VantioContext | undefined {
  return _storage.getStore();
}

/**
 * Sends an anomaly event to the Vantio ingest endpoint.
 * Call this from within a withVantio() frame after detecting a severance.
 *
 * @example
 * ```ts
 * await withVantio(async () => {
 *   // after ssl_write uprobe fires and logs to your ring buffer:
 *   await reportAnomaly({
 *     bytes_severed: 14382,
 *     pid: process.pid,
 *     target_host: "api.openai.com",
 *     action_taken: "SEVERED",
 *   }, {
 *     ingestUrl: process.env.VANTIO_INGEST_URL,
 *     identity: process.env.VANTIO_IDENTITY,
 *     auditMode: process.env.VANTIO_AUDIT_MODE === "1",
 *   });
 * });
 * ```
 */
export async function reportAnomaly(
  event: VantioEventPayload,
  opts: {
    ingestUrl?: string;
    identity?: string;
    auditMode?: boolean;
  } = {},
): Promise<void> {
  const traceId = getCurrentTraceId();
  if (!traceId) {
    console.warn("[vantio] reportAnomaly() called outside a withVantio() frame — skipping");
    return;
  }

  const ingestUrl =
    opts.ingestUrl ??
    process.env["VANTIO_INGEST_URL"];

  if (!ingestUrl) return; // local-only mode — no cloud ingest configured

  // VANTIO_API_KEY is the canonical env var; VANTIO_IDENTITY kept for back-compat.
  const identity =
    opts.identity ??
    process.env["VANTIO_API_KEY"] ??
    process.env["VANTIO_IDENTITY"] ??
    "unknown";

  const cloudIngest =
    process.env["VANTIO_CLOUD_INGEST"] === "true" ||
    process.env["VANTIO_CLOUD_INGEST"] === "1";

  if (!cloudIngest) return; // Tier 1 local mode — cloud ingest not activated

  try {
    await fetch(`${ingestUrl}/api/v1/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-vantio-identity": identity,
      },
      body: JSON.stringify({
        traceId,
        auditMode: opts.auditMode ?? false,
        eventPayload: event,
      }),
    });
  } catch (err) {
    // Non-fatal — never crash the agent over telemetry failures.
    console.warn("[vantio] ingest request failed (non-fatal):", err);
  }
}

