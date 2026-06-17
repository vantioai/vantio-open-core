/**
 * Market-data stats strip — AI agent adoption, governance gap, and incident costs.
 *
 * Sources (in order):
 *  1. Deloitte "State of AI in the Enterprise" 2026 — survey of 3,235 IT & business
 *     leaders across 24 countries. Primary large-scale survey.
 *  2. IBM / Ponemon Institute "Cost of a Data Breach Report" 2025 — 600 breached
 *     organisations across 17 industries. Primary research.
 *  3. IBM / Ponemon 2025 (same report) — shadow-AI breach-cost premium.
 *  4. Gravitee "State of AI Agent Security" 2026 — 919 executives & practitioners.
 *     Vendor-commissioned survey; hedged accordingly.
 */

const STATS = [
  {
    metric: "~4 in 5",
    label: "enterprises have no mature AI governance",
    detail: "no boundaries, monitoring, or audit trails for agents",
    source: "Deloitte State of AI in the Enterprise, 2026",
    sourceType: "primary survey · 3,235 leaders · 24 countries",
    hedged: false,
  },
  {
    metric: "97%",
    label: "of AI-related breaches had zero access controls",
    detail: "agents that caused a breach were ungoverned",
    source: "IBM / Ponemon Cost of a Data Breach Report, 2025",
    sourceType: "primary research · 600 organisations",
    hedged: false,
  },
  {
    metric: "+$670K",
    label: "added to average breach cost by shadow AI",
    detail: "unsanctioned AI tools used without IT oversight",
    source: "IBM / Ponemon Cost of a Data Breach Report, 2025",
    sourceType: "primary research · 600 organisations",
    hedged: false,
  },
  {
    metric: "88%",
    label: "of enterprises had an AI agent security incident",
    detail: "in the preceding twelve months",
    source: "Gravitee State of AI Agent Security, 2026",
    sourceType: "vendor survey · 919 executives & practitioners",
    hedged: true,
  },
] as const;

export function StatsStrip() {
  return (
    <section
      aria-label="AI agent risk statistics"
      className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-10"
    >
      <div className="mx-auto max-w-6xl">
        {/* Eyebrow */}
        <p className="mb-8 text-center text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--muted)]">
          By the numbers — the governance gap is real
        </p>

        <div className="grid grid-cols-1 divide-y divide-[var(--border)] sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
          {STATS.map((s, i) => (
            <div
              key={i}
              className="flex flex-col items-center px-6 py-5 text-center first:pt-0 last:pb-0 sm:first:pt-5 sm:last:pb-5 lg:py-0"
            >
              {/* Large metric */}
              <span className="bg-gradient-to-r from-[var(--accent)] via-emerald-300 to-[var(--accent)] bg-clip-text text-4xl font-black leading-none tracking-tight text-transparent sm:text-5xl">
                {s.metric}
              </span>

              {/* Label */}
              <p className="mt-2.5 text-sm font-semibold leading-snug text-[var(--foreground)]">
                {s.hedged ? `reported: ${s.label}` : s.label}
              </p>

              {/* Detail */}
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                {s.detail}
              </p>

              {/* Source attribution */}
              <div className="mt-3 space-y-0.5">
                <p className="text-[10px] font-medium text-[var(--muted)]/70">
                  {s.source}
                </p>
                <p className="text-[10px] italic text-[var(--muted)]/50">
                  {s.sourceType}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
