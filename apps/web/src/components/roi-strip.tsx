/**
 * Positive-outcome / ROI stats strip — what organizations GAIN from having
 * AI governance controls in place.
 *
 * Sources (in order):
 *  1. Databricks "2026 State of AI Agents" — telemetry across 20,000+ orgs including
 *     60%+ of the Fortune 500. Vendor data (Databricks sells governance tooling);
 *     cited via Dataiku analysis (Jun 2026). Marks governance-tool users vs. non-users.
 *     This is correlation data, not controlled experiment.
 *  2. Larridin "State of Enterprise AI" Q1 2026 — independent survey of 364 enterprise
 *     leaders. Compares orgs with formalized AI risk/compliance policies against those
 *     without. Not a vendor-commissioned survey.
 *  3. IBM / Ponemon "Cost of a Data Breach Report" 2025 — primary research across 600
 *     breached organisations in 17 industries. Compares breach costs for orgs with
 *     extensive AI + automation security controls vs. none.
 *  4. Gartner "Market Guide for AI Governance Platforms" Nov 2025 — Strategic Planning
 *     Assumption about governance tech and compliance cost reduction. Forward-looking
 *     analyst projection for 2028; hedged accordingly.
 */

const ROI_STATS = [
  {
    metric: "12×",
    label: "more AI projects ship to production",
    detail: "governed organizations vs. ungoverned peers",
    source: "Databricks 2026 State of AI Agents",
    sourceType: "vendor telemetry · 20,000+ orgs",
    hedged: true,
  },
  {
    metric: "2.2×",
    label: "more likely to demonstrate measurable ROI",
    detail: "with formalized AI risk & compliance policies",
    source: "Larridin State of Enterprise AI, Q1 2026",
    sourceType: "independent survey · 364 enterprise leaders",
    hedged: false,
  },
  {
    metric: "$1.9M",
    label: "average breach-cost savings",
    detail: "organizations with extensive AI security controls vs. none",
    source: "IBM / Ponemon Cost of a Data Breach Report, 2025",
    sourceType: "primary research · 600 orgs · 17 industries",
    hedged: false,
  },
  {
    metric: "−20%",
    label: "projected compliance-cost reduction",
    detail: "from governance technologies — Gartner SPA, by 2028",
    source: "Gartner Market Guide for AI Governance Platforms, Nov 2025",
    sourceType: "analyst projection",
    hedged: true,
  },
] as const;

export function RoiStrip() {
  return (
    <section
      aria-label="AI governance positive outcomes"
      className="border-y border-[var(--accent)]/20 bg-[var(--surface)] px-6 py-10"
    >
      <div className="mx-auto max-w-6xl">
        {/* Eyebrow */}
        <p className="mb-8 text-center text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
          What governance actually delivers
        </p>

        <div className="grid grid-cols-1 divide-y divide-[var(--border)] sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
          {ROI_STATS.map((s, i) => (
            <div
              key={i}
              className="flex flex-col items-center px-6 py-5 text-center first:pt-0 last:pb-0 sm:first:pt-5 sm:last:pb-5 lg:py-0"
            >
              {/* Large metric — solid emerald (positive, confident) */}
              <span className="text-4xl font-black leading-none tracking-tight text-[var(--accent)] sm:text-5xl">
                {s.metric}
              </span>

              {/* Label */}
              <p className="mt-2.5 text-sm font-semibold leading-snug text-[var(--foreground)]">
                {s.label}
              </p>

              {/* Detail */}
              <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">
                {s.detail}
              </p>

              {/* Source attribution */}
              <div className="mt-3 space-y-0.5">
                <p className="text-[10px] font-medium text-[var(--muted)]/70">
                  {s.hedged ? `${s.source}*` : s.source}
                </p>
                <p className="text-[10px] italic text-[var(--muted)]/50">
                  {s.sourceType}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Footnote for hedged stats */}
        <p className="mt-6 text-center text-[10px] text-[var(--muted)]/40">
          * Stats marked with an asterisk are vendor telemetry or analyst projections and should be read as directional indicators, not controlled-study results.
        </p>
      </div>
    </section>
  );
}
