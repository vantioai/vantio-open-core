import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// POST /api/v1/waitlist — Tier 2 (Pro) interest capture while the public
// purchase flow is disabled (waitlist-only until billing is live). NO API key,
// NO auth. Stores ONLY the email the visitor volunteers plus a coarse source
// label — no other PII, no raw IP, no prompt content. Rate-limited by a hashed
// IP (the raw IP is never stored). Edge runtime, like /telemetry.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SOURCES = new Set(["home", "pricing", "pro", "success"]);
const MAX_EMAIL_LEN = 256;

interface WaitlistInput {
  email: string;
  source: string | null;
}

// Build the persisted input from the ALLOWLISTED fields only. Returns null when
// the email is missing/malformed. The email is lower-cased so dedup is
// case-insensitive; `source` is coerced to a known coarse label or null.
function validate(raw: unknown): WaitlistInput | null {
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
    prefix:    "vantio:waitlist",
  });
}

// SHA-256 of the client IP. Used only as an ephemeral rate-limit key so the
// raw IP never leaves this function or reaches Redis/the database.
async function hashIp(ip: string): Promise<string> {
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest("SHA-256", enc.encode(ip));
  return Array.from(new Uint8Array(buf)).map((x) => x.toString(16).padStart(2, "0")).join("");
}

// Escape Slack mrkdwn control characters before interpolating user input.
function slackEscape(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export const runtime = "edge";

export async function POST(request: NextRequest): Promise<NextResponse> {
  // ── Rate limit by hashed IP (edge, before DB) ─────────────────────────────
  const limiter = getRatelimiter();
  if (limiter) {
    // Use the PLATFORM-trusted client IP, not the leftmost (client-supplied)
    // x-forwarded-for value — an attacker can spoof/rotate that to mint a fresh
    // bucket and bypass the limit.
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

  // ── Persist email + coarse source only (dedupe on email; never PII beyond
  //    the volunteered email). Never throw to the client on a DB failure. ─────
  try {
    const supabase = getSupabaseAdmin();
    const { error } = await supabase
      .from("waitlist")
      .upsert(
        { email: input.email, source: input.source, metadata: {} },
        { onConflict: "email", ignoreDuplicates: true }
      );
    if (error) {
      console.error("[vantio:waitlist] Supabase write failed:", error.message, error);
      return NextResponse.json(
        { error: "Could not save your signup. Please try again." },
        { status: 500 }
      );
    }
  } catch (err) {
    console.error("[vantio:waitlist] Supabase write threw:", err);
    return NextResponse.json(
      { error: "Could not save your signup. Please try again." },
      { status: 500 }
    );
  }

  // ── Notify internal Slack channel if configured. Escape the only
  //    user-supplied field (email) before interpolation. ─────────────────────
  const slackUrl = process.env.SLACK_WEBHOOK_URL;
  if (slackUrl) {
    // Await the Slack POST: in the edge runtime a fire-and-forget promise is
    // killed once the response is returned, so it must complete before we return.
    // Bounded + failure-safe so a slow/broken Slack never breaks the signup.
    try {
      await fetch(slackUrl, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          blocks: [
            { type: "header", text: { type: "plain_text", text: "📝 New Tier 2 Waitlist Signup" } },
            {
              type: "section",
              fields: [
                { type: "mrkdwn", text: `*Email*\n${slackEscape(input.email)}` },
                { type: "mrkdwn", text: `*Source*\n${input.source ?? "—"}` },
              ],
            },
          ],
        }),
        signal: AbortSignal.timeout(3000),
      });
    } catch (err) {
      console.error("[vantio:waitlist] Slack notify failed:", err);
    }
  }

  return NextResponse.json({ ok: true }, { status: 202 });
}
