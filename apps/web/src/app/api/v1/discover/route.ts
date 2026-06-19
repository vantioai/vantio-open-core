import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// GET /api/v1/discover — Shadow AI attack surface discovery for `vantio discover`.
// Header: x-vantio-identity: <api_key>. PRO / ENTERPRISE only.
// Query params:
//   since — "24h" | "7d" | "30d"  (default "24h")
//   host  — optional exact hostname filter

type SinceWindow = "24h" | "7d" | "30d";

const SINCE_WINDOWS = new Set<string>(["24h", "7d", "30d"]);
const MAX_EVENTS = 10_000;

function parseSince(raw: string | null): SinceWindow {
  if (raw && SINCE_WINDOWS.has(raw)) return raw as SinceWindow;
  return "24h";
}

function cutoffFromSince(since: SinceWindow): Date {
  const now = Date.now();
  const offsets: Record<SinceWindow, number> = {
    "24h": 24 * 60 * 60 * 1000,
    "7d":  7  * 24 * 60 * 60 * 1000,
    "30d": 30 * 24 * 60 * 60 * 1000,
  };
  return new Date(now - offsets[since]);
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

// Edge-compatible rate limiter — 60 discover requests per minute per API key.
function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(60, "1 m"),
    analytics: false,
    prefix:    "vantio:discover",
  });
}

interface AnomalyRow {
  anomaly_metadata: {
    target_host:  string | null;
    action_taken: string | null;
  } | null;
  created_at: string;
}

interface HostStats {
  host:       string;
  total:      number;
  allowed:    number;
  redacted:   number;
  blocked:    number;
  observed:   number;
  first_seen: string;
  last_seen:  string;
}

// An event is "shadow AI / observed" when the SDK sent action_taken="OBSERVED",
// meaning traffic was seen by the network interceptor but had no policy enforcement
// trace (no SDK wrapper). These are the unmanaged calls that vantio discover exposes.
function isObserved(action: string | null): boolean {
  if (!action) return true;
  return action.toUpperCase() === "OBSERVED";
}

function isBlocked(action: string | null): boolean {
  if (!action) return false;
  const a = action.toUpperCase();
  return a.startsWith("BLOCKED") || a === "POLICY_VIOLATION";
}

function isRedacted(action: string | null): boolean {
  if (!action) return false;
  return action.toUpperCase() === "REDACTED";
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
        { error: "Rate limit exceeded. Max 60 requests per minute per API key." },
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
        { error: "Discover requires an active PRO or Enterprise subscription." },
        { status: 403 }
      );
    }

    tenantEmail = tenant.email;
  } catch {
    return NextResponse.json({ error: "Failed to validate identity." }, { status: 500 });
  }

  // ── Parse query params ────────────────────────────────────────────────────
  const { searchParams } = new URL(request.url);
  const since  = parseSince(searchParams.get("since"));
  const hostFilter = searchParams.get("host")?.trim() || null;
  const cutoff = cutoffFromSince(since);

  // ── Fetch anomaly events ──────────────────────────────────────────────────
  let rows: AnomalyRow[];
  try {
    const supabase = getSupabaseAdmin();
    let query = supabase
      .from("anomaly_events")
      .select("anomaly_metadata, created_at")
      .eq("tenant_identity", tenantEmail)
      .gte("created_at", cutoff.toISOString())
      .order("created_at", { ascending: false })
      .limit(MAX_EVENTS);

    if (hostFilter) {
      // Exact match on the target_host field inside the JSONB anomaly_metadata column.
      query = query.eq("anomaly_metadata->>target_host", hostFilter);
    }

    const { data, error } = await query;
    if (error) {
      console.error("[vantio:discover] Supabase query failed:", error.message);
      return NextResponse.json({ error: "Failed to query events." }, { status: 500 });
    }

    rows = (data ?? []) as AnomalyRow[];
  } catch {
    return NextResponse.json({ error: "Failed to query events." }, { status: 500 });
  }

  // ── Aggregate in application code (edge-compatible, no SQL grouping) ──────
  let totalCalls     = 0;
  let governedCalls  = 0;
  let shadowAiCalls  = 0;
  let blockedCalls   = 0;
  let redactedCalls  = 0;

  const hostMap = new Map<string, HostStats>();

  for (const row of rows) {
    const action = row.anomaly_metadata?.action_taken ?? null;
    const host   = row.anomaly_metadata?.target_host  ?? null;
    const ts     = row.created_at;

    totalCalls++;

    const observed = isObserved(action);
    const blocked  = isBlocked(action);
    const redacted = isRedacted(action);

    if (observed) {
      shadowAiCalls++;
    } else {
      // ALLOWED + REDACTED + BLOCKED all count as governed
      governedCalls++;
    }
    if (blocked)  blockedCalls++;
    if (redacted) redactedCalls++;

    // Only aggregate by host when we have one — unknown hosts are skipped.
    if (!host) continue;

    let entry = hostMap.get(host);
    if (!entry) {
      entry = {
        host,
        total:      0,
        allowed:    0,
        redacted:   0,
        blocked:    0,
        observed:   0,
        first_seen: ts,
        last_seen:  ts,
      };
      hostMap.set(host, entry);
    }

    entry.total++;
    if (observed) {
      entry.observed++;
    } else if (blocked) {
      entry.blocked++;
    } else if (redacted) {
      entry.redacted++;
    } else {
      entry.allowed++;
    }

    // Rows come back newest-first; first_seen is the smallest ts we encounter.
    if (ts < entry.first_seen) entry.first_seen = ts;
    if (ts > entry.last_seen)  entry.last_seen  = ts;
  }

  const hosts = Array.from(hostMap.values()).sort((a, b) => b.total - a.total);

  return NextResponse.json(
    {
      since,
      generated_at: new Date().toISOString(),
      summary: {
        total_calls:    totalCalls,
        governed_calls: governedCalls,
        shadow_ai_calls: shadowAiCalls,
        blocked_calls:  blockedCalls,
        redacted_calls: redactedCalls,
      },
      hosts,
    },
    { status: 200 }
  );
}
