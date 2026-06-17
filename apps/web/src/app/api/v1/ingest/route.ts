import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { sendTenantAnomalyAlert, type TenantAlertSettings } from "@/lib/alerts";

interface IngestPayload {
  traceId: string;
  eventPayload: unknown;
  auditMode: boolean;
}

// Coarse, allowlisted anomaly metadata — never request content. Mirrors the
// SDK-side enforcement fields.
interface AnomalyMetadata {
  bytes_severed: number | null;
  pid:           number | null;
  timestamp_ns:  number | null;
  target_host:   string | null;
  action_taken:  string | null;
}

// Gate alerts to ACTUAL policy violations. The SDK records action_taken as one
// of OBSERVED | ALLOWED | REDACTED | BLOCKED_HOST | BLOCKED_SIZE | BLOCKED_SPEND
// (or POLICY_VIOLATION). Only the blocking/violation actions should alert —
// never OBSERVED / ALLOWED / REDACTED.
function isViolationAction(action: string | null): boolean {
  if (!action) return false;
  const a = action.toUpperCase();
  return a.startsWith("BLOCKED") || a === "POLICY_VIOLATION";
}

function parsePayload(raw: unknown): IngestPayload | null {
  if (typeof raw !== "object" || raw === null) return null;
  const body = raw as Record<string, unknown>;
  if (typeof body["traceId"] !== "string" || body["traceId"].length === 0) return null;
  if (typeof body["auditMode"] !== "boolean") return null;
  return {
    traceId: body["traceId"],
    eventPayload: body["eventPayload"] ?? null,
    auditMode: body["auditMode"],
  };
}

/** HMAC-SHA256 of traceId keyed by the tenant's API key — forms the cryptographic receipt. */
async function computeHmac(apiKey: string, traceId: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(apiKey), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig  = await crypto.subtle.sign("HMAC", key, enc.encode(traceId));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

// Edge-compatible rate limiter — 100 writes per minute per API key.
// Checked BEFORE any Supabase query so a flood never touches the DB pool.
function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(100, "1 m"),
    analytics: false,
    prefix:    "vantio:ingest",
  });
}

