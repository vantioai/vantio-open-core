// Animated "living dashboard" — a stylized, on-brand mock of the Vantio
// telemetry view, used as the hero focal piece. 100% synthetic sample data (no
// real metrics, no social-proof numbers; counts are modest + illustrative).
// Pure CSS/SVG animation (no JS, no deps) — all keyframes live in globals.css
// and self-disable under prefers-reduced-motion, where this renders as a clean,
// fully-populated static state. Decorative → aria-hidden.

type Tone = "allowed" | "redacted" | "blocked";

interface EventItem {
  t: string;
  host: string;
  action: string;
  tone: Tone;
}

const EVENTS: EventItem[] = [
  { t: "09:42:18", host: "api.openai.com", action: "ALLOWED", tone: "allowed" },
  { t: "09:42:14", host: "api.stripe.com", action: "ALLOWED", tone: "allowed" },
  { t: "09:42:09", host: "log.acme.io", action: "REDACTED", tone: "redacted" },
  { t: "09:42:03", host: "scraper.unknown.tld", action: "BLOCKED_HOST", tone: "blocked" },
  { t: "09:41:57", host: "api.anthropic.com", action: "ALLOWED", tone: "allowed" },
  { t: "09:41:52", host: "vault.acme.io", action: "ALLOWED", tone: "allowed" },
];

const TONE_BADGE: Record<Tone, string> = {
  allowed: "bg-[var(--accent)]/10 text-[var(--accent)]",
  redacted: "bg-amber-400/10 text-amber-400",
  blocked: "bg-red-500/15 text-red-400",
};

const BARS = [10, 15, 9, 18, 13, 21, 12, 17];

function EventRow({ e }: { e: EventItem }) {
  return (
    <div
      className={`flex items-center justify-between gap-3 px-3 py-2 ${
        e.tone === "blocked" ? "dv-flash rounded-lg bg-red-500/10" : ""
      }`}
    >
      <div className="flex min-w-0 items-center gap-2.5">
        <span className="font-mono text-[10px] text-[var(--muted)]">{e.t}</span>
        <span className="truncate font-mono text-xs text-[var(--foreground)]/80">{e.host}</span>
      </div>
      <span className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-bold ${TONE_BADGE[e.tone]}`}>
        {e.action}
      </span>
    </div>
  );
}

export function DashboardVisual() {
  return (
    <div
      aria-hidden="true"
      className="mx-auto w-full max-w-md overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 shadow-2xl shadow-black/40 backdrop-blur-xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2.5">
          <span className="dv-live h-2 w-2 rounded-full bg-[var(--accent)]" />
          <span className="text-xs font-semibold text-[var(--foreground)]">Agent telemetry</span>
          <span className="text-[10px] font-medium uppercase tracking-widest text-[var(--accent)]">Live</span>
        </div>
        <span className="rounded-full border border-[var(--border-2)] bg-[var(--surface-2)] px-2.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">
          acme-corp · PRO
        </span>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 gap-3 p-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-3">
          <p className="text-[10px] font-medium uppercase tracking-widest text-[var(--muted)]">Actions enforced</p>
          <p className="dv-counter mt-1 font-mono text-2xl font-bold text-[var(--foreground)]" />
          <p className="mt-0.5 text-[10px] text-[var(--muted)]">today</p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-3">
          <p className="text-[10px] font-medium uppercase tracking-widest text-[var(--muted)]">Throughput</p>
          <div className="mt-2 flex h-9 items-end gap-1">
            {BARS.map((h, i) => (
              <span
                key={i}
                className="dv-bar w-1.5 rounded-sm bg-[var(--accent)]/55"
                style={{ height: `${h}px`, animationDelay: `${i * 0.18}s` }}
              />
            ))}
          </div>
          <p className="mt-1.5 text-[10px] text-[var(--muted)]">
            <span className="font-semibold text-red-400">7</span> blocked
          </p>
        </div>
      </div>

      {/* Redaction micro-moment */}
      <div className="mx-4 mb-3 flex items-center justify-between gap-3 rounded-xl border border-amber-400/20 bg-amber-400/5 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgb(251 191 36)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z" />
          </svg>
          <span className="relative inline-block font-mono text-xs">
            <span className="dv-redact-from text-[var(--foreground)]/80">jane@acme.io</span>
            <span className="dv-redact-to absolute inset-0 text-amber-400">[REDACTED]</span>
          </span>
        </div>
        <span className="shrink-0 rounded-md bg-amber-400/10 px-2 py-0.5 text-[10px] font-bold text-amber-400">PII</span>
      </div>

      {/* Streaming event feed (seamless marquee: rows rendered twice) */}
      <div className="relative h-[164px] overflow-hidden border-t border-[var(--border)] px-1 py-1">
        <div className="dv-track">
          {[...EVENTS, ...EVENTS].map((e, i) => (
            <EventRow key={i} e={e} />
          ))}
        </div>
        <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-[var(--surface)] to-transparent" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-[var(--surface)] to-transparent" />
      </div>
    </div>
  );
}
