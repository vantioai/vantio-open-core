"use client";

import { useState } from "react";
import { PII_TYPES, type TenantPolicy } from "@/lib/policy";

function parseHostList(text: string): string[] {
  return Array.from(
    new Set(
      text
        .split(/[\n,]/)
        .map((h) => h.trim().toLowerCase())
        .filter((h) => h.length > 0)
    )
  );
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
      className="flex w-full items-start justify-between gap-4 rounded-xl border border-[--border] bg-[--surface-2] p-4 text-left transition-colors hover:border-[--border-2]"
      aria-pressed={checked}
    >
      <span>
        <span className="block text-sm font-semibold text-[--foreground]">{label}</span>
        <span className="mt-0.5 block text-xs text-[--muted]">{hint}</span>
      </span>
      <span
        className={`mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors ${
          checked ? "bg-[--accent]" : "bg-[--border-2]"
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

export function PolicyEditor({ initialPolicy }: { initialPolicy: TenantPolicy }) {
  const [enforce, setEnforce] = useState(initialPolicy.enforce);
  const [redactPii, setRedactPii] = useState(initialPolicy.redact_pii);
  const [piiTypes, setPiiTypes] = useState<string[]>(initialPolicy.pii_types);
  const [allowedHosts, setAllowedHosts] = useState(initialPolicy.allowed_hosts.join("\n"));
  const [blockedHosts, setBlockedHosts] = useState(initialPolicy.blocked_hosts.join("\n"));
  const [maxBytes, setMaxBytes] = useState(String(initialPolicy.max_request_bytes ?? 0));
  const [spendCap, setSpendCap] = useState(String(initialPolicy.spend_cap_usd ?? 0));

  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<"idle" | "saved" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  function togglePii(type: string) {
    setPiiTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
    setStatus("idle");
  }

  async function save() {
    setSaving(true);
    setStatus("idle");
    setMessage(null);

    const policy: TenantPolicy = {
      enforce,
      redact_pii: redactPii,
      pii_types: piiTypes,
      allowed_hosts: parseHostList(allowedHosts),
      blocked_hosts: parseHostList(blockedHosts),
      max_request_bytes: Math.max(0, Math.floor(Number(maxBytes) || 0)),
      spend_cap_usd: Math.max(0, Number(spendCap) || 0),
    };

    try {
      const res = await fetch("/api/v1/policy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ policy }),
      });
      const data = (await res.json()) as { ok?: boolean; error?: string };
      if (res.ok && data.ok) {
        setStatus("saved");
        setMessage("Policy saved. Your SDK/CLI will pick it up on its next config sync.");
      } else {
        setStatus("error");
        setMessage(data.error ?? "Failed to save policy.");
      }
    } catch {
      setStatus("error");
      setMessage("Failed to save policy.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Enforcement mode */}
      <section className="rounded-2xl border border-[--border] bg-[--surface] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[--foreground]">Enforcement</h2>
        <p className="mb-4 text-xs text-[--muted]">
          When enforcement is off, the SDK observes and reports only. When on, it actively
          redacts and blocks per the rules below.
        </p>
        <Toggle
          checked={enforce}
          onChange={(v) => {
            setEnforce(v);
            setStatus("idle");
          }}
          label="Enforce policy"
          hint="Block and redact in real time. Off = observe-only (audit)."
        />
      </section>

      {/* PII redaction */}
      <section className="rounded-2xl border border-[--border] bg-[--surface] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[--foreground]">PII Redaction</h2>
        <p className="mb-4 text-xs text-[--muted]">
          The SDK strips matching data from requests before they leave your environment.
          Vantio never sees the original content.
        </p>
        <div className="mb-5">
          <Toggle
            checked={redactPii}
            onChange={(v) => {
              setRedactPii(v);
              setStatus("idle");
            }}
            label="Redact PII"
            hint="Mask the selected categories client-side."
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {PII_TYPES.map((type) => {
            const active = piiTypes.includes(type);
            return (
              <button
                key={type}
                type="button"
                onClick={() => togglePii(type)}
                disabled={!redactPii}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-40 ${
                  active
                    ? "border-[--accent]/40 bg-[--accent]/10 text-[--accent]"
                    : "border-[--border-2] bg-[--surface-2] text-[--muted] hover:text-[--foreground]"
                }`}
              >
                {type.replace(/_/g, " ")}
              </button>
            );
          })}
        </div>
      </section>

      {/* Host rules */}
      <section className="rounded-2xl border border-[--border] bg-[--surface] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[--foreground]">Host Policy</h2>
        <p className="mb-4 text-xs text-[--muted]">
          One host per line. If an allow-list is set, only those hosts are permitted; blocked
          hosts are always denied.
        </p>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[--muted]">
              Allowed hosts
            </label>
            <textarea
              value={allowedHosts}
              onChange={(e) => {
                setAllowedHosts(e.target.value);
                setStatus("idle");
              }}
              rows={5}
              placeholder={"api.openai.com\napi.anthropic.com"}
              className="w-full rounded-xl border border-[--border-2] bg-[--surface-2] px-3 py-2.5 font-mono text-xs text-[--foreground] outline-none transition-colors placeholder-[--muted] focus:border-[--accent]/50"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[--muted]">
              Blocked hosts
            </label>
            <textarea
              value={blockedHosts}
              onChange={(e) => {
                setBlockedHosts(e.target.value);
                setStatus("idle");
              }}
              rows={5}
              placeholder={"pastebin.com\nunknown-host.example"}
              className="w-full rounded-xl border border-[--border-2] bg-[--surface-2] px-3 py-2.5 font-mono text-xs text-[--foreground] outline-none transition-colors placeholder-[--muted] focus:border-red-400/50"
            />
          </div>
        </div>
      </section>

      {/* Limits */}
      <section className="rounded-2xl border border-[--border] bg-[--surface] p-6">
        <h2 className="mb-1 text-sm font-semibold text-[--foreground]">Limits</h2>
        <p className="mb-4 text-xs text-[--muted]">
          Set to 0 to disable a limit. Spend caps are enforced per the SDK&apos;s local cost
          accounting.
        </p>
        <div className="grid gap-5 sm:grid-cols-2">
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[--muted]">
              Max request bytes
            </label>
            <input
              type="number"
              min={0}
              value={maxBytes}
              onChange={(e) => {
                setMaxBytes(e.target.value);
                setStatus("idle");
              }}
              className="w-full rounded-xl border border-[--border-2] bg-[--surface-2] px-3 py-2.5 text-sm text-[--foreground] outline-none transition-colors focus:border-[--accent]/50"
            />
          </div>
          <div>
            <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[--muted]">
              Spend cap (USD)
            </label>
            <input
              type="number"
              min={0}
              step="0.01"
              value={spendCap}
              onChange={(e) => {
                setSpendCap(e.target.value);
                setStatus("idle");
              }}
              className="w-full rounded-xl border border-[--border-2] bg-[--surface-2] px-3 py-2.5 text-sm text-[--foreground] outline-none transition-colors focus:border-[--accent]/50"
            />
          </div>
        </div>
      </section>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="rounded-xl bg-[--accent] px-6 py-3 text-sm font-bold text-black transition-all hover:bg-[--accent-dim] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)] disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Policy"}
        </button>
        {message && (
          <p className={`text-xs ${status === "error" ? "text-red-400" : "text-[--accent]"}`}>
            {message}
          </p>
        )}
      </div>
    </div>
  );
}
