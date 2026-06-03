import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { sendAlertEmail } from "@/lib/email";

// Per-tenant anomaly alerting. Triggered by a Supabase DB webhook on INSERT into
// anomaly_events. Each customer's anomaly is routed to THEIR OWN Slack webhook
// and/or email (configured via /dashboard/alerts) — it is NEVER sent to Vantio's
// shared SLACK_WEBHOOK_URL channel. Runs on the Node runtime.
export const runtime = "nodejs";

interface AnomalyRecord {
  id:               string;
  tenant_identity:  string;
  trace_id:         string;
  audit_mode:       boolean;
  created_at:       string;
  anomaly_metadata: {
    target_host?:   string | null;
    action_taken?:  string | null;
    bytes_severed?: number | null;
    pid?:           number | null;
  } | null;
}

interface TenantAlertRouting {
  alerts_enabled:          boolean | null;
  alert_slack_webhook_url: string | null;
  alert_email:             string | null;
}

// Lazy service-role client — used only to look up the tenant's own alert
// routing. Same pattern as the other server routes.
function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}

function buildSlackMessage(record: AnomalyRecord): object {
  const host    = record.anomaly_metadata?.target_host ?? "unknown";
  const action  = record.anomaly_metadata?.action_taken ?? "POLICY_VIOLATION";
  const bytes   = record.anomaly_metadata?.bytes_severed;
  const pid     = record.anomaly_metadata?.pid;
  const time    = new Date(record.created_at).toLocaleString("en-US", { timeZone: "UTC" });

  return {
    blocks: [
      {
        type: "header",
        text: { type: "plain_text", text: "🚨 Vantio — Policy Violation Detected" },
      },
      {
        type: "section",
        fields: [
          { type: "mrkdwn", text: `*Tenant*\n${record.tenant_identity}` },
          { type: "mrkdwn", text: `*Target Host*\n${host}` },
          { type: "mrkdwn", text: `*Action*\n${action}` },
          { type: "mrkdwn", text: `*Bytes Blocked*\n${bytes != null ? bytes.toLocaleString() : "—"}` },
          { type: "mrkdwn", text: `*Trace ID*\n\`${record.trace_id.slice(0, 8)}…\`` },
          { type: "mrkdwn", text: `*PID*\n${pid ?? "—"}` },
        ],
      },
      {
        type: "context",
        elements: [
          { type: "mrkdwn", text: `*Audit Mode:* ${record.audit_mode ? "Yes" : "No"}  •  *Time (UTC):* ${time}` },
        ],
      },
      {
        type: "actions",
        elements: [
          {
            type:  "button",
            text:  { type: "plain_text", text: "View Dashboard" },
            url:   `${process.env.NEXT_PUBLIC_APP_URL}/dashboard`,
            style: "primary",
          },
        ],
      },
    ],
  };
}

// Plain-text email body — the same coarse metadata as the Slack alert plus a
// dashboard link. No prompt content or PII beyond the existing anomaly_metadata.
function buildEmailBody(record: AnomalyRecord): string {
  const host   = record.anomaly_metadata?.target_host ?? "unknown";
  const action = record.anomaly_metadata?.action_taken ?? "POLICY_VIOLATION";
  const bytes  = record.anomaly_metadata?.bytes_severed;
  const pid    = record.anomaly_metadata?.pid;
  const time   = new Date(record.created_at).toLocaleString("en-US", { timeZone: "UTC" });
  const dash   = `${process.env.NEXT_PUBLIC_APP_URL ?? ""}/dashboard`;

  return [
    "Vantio — Policy Violation Detected",
    "",
    `Target Host:   ${host}`,
    `Action:        ${action}`,
    `Bytes Blocked: ${bytes != null ? bytes.toLocaleString() : "—"}`,
    `Trace ID:      ${record.trace_id.slice(0, 8)}…`,
    `PID:           ${pid ?? "—"}`,
    `Audit Mode:    ${record.audit_mode ? "Yes" : "No"}`,
    `Time (UTC):    ${time}`,
    "",
    `View dashboard: ${dash}`,
  ].join("\n");
}

// Bounded, failure-safe Slack POST so a slow/broken tenant webhook never breaks
// the webhook ack.
async function postSlack(url: string, payload: object): Promise<void> {
  try {
    const res = await fetch(url, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
      signal:  AbortSignal.timeout(3000),
    });
    if (!res.ok) {
      console.error("[vantio:alerts] Slack responded with:", res.status, await res.text());
    }
  } catch (err) {
    console.error("[vantio:alerts] Failed to send Slack alert:", err);
  }
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  // Verify the request is from Supabase using a shared secret.
  // Fail closed: if the secret is not configured the endpoint must not be open.
  const webhookSecret = process.env.SUPABASE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json(
      { error: "Webhook secret not configured." },
      { status: 503 }
    );
  }
  const authHeader = req.headers.get("authorization");
  if (authHeader !== `Bearer ${webhookSecret}`) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }

  let body: { type?: string; record?: AnomalyRecord };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  // Supabase sends type: "INSERT" | "UPDATE" | "DELETE"
  if (body.type !== "INSERT" || !body.record) {
    return NextResponse.json({ ok: true });
  }
  const record = body.record;

  // Per-tenant routing: look up THIS tenant's own alert settings by
  // tenant_identity (= the tenant's email). Customer anomaly data only ever
  // goes to the destinations the tenant configured for themselves.
  const supabase = getSupabaseAdmin();
  const { data: tenantRow } = await supabase
    .from("tenants")
    .select("alerts_enabled, alert_slack_webhook_url, alert_email")
    .eq("email", record.tenant_identity)
    .maybeSingle();

  const tenant = tenantRow as TenantAlertRouting | null;

  // Unknown tenant or alerts disabled → ack and do nothing.
  if (!tenant || tenant.alerts_enabled === false) {
    return NextResponse.json({ ok: true, skipped: "no tenant or alerts disabled" });
  }

  // Send to the tenant's own Slack webhook, if they set one.
  if (tenant.alert_slack_webhook_url) {
    await postSlack(tenant.alert_slack_webhook_url, buildSlackMessage(record));
  }

  // Send to the tenant's own alert email, if they set one.
  if (tenant.alert_email) {
    await sendAlertEmail(
      tenant.alert_email,
      "🚨 Vantio — Policy Violation Detected",
      buildEmailBody(record)
    );
  }

  return NextResponse.json({ ok: true });
}
