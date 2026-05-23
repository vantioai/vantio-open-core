import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

interface IngestPayload {
  traceId: string;
  eventPayload: unknown;
  auditMode: boolean;
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
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("tenants")
      .select("email, tier")
      .eq("api_key", identity)
      .single();

    if (error || !data) {
      return NextResponse.json({ error: "Invalid API key." }, { status: 401 });
    }

    const tenant = data as { email: string; tier: string };
    if (tenant.tier !== "PRO" && tenant.tier !== "ENTERPRISE") {
      return NextResponse.json(
        { error: "Ingest requires an active PRO or Enterprise subscription." },
        { status: 403 }
      );
    }

    tenantEmail = tenant.email;
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
  const buildAnomalyMetadata = (p: IngestPayload): Record<string, unknown> => {
    const raw =
      typeof p.eventPayload === "object" && p.eventPayload !== null
        ? (p.eventPayload as Record<string, unknown>)
        : {};
    return {
      bytes_severed: typeof raw["bytes_severed"] === "number" ? raw["bytes_severed"] : null,
      pid:           typeof raw["pid"]           === "number" ? raw["pid"]           : null,
      timestamp_ns:  typeof raw["timestamp_ns"]  === "number" ? raw["timestamp_ns"]  : null,
      target_host:   typeof raw["target_host"]   === "string" ? raw["target_host"]   : null,
      action_taken:  typeof raw["action_taken"]  === "string" ? raw["action_taken"]  : null,
    };
  };

  const writeToSupabase = async () => {
    try {
      const supabase = getSupabaseAdmin();
      await supabase.from("anomaly_events").insert({
        tenant_identity: tenantEmail,
        trace_id:        payload.traceId,
        anomaly_metadata: buildAnomalyMetadata(payload),
        audit_mode:      payload.auditMode,
        created_at:      new Date().toISOString(),
      });
    } catch (err) {
      console.error("[vantio:ingest] Supabase write failed:", err);
    }
  };

  void writeToSupabase();

  return NextResponse.json({ status: 0, traceId: payload.traceId }, { status: 200 });
}
