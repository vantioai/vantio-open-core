"use client";

import { useState } from "react";

interface WaitlistCtaProps {
  /** Coarse origin label sent to /api/v1/waitlist (e.g. "home" | "pricing" | "pro"). */
  source: string;
  /** Tailwind classes for the trigger/submit button so it matches each page's CTA. */
  buttonClassName: string;
  /** Optional spacing wrapper (e.g. "mb-8") to preserve the original CTA's layout. */
  wrapperClassName?: string;
  /** Trigger/submit label. */
  label?: string;
}

type State = "idle" | "submitting" | "success" | "error";

/**
 * Inline "Join the waitlist" CTA used while the Tier 2 public purchase flow is
 * disabled. Clicking reveals a small email form that POSTs to /api/v1/waitlist.
 * Renders nothing that can trigger a checkout — purely interest capture.
 */
export function WaitlistCta({
  source,
  buttonClassName,
  wrapperClassName,
  label = "Join the Waitlist",
}: WaitlistCtaProps) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [state, setState] = useState<State>("idle");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (state === "submitting") return;
    setState("submitting");
    try {
      const res = await fetch("/api/v1/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source }),
      });
      if (!res.ok) throw new Error();
      setState("success");
    } catch {
      setState("error");
    }
  }

  if (state === "success") {
    return (
      <div className={wrapperClassName}>
        <p className="rounded-xl border border-[--accent]/30 bg-[--accent]/10 px-4 py-3 text-center text-sm text-[--foreground]">
          You&apos;re on the list — we&apos;ll email you when Tier 2 opens.
        </p>
      </div>
    );
  }

  if (!open) {
    return (
      <div className={wrapperClassName}>
        <button type="button" onClick={() => setOpen(true)} className={buttonClassName}>
          {label}
        </button>
      </div>
    );
  }

  return (
    <div className={wrapperClassName}>
      <form onSubmit={submit} className="space-y-2">
        <input
          type="email"
          required
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm text-[--foreground] outline-none focus:border-[--accent]"
        />
        <button type="submit" disabled={state === "submitting"} className={`${buttonClassName} disabled:opacity-60`}>
          {state === "submitting" ? "Joining…" : label}
        </button>
        {state === "error" && (
          <p className="text-xs text-red-400">Something went wrong. Please try again.</p>
        )}
      </form>
    </div>
  );
}
