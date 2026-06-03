"use client";

import { useState } from "react";

// Reusable code snippet in the app's dark/mono style with a corner
// copy-to-clipboard button and line wrapping (no horizontal scrollbar).
// `navigator.clipboard` is guarded so it no-ops where unavailable.
export function CodeBlock({
  code,
  label,
  accent = false,
  className = "",
}: {
  code: string;
  label?: string;
  accent?: boolean;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard denied/unavailable — fail silently.
    }
  }

  return (
    <div>
      {label && (
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">{label}</p>
      )}
      <div className={`relative overflow-hidden rounded-lg ${className || "bg-[var(--surface)]"}`}>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? "Copied to clipboard" : "Copy code"}
          className="absolute right-2 top-2 z-10 inline-flex h-7 items-center gap-1 rounded-md border border-[var(--border-2)] bg-[var(--surface-2)]/80 px-2 text-[10px] font-semibold text-[var(--muted)] backdrop-blur-sm transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
        >
          {copied ? (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              Copied
            </>
          ) : (
            <>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <rect x="9" y="9" width="11" height="11" rx="2" />
                <path d="M5 15V5a2 2 0 0 1 2-2h10" />
              </svg>
              Copy
            </>
          )}
        </button>
        <pre className="whitespace-pre-wrap break-words p-4 pr-16 text-xs leading-relaxed">
          <code className={accent ? "text-[var(--accent)]" : "text-[var(--muted)]"}>{code}</code>
        </pre>
      </div>
    </div>
  );
}
