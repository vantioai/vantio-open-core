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
 */
export type VantioActionTaken =
  | "OBSERVED"
  | "ALLOWED"
  | "REDACTED"
  | "BLOCKED_HOST"
  | "BLOCKED_SIZE"
  | "BLOCKED_SPEND";

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
 * Fetches the cloud-managed policy from GET /api/v1/config (Tier 2).
 *
 * Fails open: on any error — network failure, non-2xx status, malformed body,
 * or timeout — a permissive copy of DEFAULT_POLICY is returned so an
 * unreachable control plane can never block the agent. The returned object is
 * always a fresh copy and safe to mutate.
 *
 * @example
 * ```ts
 * const policy = await fetchPolicy(process.env.VANTIO_API_KEY!);
 * if (policy.enforce && policy.redact_pii) {
 *   const { text } = redactPII(requestBody, policy.pii_types);
 * }
 * ```
 */
export async function fetchPolicy(
  apiKey: string,
  opts: FetchPolicyOptions = {},
): Promise<VantioPolicy> {
  const ingestUrl =
    opts.ingestUrl ?? process.env["VANTIO_INGEST_URL"] ?? "https://vantio.ai";

  try {
    const res = await fetch(`${ingestUrl}/api/v1/config`, {
      method: "GET",
      headers: { "x-vantio-identity": apiKey },
      signal: opts.signal ?? AbortSignal.timeout(opts.timeoutMs ?? 5000),
    });
    if (!res.ok) return { ...DEFAULT_POLICY };
    const data: unknown = await res.json();
    if (
      data &&
      typeof data === "object" &&
      "policy" in data &&
      (data as { policy?: unknown }).policy &&
      typeof (data as { policy: unknown }).policy === "object"
    ) {
      // Validate the shape rather than trusting it — a malformed policy
      // (null/array/number where a different type is expected) must never
      // produce an object that throws when enforcement reads it.
      return normalizePolicy((data as { policy: unknown }).policy);
    }
    return { ...DEFAULT_POLICY };
  } catch {
    // Fail open — never block the agent because our control plane is unreachable
    // or returns an unparseable / malformed body.
    return { ...DEFAULT_POLICY };
  }
}

/** PII detection patterns — kept identical to the CLI interceptor. */
const PII_PATTERNS: Record<string, { re: RegExp; label: string }> = {
  ssn:         { re: /\b\d{3}-\d{2}-\d{4}\b/g,                                label: "SSN" },
  email:       { re: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g,   label: "EMAIL" },
  credit_card: { re: /\b(?:\d[ -]?){13,16}\b/g,                              label: "CC" },
  phone:       { re: /\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g,             label: "PHONE" },
};

export interface RedactionResult {
  /** The input text with every matched PII span replaced by a label token. */
  text: string;
  /** The PII categories that were matched, one entry per redacted span. */
  redactions: string[];
}

/**
 * Pure, side-effect-free PII redactor. Replaces matches with
 * `[VANTIO_REDACTED:LABEL]` using the same patterns and labels as the CLI
 * interceptor (ssn → SSN, email → EMAIL, credit_card → CC, phone → PHONE).
 *
 * This runs entirely locally — no content ever leaves the process — and is the
 * building block for SDK-side Tier 2 enforcement.
 *
 * @example
 * ```ts
 * const { text, redactions } = redactPII("ssn 123-45-6789");
 * // text       → "ssn [VANTIO_REDACTED:SSN]"
 * // redactions → ["ssn"]
 * ```
 */
export function redactPII(
  text: string,
  piiTypes: string[] = ["ssn", "email", "credit_card", "phone"],
): RedactionResult {
  if (typeof text !== "string") return { text, redactions: [] };
  let out = text;
  const redactions: string[] = [];
  for (const type of piiTypes) {
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

