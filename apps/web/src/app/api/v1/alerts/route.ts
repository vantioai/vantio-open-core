import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Per-tenant anomaly alert settings. Authenticated by the logged-in Supabase
// user (session cookie) — NOT by an API key — exactly like /api/v1/policy.
// Reads/writes ONLY the caller's own tenant row (resolved by the authenticated
// user's email); another tenant's row can never be read or written. Lets each
// tenant route their anomaly alerts to THEIR OWN Slack webhook + email so
// customer data never flows to Vantio's shared channel.

const EMAIL_RE     = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SLACK_PREFIX = "https://hooks.slack.com/";
const MAX_URL_LEN  = 1024;
const MAX_EMAIL_LEN = 256;

export interface AlertSettings {
  alert_slack_webhook_url: string;
  alert_email:             string;
  alerts_enabled:          boolean;
}

function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}

async function getAuthedEmail(): Promise<string | null> {
  const cookieStore = await cookies();
  const authClient  = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();
  return user?.email ?? null;
}

function rowToSettings(row: Record<string, unknown> | null): AlertSettings {
  return {
    alert_slack_webhook_url:
      typeof row?.["alert_slack_webhook_url"] === "string" ? (row["alert_slack_webhook_url"] as string) : "",
    alert_email:
      typeof row?.["alert_email"] === "string" ? (row["alert_email"] as string) : "",
    // Defaults true (DB default) — only an explicit false disables alerting.
    alerts_enabled: row?.["alerts_enabled"] !== false,
  };
}

export async function GET(): Promise<NextResponse> {
  const email = await getAuthedEmail();
  if (!email) return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });

  const supabase = getSupabaseAdmin();
  const { data } = await supabase
    .from("tenants")
    .select("alert_slack_webhook_url, alert_email, alerts_enabled")
    .eq("email", email)
    .single();

  if (!data) return NextResponse.json({ error: "No tenant found." }, { status: 404 });

  return NextResponse.json({ settings: rowToSettings(data as Record<string, unknown>) });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const email = await getAuthedEmail();
  if (!email) return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }
  const b = (typeof rawBody === "object" && rawBody !== null ? rawBody : {}) as Record<string, unknown>;

  // Slack webhook: empty clears it; otherwise it must be a real Slack incoming
  // webhook URL so we can't be pointed at an arbitrary host.
  const slackRaw =
    typeof b["alert_slack_webhook_url"] === "string"
      ? b["alert_slack_webhook_url"].trim().slice(0, MAX_URL_LEN)
      : "";
  if (slackRaw && !slackRaw.startsWith(SLACK_PREFIX)) {
    return NextResponse.json(
      { error: "Slack webhook URL must start with https://hooks.slack.com/." },
      { status: 422 }
    );
  }

  // Alert email: empty clears it; otherwise it must be well-formed.
  const emailRaw =
    typeof b["alert_email"] === "string" ? b["alert_email"].trim().slice(0, MAX_EMAIL_LEN) : "";
  if (emailRaw && !EMAIL_RE.test(emailRaw)) {
    return NextResponse.json(
      { error: "Alert email is not a valid email address." },
      { status: 422 }
    );
  }

  const alertsEnabled = b["alerts_enabled"] !== false;

  // Resolve the caller's tenant, then write ONLY that row. The update is keyed
  // by the authenticated email, so another tenant's row can never be touched.
  const supabase = getSupabaseAdmin();
  const { data: tenant, error: tenantErr } = await supabase
    .from("tenants")
    .select("id")
    .eq("email", email)
    .single();

  if (tenantErr || !tenant) {
    return NextResponse.json({ error: "No tenant found for this account." }, { status: 404 });
  }

  const { error: updateErr } = await supabase
    .from("tenants")
    .update({
      alert_slack_webhook_url: slackRaw || null,
      alert_email:             emailRaw || null,
      alerts_enabled:          alertsEnabled,
      updated_at:              new Date().toISOString(),
    })
    .eq("email", email);

  if (updateErr) {
    console.error("[vantio:alerts] update failed:", updateErr);
    return NextResponse.json({ error: "Failed to save alert settings." }, { status: 500 });
  }

  return NextResponse.json({
    ok: true,
    settings: {
      alert_slack_webhook_url: slackRaw,
      alert_email:             emailRaw,
      alerts_enabled:          alertsEnabled,
    } satisfies AlertSettings,
  });
}
