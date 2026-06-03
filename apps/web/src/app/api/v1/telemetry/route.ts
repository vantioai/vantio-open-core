import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// POST /api/v1/telemetry — Lane 1: ANONYMOUS usage telemetry.
// NO API key, NO auth. This endpoint must never read x-vantio-identity and
// never stores an API key, email, raw IP, prompt content, or any PII. Only the
// allowlisted aggregate counters below are persisted; every other field on the
// incoming body is dropped. Rate-limited by a hashed IP (the raw IP is never
// stored). Edge runtime, like /ingest.

const RUNTIMES = new Set(["node", "python"]);
const EVENTS   = new Set(["run", "summary"]);

const MAX_HOSTS    = 100;
const MAX_HOST_LEN = 255;
const MAX_STR_LEN  = 128;
const MAX_COUNT    = 100_000_000;

interface TelemetryRow {
  anonymous_id:    string;
  sdk_version:     string | null;
  cli_version:     string | null;
  runtime:         string;
  runtime_version: string;
  os:              string;
  event:           string;
  hosts:           string[];
  call_count:      number;
  redacted_count:  number;
  blocked_count:   number;
  framework:       string | null;
  created_at:      string;
}

function str(raw: unknown, max = MAX_STR_LEN): string | null {
  if (typeof raw !== "string") return null;
  const s = raw.trim().slice(0, max);
  return s.length > 0 ? s : null;
}

function count(raw: unknown): number {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.min(Math.floor(n), MAX_COUNT);
}

function hosts(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const out: string[] = [];
  for (const h of raw) {
    if (typeof h !== "string") continue;
    const host = h.trim().toLowerCase().slice(0, MAX_HOST_LEN);
    if (host.length > 0) out.push(host);
    if (out.length >= MAX_HOSTS) break;
  }
  return out;
}

// Build the persisted row from the ALLOWLISTED fields only. Returns null when
// required fields are missing/invalid. Unknown fields on `raw` are ignored.
function buildRow(raw: unknown): TelemetryRow | null {
  if (typeof raw !== "object" || raw === null) return null;
  const b = raw as Record<string, unknown>;

  const anonymousId    = str(b["anonymousId"]);
  const runtime        = typeof b["runtime"] === "string" ? b["runtime"].trim().toLowerCase() : "";
  const runtimeVersion = str(b["runtimeVersion"], 64);
  const os             = str(b["os"], 64);
  const event          = typeof b["event"] === "string" ? b["event"].trim().toLowerCase() : "";

  if (!anonymousId) return null;
  if (!RUNTIMES.has(runtime)) return null;
  if (!runtimeVersion) return null;
  if (!os) return null;
  if (!EVENTS.has(event)) return null;

  return {
    anonymous_id:    anonymousId,
    sdk_version:     str(b["sdkVersion"], 64),
    cli_version:     str(b["cliVersion"], 64),
    runtime,
    runtime_version: runtimeVersion,
    os,
    event,
    hosts:           hosts(b["hosts"]),
    call_count:      count(b["callCount"]),
    redacted_count:  count(b["redactedCount"]),
    blocked_count:   count(b["blockedCount"]),
    framework:       str(b["framework"], 64),
    created_at:      new Date().toISOString(),
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

// Rate limit by IP to deter abuse of this unauthenticated lane — 60/min.
function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(60, "1 m"),
    analytics: false,
    prefix:    "vantio:telemetry",
  });
}

// SHA-256 of the client IP. Used only as an ephemeral rate-limit key so the
// raw IP never leaves this function or reaches Redis/the database.
async function hashIp(ip: string): Promise<string> {
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest("SHA-256", enc.encode(ip));
  return Array.from(new Uint8Array(buf)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

export const runtime = "edge";

export async function POST(request: NextRequest): Promise<NextResponse> {
  // ── Rate limit by hashed IP (edge, before DB) ─────────────────────────────
  const limiter = getRatelimiter();
  if (limiter) {
    // Use the PLATFORM-trusted client IP, not the leftmost (client-supplied)
    // x-forwarded-for value — an attacker can spoof/rotate that to mint a fresh
    // bucket and bypass the limit. Assumes Vercel's proxy: `x-real-ip` is set by
    // the platform, and the RIGHTMOST x-forwarded-for hop is the value appended
    // by the trusted proxy (leftmost entries are arbitrary client input).
    const rawIp =
      request.headers.get("x-real-ip")?.trim() ||
      request.headers.get("x-forwarded-for")?.split(",").pop()?.trim() ||
      "unknown";
    const key = await hashIp(rawIp);
    const { success } = await limiter.limit(key);
    if (!success) {
      return NextResponse.json(
        { error: "Rate limit exceeded." },
        { status: 429, headers: { "Retry-After": "60" } }
      );
    }
  }

  // ── Parse + validate (loosely) ────────────────────────────────────────────
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  const row = buildRow(rawBody);
  if (!row) {
    return NextResponse.json(
      {
        error: "Malformed telemetry.",
        message: "Required: anonymousId, runtime (node|python), runtimeVersion, os, event (run|summary).",
      },
      { status: 422 }
    );
  }

  // ── Persist allowlisted fields only ───────────────────────────────────────
  try {
    const supabase = getSupabaseAdmin();
    await supabase.from("usage_telemetry").insert(row);
  } catch (err) {
    console.error("[vantio:telemetry] Supabase write failed:", err);
  }

  return NextResponse.json({ ok: true }, { status: 202 });
}
