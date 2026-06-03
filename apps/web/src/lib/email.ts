// Outbound alert email — isolated here so the email provider stays swappable.
// Today it speaks Resend's REST API directly (no SDK dependency); swapping
// providers means editing ONLY this file. Carries nothing beyond the coarse
// anomaly metadata already shown in the Slack alert — no prompt content or PII.

const RESEND_ENDPOINT = "https://api.resend.com/emails";

/**
 * Send a plain-text alert email via Resend. Never throws: a failed or
 * unconfigured send must not break the caller (e.g. the anomaly webhook).
 * If RESEND_API_KEY is unset this is a no-op (debug log only).
 */
export async function sendAlertEmail(
  to: string,
  subject: string,
  text: string
): Promise<void> {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    // No provider configured — skip silently so dev/unconfigured prod never throw.
    console.debug("[vantio:email] RESEND_API_KEY unset; skipping alert email.");
    return;
  }

  const from = process.env.ALERT_FROM_EMAIL || "alerts@vantio.ai";

  try {
    const res = await fetch(RESEND_ENDPOINT, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ from, to, subject, text }),
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) {
      console.error("[vantio:email] Resend responded with:", res.status, await res.text());
    }
  } catch (err) {
    console.error("[vantio:email] Failed to send alert email:", err);
  }
}
