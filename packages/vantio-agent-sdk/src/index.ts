import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

export interface VantioContext {
  readonly traceId: string;
}

/**
 * Options for `withVantio()` / `shield()`.
 * Controls only trace ID generation — cloud ingest options (ingestUrl, identity)
 * belong on `reportAnomaly()` where they are actually used.
 */
export interface WithVantioOptions {
  traceId?: string;
}

export interface VantioEventPayload {
  bytes_severed?: number;
  pid?: number;
  timestamp_ns?: number;
  target_host?: string;
  action_taken?: VantioActionTaken;
}

/**
 * The action Vantio took for a single intercepted outbound LLM call.
 * Mirrors the `action_taken` field in the /api/v1/ingest contract and the
 * enforcement engine in the CLI interceptor.
 *
 * DRY_RUN_* variants are emitted when dry_run=true in the policy — the
 * enforcement decision was made but the call was allowed through. Use these
 * to validate a policy before enabling hard enforcement.
 *
 * ENFORCEMENT_GAP is emitted when the interceptor could not apply a policy
 * (e.g. streaming body that cannot be scanned for PII). These events feed
 * the /api/v1/residual-risk endpoint and surface the Pro→Enterprise upgrade path.
 */
export type VantioActionTaken =
  | "OBSERVED"
  | "ALLOWED"
  | "REDACTED"
  | "BLOCKED_HOST"
  | "BLOCKED_SIZE"
  | "BLOCKED_SPEND"
  | "ENFORCEMENT_GAP"
  | "DRY_RUN_BLOCKED_HOST"
  | "DRY_RUN_BLOCKED_SIZE"
  | "DRY_RUN_BLOCKED_SPEND";

/**
 * Cloud-managed policy returned by GET /api/v1/config (Tier 2).
 * Enforcement runs locally in the SDK/CLI — this is the policy that drives it.
 */
export interface VantioPolicy {
  /** Master switch — when false, calls are observed but never blocked/redacted. */
  enforce: boolean;
  /** When true, request bodies are scanned and matching PII is redacted. */
  redact_pii: boolean;
  /** Which PII categories to redact (e.g. "ssn", "email", "credit_card", "phone"). */
  pii_types: string[];
  /** Allow-list of LLM hostnames; empty means all known LLM hosts are allowed. */
  allowed_hosts: string[];
  /** Deny-list of LLM hostnames; always blocked when enforce is true. */
  blocked_hosts: string[];
  /** Hard cap on outbound request size in bytes; 0 means no limit. */
  max_request_bytes: number;
  /** Soft USD spend cap for the run; 0 means no cap. */
  spend_cap_usd: number;
  /**
   * When true, enforcement decisions are logged and reported as DRY_RUN_* events
   * but requests are NOT blocked. Use this to validate a policy against live traffic
   * before enabling hard enforcement. Has no effect when enforce=false.
   */
  dry_run: boolean;
}

/**
 * Permissive, fail-open default policy. Used until a cloud policy loads and
 * returned by fetchPolicy() on any error so an unreachable control plane can
 * never block the agent.
 */
export const DEFAULT_POLICY: VantioPolicy = {
  enforce: false,
  redact_pii: false,
  pii_types: ["ssn", "email", "credit_card", "phone"],
  allowed_hosts: [],
  blocked_hosts: [],
  max_request_bytes: 0,
  spend_cap_usd: 0,
  dry_run: false,
};

/** Coerce to boolean, falling back to a default for non-boolean input. */
function asBool(value: unknown, dflt: boolean): boolean {
  return typeof value === "boolean" ? value : dflt;
}

/** Coerce to an array of strings, dropping non-string entries. */
function asStringArray(value: unknown, dflt: string[]): string[] {
  if (!Array.isArray(value)) return [...dflt];
  return value.filter((v): v is string => typeof v === "string");
}

/** Coerce to a finite number ≥ 0, falling back to a default otherwise. */
function asNonNegativeNumber(value: unknown, dflt: number): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) && n >= 0 ? n : dflt;
}

/**
 * Validate and normalize an untrusted policy object into a well-typed
 * VantioPolicy. A malformed cloud policy (null fields, wrong types) is coerced
 * to safe defaults instead of being trusted verbatim — this is what keeps
 * downstream enforcement (`.includes`, `for..of`, numeric comparisons) from
 * throwing on bad input.
 */
