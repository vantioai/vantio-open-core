"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { Logo } from "@/components/logo";

const PRODUCT_LINKS: ReadonlyArray<readonly [string, string, string]> = [
  ["/developers", "Developers", "Free SDK & open-source"],
  ["/pro",        "Pro",        "SDK enforcement · $499/mo"],
  ["/enterprise", "Enterprise", "Kernel-level eBPF · custom"],
  ["/architecture","Architecture","How it's built"],
];

const MOBILE_LINKS: ReadonlyArray<readonly [string, string]> = [
  ["/developers",  "Developers"],
  ["/pro",         "Pro"],
  ["/enterprise",  "Enterprise"],
  ["/architecture","Architecture"],
  ["/pricing",     "Pricing"],
  ["/brief",       "The Brief"],
];

export function Nav() {
  const [productOpen, setProductOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close Product dropdown on outside click
  useEffect(() => {
    if (!productOpen) return;
    function onOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setProductOpen(false);
      }
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, [productOpen]);

  const closeMobile = () => setMobileOpen(false);
  const closeProduct = () => setProductOpen(false);

  return (
    <nav className="fixed top-0 z-50 w-full">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Frosted glass pill */}
        <div className="relative flex w-full items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 px-5 py-2.5 shadow-lg shadow-black/20 backdrop-blur-xl">

          {/* Brand */}
          <Link href="/" className="flex items-center gap-2.5 font-bold tracking-tight">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
              <Logo size={18} />
            </span>
            <span className="text-sm font-semibold tracking-wider text-[var(--foreground)]">VANTIO</span>
          </Link>

          {/* Desktop links */}
          <div className="hidden items-center gap-1 md:flex">
            {/* Product dropdown */}
            <div ref={dropdownRef} className="relative">
              <button
                type="button"
                onClick={() => setProductOpen((v) => !v)}
                aria-expanded={productOpen}
                aria-haspopup="true"
                className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition-all hover:bg-white/5 hover:text-[var(--foreground)]"
              >
                Product
                <svg
                  width="10" height="10" viewBox="0 0 10 10" fill="currentColor" aria-hidden="true"
                  className={`transition-transform duration-150 ${productOpen ? "rotate-180" : ""}`}
                >
                  <path d="M2 3.5 5 6.5 8 3.5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>

              {productOpen && (
                <div className="absolute left-1/2 top-full z-50 mt-2 w-56 -translate-x-1/2 rounded-2xl border border-[var(--border)] bg-[var(--surface)]/95 p-2 shadow-2xl shadow-black/40 backdrop-blur-xl">
                  {PRODUCT_LINKS.map(([href, label, sub]) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={closeProduct}
                      className="flex flex-col rounded-xl px-4 py-2.5 transition-colors hover:bg-white/5"
                    >
                      <span className="text-xs font-semibold text-[var(--foreground)]">{label}</span>
                      <span className="text-[10px] text-[var(--muted)]">{sub}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            {[
              ["/pricing", "Pricing"],
              ["/brief",   "The Brief"],
            ].map(([href, label]) => (
              <a key={href} href={href}
                className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition-all hover:bg-white/5 hover:text-[var(--foreground)]">
                {label}
              </a>
            ))}
          </div>

          {/* Dashboard CTA (desktop) */}
          <a href="/dashboard"
            className="hidden md:inline-flex items-center rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] px-4 py-1.5 text-xs font-semibold text-[var(--foreground)] transition-all hover:border-[var(--accent)]/40 hover:text-[var(--accent)]">
            Dashboard
          </a>

          {/* Mobile hamburger */}
          <div className="md:hidden">
            <button
              type="button"
              onClick={() => setMobileOpen((v) => !v)}
              aria-expanded={mobileOpen}
              aria-controls="mobile-nav-menu"
              aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] text-[var(--foreground)] transition-colors hover:border-[var(--accent)]/40 hover:text-[var(--accent)]"
            >
              {mobileOpen ? (
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

            {mobileOpen && (
              <>
                <button
                  type="button"
                  tabIndex={-1}
                  aria-hidden="true"
                  onClick={closeMobile}
                  className="fixed inset-0 z-40 cursor-default bg-black/40 backdrop-blur-sm"
                />
                <div
                  id="mobile-nav-menu"
                  className="absolute left-0 right-0 top-full z-50 mt-2 origin-top rounded-2xl border border-[var(--border)] bg-[var(--surface)]/95 p-2 shadow-2xl shadow-black/40 backdrop-blur-xl"
                >
                  <nav className="flex flex-col">
                    {MOBILE_LINKS.map(([href, label]) => (
                      <Link
                        key={href}
                        href={href}
                        onClick={closeMobile}
                        className="rounded-lg px-4 py-2.5 text-sm font-medium text-[var(--muted)] transition-colors hover:bg-white/5 hover:text-[var(--foreground)]"
                      >
                        {label}
                      </Link>
                    ))}
                    <Link
                      href="/dashboard"
                      onClick={closeMobile}
                      className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2.5 text-center text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)]"
                    >
                      Dashboard →
                    </Link>
                  </nav>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
