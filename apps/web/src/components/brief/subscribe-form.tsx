"use client";

import { useState } from "react";

type State = "idle" | "submitting" | "success" | "error";

// Email capture for The Brief. POSTs to /api/v1/subscribe (anonymous, email
// only). Privacy-safe and graceful: never blocks, never collects more than the
// volunteered address.
export function SubscribeForm({ source, className = "" }: { source: string; className?: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (state === "submitting") return;
    setState("submitting");
    try {
      const res = await fetch("/api/v1/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source }),
      });
      if (!res.ok) throw new Error();
      setState("success");
      setEmail("");
    } catch {
      setState("error");
    }
  }

  if (state === "success") {
    return (
      <p className={`rounded-xl border border-[var(--accent)]/30 bg-[var(--accent)]/10 px-4 py-3 text-center text-sm text-[var(--foreground)] ${className}`}>
        You&apos;re on the list — we&apos;ll send the next Brief straight to your inbox.
      </p>
    );
  }

  return (
    <div className={className}>
      <form onSubmit={submit} className="flex flex-col gap-2 sm:flex-row">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full flex-1 rounded-xl border border-[var(--border-2)] bg-[var(--surface-2)] px-4 py-3 text-sm text-[var(--foreground)] placeholder-[var(--muted)] outline-none transition-colors focus:border-[var(--accent)]/50"
        />
        <button
          type="submit"
          disabled={state === "submitting"}
          className="shrink-0 rounded-xl bg-[var(--accent)] px-6 py-3 text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)] disabled:opacity-50"
        >
          {state === "submitting" ? "Subscribing…" : "Subscribe"}
        </button>
      </form>
      {state === "error" && (
        <p className="mt-2 text-xs text-red-400">Something went wrong. Please try again.</p>
      )}
      <p className="mt-2 text-[11px] text-[var(--muted)]">No spam. Email only — unsubscribe anytime.</p>
    </div>
  );
}