export const runtime = "edge";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const identity = request.headers.get("x-vantio-identity")?.trim();
  if (!identity) {
    return NextResponse.json(
      { error: "Unauthenticated.", message: "x-vantio-identity header is required." },
      { status: 401 }
    );
  }

  // ── Rate limit (edge, before DB) ─────────────────────────────────────────
  const limiter = getRatelimiter();
  if (limiter) {
    const { success, limit, remaining, reset } = await limiter.limit(identity);
    if (!success) {
      return NextResponse.json(
        { error: "Rate limit exceeded. Max 100 requests per minute per API key." },
        {
          status: 429,
          headers: {
            "X-RateLimit-Limit":     String(limit),
            "X-RateLimit-Remaining": String(remaining),
            "X-RateLimit-Reset":     String(reset),
            "Retry-After":           "60",
          },
        }
      );
    }
  }

  // ── Validate API key against tenants table ────────────────────────────────
  let tenantEmail: string;
  let tenantSettings: TenantAlertSettings;
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("tenants")
      .select("email, tier, alert_slack_webhook_url, alert_email, alerts_enabled")
      .eq("api_key", identity)
      .single();

    if (error || !data) {
      return NextResponse.json({ error: "Invalid API key." }, { status: 401 });
    }

    const tenant = data as {
      email: string;
      tier: string;
      alert_slack_webhook_url: string | null;
      alert_email: string | null;
      alerts_enabled: boolean | null;
    };
    if (tenant.tier !== "PRO" && tenant.tier !== "ENTERPRISE") {
      return NextResponse.json(
        { error: "Ingest requires an active PRO or Enterprise subscription." },
        { status: 403 }
      );
    }

    tenantEmail = tenant.email;
    tenantSettings = {
      alert_slack_webhook_url: tenant.alert_slack_webhook_url,
      alert_email:             tenant.alert_email,
      alerts_enabled:          tenant.alerts_enabled,
    };
  } catch {
    return NextResponse.json({ error: "Failed to validate identity." }, { status: 500 });
  }

  // ── Parse and validate body ───────────────────────────────────────────────
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid request body. Expected a JSON object." },
      { status: 400 }
    );
  }

  const payload = parsePayload(rawBody);
  if (!payload) {
    return NextResponse.json(
      {
        error: "Malformed payload.",
        message: "Required: traceId (non-empty string), auditMode (boolean).",
      },
      { status: 422 }
    );
  }

  // ── Payload Quarantine ────────────────────────────────────────────────────
  const buildAnomalyMetadata = (p: IngestPayload): AnomalyMetadata => {
    const raw =
      typeof p.eventPayload === "object" && p.eventPayload !== null
        ? (p.eventPayload as Record<string, unknown>)
        : {};
    return {
      bytes_severed: typeof raw["bytes_severed"] === "number" ? raw["bytes_severed"] : null,
      pid:           typeof raw["pid"]           === "number" ? raw["pid"]           : null,
      timestamp_ns:  typeof raw["timestamp_ns"]  === "number" ? raw["timestamp_ns"]  : null,
      target_host:   typeof raw["target_host"]   === "string" ? raw["target_host"]   : null,
      // action_taken is stored verbatim as a string. The SDK-side enforcement
      // values — "OBSERVED" | "ALLOWED" | "REDACTED" | "BLOCKED_HOST" |
      // "BLOCKED_SIZE" | "BLOCKED_SPEND" — therefore persist as-is with no
      // change needed here. Still metadata only: never the request content.
      action_taken:  typeof raw["action_taken"]  === "string" ? raw["action_taken"]  : null,
    };
  };

  // Build the metadata + timestamp once so the persisted row and any alert
  // describe exactly the same event.
  const metadata  = buildAnomalyMetadata(payload);
  const createdAt = new Date().toISOString();

  const writeToSupabase = async (): Promise<boolean> => {
    try {
      const supabase = getSupabaseAdmin();
      const { error } = await supabase.from("anomaly_events").insert({
        tenant_identity: tenantEmail,
        trace_id:        payload.traceId,
        anomaly_metadata: metadata,
        audit_mode:      payload.auditMode,
        created_at:      createdAt,
      });
      if (error) {
        console.error("[vantio:ingest] Supabase write failed:", error.message, error);
        return false;
      }
      return true;
    } catch (err) {
      console.error("[vantio:ingest] Supabase write failed:", err);
      return false;
    }
  };

  // Run the Supabase write and HMAC computation concurrently.
  // Both must complete before we return — in Edge runtime a fire-and-forget
  // void promise is killed the moment the response is dispatched.
  const [hmacSig, writeOk] = await Promise.all([
    computeHmac(identity, payload.traceId),
    writeToSupabase(),
  ]);

  // Fire the per-tenant alert inline the instant a real policy VIOLATION is
  // recorded — no Supabase DB webhook required. Only BLOCKED_* / POLICY_VIOLATION
  // events alert; OBSERVED / ALLOWED / REDACTED never do. Awaited (bounded by the
  // helper's 3s timeouts) but fully failure-safe: any problem is caught + logged
  // so ingest still returns its normal 200 + HMAC signature.
  if (writeOk && isViolationAction(metadata.action_taken)) {
    try {
      await sendTenantAnomalyAlert(tenantSettings, {
        tenant_identity:  tenantEmail,
        trace_id:         payload.traceId,
        audit_mode:       payload.auditMode,
        created_at:       createdAt,
        anomaly_metadata: metadata,
      });
    } catch (err) {
      console.error("[vantio:ingest] alert send failed:", err);
    }
  }

  return NextResponse.json(
    { status: 0, traceId: payload.traceId },
    { status: 200, headers: { "x-vantio-signature": hmacSig } }
  );
}
