import { sendAlertEmail } from "@/lib/email";

// Per-tenant anomaly alert routing — the SINGLE implementation of how a recorded
// anomaly is delivered to a tenant's OWN destinations (their Slack webhook and/or
// email). The ingest route fires this inline the instant an anomaly is recorded,
// and the optional Supabase DB webhook delegates here too, so there is exactly
// one send path and one message format. Customer anomaly data only ever goes to
// the tenant's own destinations — never to Vantio's shared channel. Never throws
// and is edge-safe (fetch + AbortSignal only).

export interface AnomalyAlertRecord {
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

export interface TenantAlertSettings {
  alert_slack_webhook_url?: string | null;
  alert_email?:             string | null;
  alerts_enabled?:          boolean | null;
}

const ALERT_TITLE = "🚨 Vantio — Policy Violation Detected";

function buildSlackMessage(record: AnomalyAlertRecord): object {
  const host   = record.anomaly_metadata?.target_host ?? "unknown";
  const action = record.anomaly_metadata?.action_taken ?? "POLICY_VIOLATION";
  const bytes  = record.anomaly_metadata?.bytes_severed;
  const pid    = record.anomaly_metadata?.pid;
  const time   = new Date(record.created_at).toLocaleString("en-US", { timeZone: "UTC" });

  return {
    blocks: [
      {
        type: "header",
        text: { type: "plain_text", text: ALERT_TITLE },
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
function buildEmailBody(record: AnomalyAlertRecord): string {
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
// the caller (ingest or the webhook ack).
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

/**
 * Deliver an anomaly to a tenant's OWN alert destinations. No-ops when alerting
 * is disabled or no destination is set. Each leg is individually bounded and
 * failure-safe, so this never throws regardless of Slack/email outcomes.
 */
export async function sendTenantAnomalyAlert(
  settings: TenantAlertSettings,
  record: AnomalyAlertRecord
): Promise<void> {
  // Master switch: only an explicit false disables alerting.
  if (settings.alerts_enabled === false) return;

  if (settings.alert_slack_webhook_url) {
    await postSlack(settings.alert_slack_webhook_url, buildSlackMessage(record));
  }

  if (settings.alert_email) {
    await sendAlertEmail(settings.alert_email, ALERT_TITLE, buildEmailBody(record));
  }
}
