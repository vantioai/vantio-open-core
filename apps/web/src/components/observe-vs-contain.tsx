// Code-built contrast visual for the "Watching isn't governing" manifesto.
// Left  = a dim, passive radar just watching (Observe — after the fact).
// Right = a glowing boundary severing an egress attempt (Contain — before it
// leaves). Pure CSS/SVG, on-brand, decorative (aria-hidden). Motion disables
// under prefers-reduced-motion via globals.css.
export function ObserveVsContain() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Observe — passive */}
      <figure className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-7">
        <div className="relative mx-auto aspect-square w-40" aria-hidden="true">
          <div className="absolute inset-0 rounded-full border border-[var(--muted)]/25" />
          <div className="absolute inset-[18%] rounded-full border border-[var(--muted)]/20" />
          <div className="absolute inset-[36%] rounded-full border border-[var(--muted)]/15" />
          <span className="ovc-ping absolute inset-[36%] rounded-full border border-[var(--muted)]/40" />
          {/* sweep arm */}
          <div className="ovc-radar absolute inset-0">
            <div className="absolute left-1/2 top-0 h-1/2 w-px -translate-x-1/2 bg-gradient-to-t from-[var(--muted)]/0 to-[var(--muted)]/60" />
          </div>
          <span className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--muted)]/70" />
        </div>
        <figcaption className="mt-5 text-center">
          <span className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Observe</span>
          <p className="mt-1 text-xs text-[var(--muted)]">After the fact</p>
        </figcaption>
      </figure>

      {/* Contain — active */}
      <figure className="rounded-2xl border border-[var(--accent)]/30 bg-[var(--accent)]/5 p-7">
        <div className="relative mx-auto aspect-square w-40" aria-hidden="true">
          <div className="pointer-events-none absolute inset-[6%] rounded-full bg-[var(--accent)]/10 blur-xl" />
          <div className="cv-ring absolute inset-[10%] rounded-full border border-[var(--accent)]/60" />
          <span className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[var(--accent)]/80 bg-[var(--accent)]/10" />
          {/* egress attempt, severed at the boundary */}
          <div className="absolute left-1/2 top-1/2 h-px w-1/2 origin-left" style={{ transform: "rotate(20deg)" }}>
            <div className="h-px w-full bg-gradient-to-r from-red-500/0 via-red-500/30 to-red-500/0" />
            <span className="cv-blocked absolute top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-red-500" />
            <span className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: "60%" }}>
              <span className="cv-sever block">
                <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="rgb(248 113 113)" strokeWidth="2.5" strokeLinecap="round">
                  <line x1="4" y1="4" x2="12" y2="12" />
                  <line x1="12" y1="4" x2="4" y2="12" />
                </svg>
              </span>
            </span>
          </div>
        </div>
        <figcaption className="mt-5 text-center">
          <span className="text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">Contain</span>
          <p className="mt-1 text-xs text-[var(--muted)]">Before it leaves</p>
        </figcaption>
      </figure>
    </div>
  );
}