export function normalizePolicy(raw: unknown): VantioPolicy {
  const p = (raw && typeof raw === "object" ? raw : {}) as Partial<VantioPolicy>;
  return {
    enforce: asBool(p.enforce, DEFAULT_POLICY.enforce),
    redact_pii: asBool(p.redact_pii, DEFAULT_POLICY.redact_pii),
    pii_types: asStringArray(p.pii_types, DEFAULT_POLICY.pii_types),
    allowed_hosts: asStringArray(p.allowed_hosts, DEFAULT_POLICY.allowed_hosts),
    blocked_hosts: asStringArray(p.blocked_hosts, DEFAULT_POLICY.blocked_hosts),
    max_request_bytes: asNonNegativeNumber(p.max_request_bytes, DEFAULT_POLICY.max_request_bytes),
    spend_cap_usd: asNonNegativeNumber(p.spend_cap_usd, DEFAULT_POLICY.spend_cap_usd),
    dry_run: asBool(p.dry_run, DEFAULT_POLICY.dry_run),
  };
}

const _storage = new AsyncLocalStorage<VantioContext>();

/**
 * Wraps an async agent callback in a Vantio execution context.
 * Generates (or accepts) a VANTIO_TRACE_ID and propagates it through
 * the full async call-tree via AsyncLocalStorage.
 *
 * shield() is the canonical alias — use either name.
 */
export async function withVantio<T>(
  callback: () => Promise<T>,
  options: WithVantioOptions = {},
): Promise<T> {
  const traceId = options.traceId ?? randomUUID();
  const ctx: VantioContext = { traceId };
  return _storage.run(ctx, callback);
}

/** Canonical alias for withVantio — use whichever you prefer. */
export const shield = withVantio;

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
 *     ingestUrl: process.env.VANTIO_INGEST_URL,  // https://vantio.ai
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

  // Bypass the env gate when the caller explicitly supplied an ingestUrl —
  // the explicit opt-in is sufficient. Only fall back to the env gate when
  // ingestUrl comes from the environment (Tier 1 local mode guard).
  const callerSuppliedUrl = !!opts.ingestUrl;
  const cloudIngest =
    callerSuppliedUrl ||
    process.env["VANTIO_CLOUD_INGEST"] === "true" ||
    process.env["VANTIO_CLOUD_INGEST"] === "1";

  if (!cloudIngest) return; // Tier 1 local mode — cloud ingest not activated

  try {
    const res = await fetch(`${ingestUrl}/api/v1/ingest`, {
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
      // Bound the request so a stalled ingest endpoint never hangs the agent.
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      // Non-fatal but visible — silent 4xx/5xx made debugging impossible.
      console.warn(`[vantio] ingest request returned HTTP ${res.status} (non-fatal)`);
    }
  } catch (err) {
    // Non-fatal — never crash the agent over telemetry failures.
    console.warn("[vantio] ingest request failed (non-fatal):", err);
  }
}

export interface FetchPolicyOptions {
  /** Base URL of the Vantio control plane. Defaults to VANTIO_INGEST_URL or https://vantio.ai. */
  ingestUrl?: string;
  /** Abort the request early. Overrides timeoutMs when provided. */
  signal?: AbortSignal;
  /** Request timeout in milliseconds (default 5000). */
  timeoutMs?: number;
}

/**
 * Optics does not fetch a policy and does not send VANTIO_API_KEY.
 *
 * This function warns and returns a permissive copy of DEFAULT_POLICY with
 * enforce and redact_pii false. Enforcement is provided by Phantom Engine.
 * The returned object is a fresh copy and safe to mutate.
 */
export async function fetchPolicy(
  apiKey: string,
  opts: FetchPolicyOptions = {},
): Promise<VantioPolicy> {
  void apiKey;
  void opts;
  console.warn(
    "[vantio] fetchPolicy does not load a policy and does not send VANTIO_API_KEY. Enforcement is provided by Phantom Engine. Optics stays observational.",
  );
  return { ...DEFAULT_POLICY, enforce: false, redact_pii: false };
}

export interface RedactionResult {
  /** The input text with every matched PII span replaced by a label token. */
  text: string;
  /** The PII categories that were matched, one entry per redacted span. */
  redactions: string[];
}

/**
 * Optics does not rewrite request text.
 *
 * This function warns and returns the original text with an empty redaction
 * list. Enforcement is provided by Phantom Engine.
 */
export function redactPII(
  text: string,
  piiTypes: string[] = ["ssn", "email", "credit_card", "phone"],
): RedactionResult {
  void piiTypes;
  console.warn(
    "[vantio] redactPII does not rewrite request text. Enforcement is provided by Phantom Engine.",
  );
  return { text, redactions: [] };
}

