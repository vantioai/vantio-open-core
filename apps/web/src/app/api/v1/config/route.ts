import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { DEFAULT_POLICY, type TenantPolicy } from "@/lib/policy";

// GET /api/v1/config — the SDK/CLI polls this for its cloud-managed policy.
// Header: x-vantio-identity: <api_key>. Returns { policy }. The SDK performs
// the actual enforcement (redaction, spend caps, host blocking) client-side;
// this endpoint only hands it the rules. It must fail open: free / un-provisioned
// tenants always receive the permissive DEFAULT_POLICY so they are never broken.

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

// Edge-compatible rate limiter — config is polled, so cap per API key.
function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(120, "1 m"),
    analytics: false,
    prefix:    "vantio:config",
  });
}

export const runtime = "edge";

export async function GET(request: NextRequest): Promise<NextResponse> {
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
        { error: "Rate limit exceeded. Max 120 requests per minute per API key." },
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
  let tenantId: string;
  let tier: string;
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("tenants")
      .select("id, tier")
      .eq("api_key", identity)
      .single();

    if (error || !data) {
      return NextResponse.json({ error: "Invalid API key." }, { status: 401 });
    }

    const tenant = data as { id: string; tier: string };
    tenantId = tenant.id;
    tier     = tenant.tier;
  } catch {
    return NextResponse.json({ error: "Failed to validate identity." }, { status: 500 });
  }

  // Non-paid tiers: fail open with the permissive default so free users
  // running the SDK are never blocked or broken.
  if (tier !== "PRO" && tier !== "ENTERPRISE") {
    return NextResponse.json({ policy: DEFAULT_POLICY }, { status: 200 });
  }

  // ── Load the tenant's saved policy (or default if no row yet) ─────────────
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from("tenant_policies")
      .select("enforce, redact_pii, pii_types, allowed_hosts, blocked_hosts, max_request_bytes, spend_cap_usd")
      .eq("tenant_id", tenantId)
      .maybeSingle();

    if (error || !data) {
      return NextResponse.json({ policy: DEFAULT_POLICY }, { status: 200 });
    }

    const row = data as Record<string, unknown>;
    const policy: TenantPolicy = {
      enforce:           row["enforce"] === true,
      redact_pii:        row["redact_pii"] === true,
      pii_types:         Array.isArray(row["pii_types"])     ? (row["pii_types"]     as string[]) : [],
      allowed_hosts:     Array.isArray(row["allowed_hosts"]) ? (row["allowed_hosts"] as string[]) : [],
      blocked_hosts:     Array.isArray(row["blocked_hosts"]) ? (row["blocked_hosts"] as string[]) : [],
      max_request_bytes: typeof row["max_request_bytes"] === "number" ? row["max_request_bytes"] : Number(row["max_request_bytes"] ?? 0),
      spend_cap_usd:     typeof row["spend_cap_usd"]     === "number" ? row["spend_cap_usd"]     : Number(row["spend_cap_usd"] ?? 0),
    };

    return NextResponse.json({ policy }, { status: 200 });
  } catch {
    // On any read failure, still fail open with the default policy.
    return NextResponse.json({ policy: DEFAULT_POLICY }, { status: 200 });
  }
}
