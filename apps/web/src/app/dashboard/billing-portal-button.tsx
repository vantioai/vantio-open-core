"use client";

import { useState } from "react";

export function BillingPortalButton() {
  const [loading, setLoading] = useState(false);

  async function openPortal() {
    setLoading(true);
    try {
      const res  = await fetch("/api/stripe/portal", { method: "POST" });
      const data = await res.json() as { url?: string; error?: string };
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert(data.error ?? "Unable to open billing portal.");
        setLoading(false);
      }
    } catch {
      alert("Unable to open billing portal.");
      setLoading(false);
    }
  }

  return (
    <button
      onClick={openPortal}
      disabled={loading}
      className="rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] px-4 py-1.5 text-xs font-semibold text-[var(--foreground)] transition-all hover:border-[var(--accent)]/40 hover:text-[var(--accent)] disabled:opacity-50"
    >
      {loading ? "Loading…" : "Manage Billing"}
    </button>
  );
}
