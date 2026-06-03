import { NextRequest, NextResponse } from "next/server";

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

  const slackUrl = process.env.SLACK_WEBHOOK_URL;
  if (!slackUrl) {
    // Slack not configured — ack the webhook silently.
    return NextResponse.json({ ok: true, skipped: "SLACK_WEBHOOK_URL not set" });
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

  try {
    const res = await fetch(slackUrl, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(buildSlackMessage(body.record)),
    });

    if (!res.ok) {
      console.error("[vantio:slack] Slack responded with:", res.status, await res.text());
    }
  } catch (err) {
    console.error("[vantio:slack] Failed to send Slack alert:", err);
  }

  return NextResponse.json({ ok: true });
}
