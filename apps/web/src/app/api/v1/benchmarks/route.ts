import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";
import { computeBenchmarks } from "@/lib/benchmarks";

// GET /api/v1/benchmarks — Lane 2: authenticated via x-vantio-identity.
// Returns cross-tenant ANONYMIZED aggregates over anomaly_events. No tenant
// identifiers are exposed; peer figures are suppressed (null) when data is
// sparse. See lib/benchmarks for the aggregation + k-anonymity rules.

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(30, "1 m"),
    analytics: false,
    prefix:    "vantio:benchmarks",
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
    const { success } = await limiter.limit(identity);
    if (!success) {
      return NextResponse.json(
        { error: "Rate limit exceeded. Max 30 requests per minute per API key." },
        { status: 429, headers: { "Retry-After": "60" } }
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
        { error: "Benchmarks require an active PRO or Enterprise subscription." },
        { status: 403 }
      );
    }
    tenantEmail = tenant.email;
  } catch {
    return NextResponse.json({ error: "Failed to validate identity." }, { status: 500 });
  }

  // ── Compute anonymized aggregates ─────────────────────────────────────────
  try {
    const supabase   = getSupabaseAdmin();
    const benchmarks = await computeBenchmarks(supabase, tenantEmail);
    return NextResponse.json({ benchmarks }, { status: 200 });
  } catch {
    return NextResponse.json({ error: "Failed to compute benchmarks." }, { status: 500 });
  }
}
