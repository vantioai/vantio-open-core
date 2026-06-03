"use client";

import { useState } from "react";

export interface AlertSettings {
  alert_slack_webhook_url: string;
  alert_email:             string;
  alerts_enabled:          boolean;
}

function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex w-full items-start justify-between gap-4 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4 text-left transition-colors hover:border-[var(--border-2)]"
      aria-pressed={checked}
    >
      <span>
        <span className="block text-sm font-semibold text-[var(--foreground)]">{label}</span>
        <span className="mt-0.5 block text-xs text-[var(--muted)]">{hint}</span>
      </span>
      <span
        className={`mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors ${
          checked ? "bg-[var(--accent)]" : "bg-[var(--border-2)]"
        }`}
      >
        <span
          className={`h-4 w-4 rounded-full bg-white transition-transform ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </span>
    </button>
  );
}

export function AlertsEditor({ initialSettings }: { initialSettings: AlertSettings }) {
  const [slackUrl, setSlackUrl]   = useState(initialSettings.alert_slack_webhook_url);
  const [alertEmail, setAlertEmail] = useState(initialSettings.alert_email);
  const [enabled, setEnabled]     = useState(initialSettings.alerts_enabled);

  const [saving, setSaving]   = useState(false);
  const [status, setStatus]   = useState<"idle" | "saved" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setStatus("idle");
    setMessage(null);

    try {
      const res = await fetch("/api/v1/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          alert_slack_webhook_url: slackUrl.trim(),
          alert_email:             alertEmail.trim(),
          alerts_enabled:          enabled,
        }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        setStatus("saved");
        setMessage("Alert settings saved. New anomalies will route to your destinations.");
      } else {
        setStatus("error");
        setMessage(data.error ?? "Failed to save alert settings.");
      }
    } catch {
      setStatus("error");
      setMessage("Failed to save alert settings.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Master switch */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[var(--foreground)]">Alerting</h2>
        <p className="mb-4 text-xs text-[var(--muted)]">
          When on, each policy violation on your account is delivered to the destinations
          below. Anomaly alerts go ONLY to your own Slack/email — never to a shared channel.
        </p>
        <Toggle
          checked={enabled}
          onChange={(v) => {
            setEnabled(v);
            setStatus("idle");
          }}
          label="Enable alerts"
          hint="Off = anomalies are still recorded, but no Slack/email is sent."
        />
      </section>

      {/* Slack destination */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[var(--foreground)]">Slack Webhook</h2>
        <p className="mb-4 text-xs text-[var(--muted)]">
          Your own Slack incoming webhook. Create one at{" "}
          <span className="font-mono text-[var(--foreground)]/80">api.slack.com/apps</span> → Incoming
          Webhooks. Leave blank to disable Slack alerts.
        </p>
        <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
          Webhook URL
        </label>
        <input
          type="url"
          value={slackUrl}
          onChange={(e) => {
            setSlackUrl(e.target.value);
            setStatus("idle");
          }}
          placeholder="https://hooks.slack.com/services/T000/B000/xxxx"
          className="w-full rounded-xl border border-[var(--border-2)] bg-[var(--surface-2)] px-3 py-2.5 font-mono text-xs text-[var(--foreground)] outline-none transition-colors placeholder-[var(--muted)] focus:border-[var(--accent)]/50"
        />
      </section>

      {/* Email destination */}
      <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[var(--foreground)]">Alert Email</h2>
        <p className="mb-4 text-xs text-[var(--muted)]">
          Where to email policy-violation alerts. Leave blank to disable email alerts.
        </p>
        <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
          Email address
        </label>
        <input
          type="email"
          value={alertEmail}
          onChange={(e) => {
            setAlertEmail(e.target.value);
            setStatus("idle");
          }}
          placeholder="security@yourcompany.com"
          className="w-full rounded-xl border border-[var(--border-2)] bg-[var(--surface-2)] px-3 py-2.5 text-sm text-[var(--foreground)] outline-none transition-colors placeholder-[var(--muted)] focus:border-[var(--accent)]/50"
        />
      </section>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-xl bg-[var(--accent)] px-6 py-3 text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)] disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Alert Settings"}
        </button>
        {message && (
          <p className={`text-xs ${status === "error" ? "text-red-400" : "text-[var(--accent)]"}`}>
            {message}
          </p>
        )}
      </div>
    </div>
  );
}
