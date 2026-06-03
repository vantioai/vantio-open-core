"use client";

import { useState } from "react";
import Link from "next/link";

// Mobile-only hamburger navigation. The desktop nav lives in layout.tsx behind
// `hidden md:flex`; this renders the matching links inside a frosted dropdown for
// small screens. Closes on link click and on toggle. No new deps — inline SVG.
const LINKS: ReadonlyArray<readonly [string, string]> = [
  ["/architecture", "Architecture"],
  ["/pricing", "Pricing"],
  ["/enterprise", "Enterprise"],
  ["/pro", "Pro"],
  ["/developers", "Developers"],
  ["/brief", "The Brief"],
];

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);

  return (
    <div className="md:hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="mobile-nav-menu"
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] text-[var(--foreground)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
      >
        {open ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <line x1="6" y1="6" x2="18" y2="18" />
            <line x1="18" y1="6" x2="6" y2="18" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        )}
      </button>

      {open && (
        <>
          {/* Tap-out backdrop */}
          <button
            type="button"
            tabIndex={-1}
            aria-hidden="true"
            onClick={close}
            className="fixed inset-0 z-40 cursor-default bg-black/40 backdrop-blur-sm"
          />
          <div
            id="mobile-nav-menu"
            className="absolute left-0 right-0 top-full z-50 mt-2 origin-top rounded-2xl border border-[var(--border)] bg-[var(--surface)]/95 p-2 shadow-2xl shadow-black/40 backdrop-blur-xl"
          >
            <nav className="flex flex-col">
              {LINKS.map(([href, label]) => (
                <Link
                  key={href}
                  href={href}
                  onClick={close}
                  className="rounded-lg px-4 py-2.5 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-white/5 hover:text-[var(--foreground)]"
                >
                  {label}
                </Link>
              ))}
              <Link
                href="/dashboard"
                onClick={close}
                className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2.5 text-center text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)]"
              >
                Dashboard →
              </Link>
            </nav>
          </div>
        </>
      )}
    </div>
  );
}
