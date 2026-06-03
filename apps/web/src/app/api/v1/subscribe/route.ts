import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// POST /api/v1/subscribe — "The Brief" newsletter capture. NO API key, NO auth.
// Stores ONLY the email the visitor volunteers plus a coarse source label — no
// other PII, no raw IP, no content. Rate-limited by a hashed IP (the raw IP is
// never stored). Edge runtime, mirrors /api/v1/waitlist.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SOURCES = new Set(["brief", "article"]);
const MAX_EMAIL_LEN = 256;

interface SubscribeInput {
  email: string;
  source: string | null;
}

function validate(raw: unknown): SubscribeInput | null {
  if (typeof raw !== "object" || raw === null) return null;
  const b = raw as Record<string, unknown>;
  if (typeof b["email"] !== "string") return null;
  const email = b["email"].trim().toLowerCase().slice(0, MAX_EMAIL_LEN);
  if (!EMAIL_RE.test(email)) return null;
  const rawSource = typeof b["source"] === "string" ? b["source"].trim().toLowerCase() : "";
  return { email, source: SOURCES.has(rawSource) ? rawSource : null };
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

// Rate limit by IP to deter abuse of this unauthenticated lane — 10/min.
function getRatelimiter() {
  const url   = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return new Ratelimit({
    redis:     new Redis({ url, token }),
    limiter:   Ratelimit.slidingWindow(10, "1 m"),
    analytics: false,
    prefix:    "vantio:subscribe",
  });
}

// SHA-256 of the client IP — used only as an ephemeral rate-limit key, never stored.
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

  // ── Parse + validate ──────────────────────────────────────────────────────
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  const input = validate(rawBody);
  if (!input) {
    return NextResponse.json({ error: "A valid email is required." }, { status: 422 });
  }

  // ── Persist email + coarse source only (dedupe on email). Never throw to the
  //    client on a DB failure beyond a generic message. ──────────────────────
  try {
    const supabase = getSupabaseAdmin();
    const { error } = await supabase
      .from("subscribers")
      .upsert(
        { email: input.email, source: input.source },
        { onConflict: "email", ignoreDuplicates: true }
      );
    if (error) {
      console.error("[vantio:subscribe] Supabase write failed:", error.message, error);
      return NextResponse.json(
        { error: "Could not save your subscription. Please try again." },
        { status: 500 }
      );
    }
  } catch (err) {
    console.error("[vantio:subscribe] Supabase write threw:", err);
    return NextResponse.json(
      { error: "Could not save your subscription. Please try again." },
      { status: 500 }
    );
  }

  return NextResponse.json({ ok: true }, { status: 202 });
}
