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
      className="font-medium text-gray-700 hover:text-gray-900 disabled:opacity-50"
    >
      {loading ? "Loading…" : "Manage Billing"}
    </button>
  );
}
