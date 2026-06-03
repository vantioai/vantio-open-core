// Pure-CSS animated containment diagram — no JS, no deps, server-rendered.
// A glowing emerald boundary holds a small agent cluster; allowed egress dots
// flow OUT through the ring while one rogue (red) request is severed at the
// boundary. Every animation is a CSS keyframe defined in globals.css that
// self-disables under prefers-reduced-motion. Decorative → aria-hidden.

// Angles (degrees, 0° = →) for the allowed egress channels.
const ALLOWED = [-34, 6, 38, 74];
// One rogue channel pointing down-left.
const BLOCKED = 202;

export function ContainmentVisual() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-md" aria-hidden="true">
      {/* ambient glow */}
      <div className="pointer-events-none absolute inset-[10%] rounded-full bg-[var(--accent)]/10 blur-3xl" />

      {/* boundary ring (solid glowing + dashed inner) */}
      <div className="cv-ring absolute left-1/2 top-1/2 h-[64%] w-[64%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-[var(--accent)]/50" />
      <div className="absolute left-1/2 top-1/2 h-[64%] w-[64%] -translate-x-1/2 -translate-y-1/2 rounded-full border border-dashed border-[var(--accent)]/20" />

      {/* allowed egress channels (faint tracks + flowing green dots) */}
      {ALLOWED.map((deg, i) => (
        <div
          key={deg}
          className="absolute left-1/2 top-1/2 h-px w-1/2 origin-left"
          style={{ transform: `rotate(${deg}deg)` }}
        >
          <div className="h-px w-full bg-gradient-to-r from-[var(--accent)]/0 via-[var(--accent)]/20 to-[var(--accent)]/0" />
          <span
            className="cv-flow absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-[var(--accent)] shadow-[0_0_10px_var(--accent-glow)]"
            style={{ animationDelay: `${i * 0.8}s` }}
          />
        </div>
      ))}

      {/* rogue request channel (red track, dot blocked at boundary, sever X) */}
      <div
        className="absolute left-1/2 top-1/2 h-px w-1/2 origin-left"
        style={{ transform: `rotate(${BLOCKED}deg)` }}
      >
        <div className="h-px w-full bg-gradient-to-r from-red-500/0 via-red-500/30 to-red-500/0" />
        <span className="cv-blocked absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-red-500 shadow-[0_0_10px_rgba(239,68,68,0.6)]" />
        <span className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: "62%" }}>
          <span className="cv-sever block">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="rgb(248 113 113)" strokeWidth="2" strokeLinecap="round">
              <line x1="4" y1="4" x2="12" y2="12" />
              <line x1="12" y1="4" x2="4" y2="12" />
            </svg>
          </span>
        </span>
      </div>

      {/* agent cluster (core) */}
      <div className="cv-core absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
        <svg width="104" height="104" viewBox="0 0 104 104" fill="none">
          <g stroke="var(--accent)" strokeOpacity="0.35" strokeWidth="1">
            <line x1="52" y1="52" x2="30" y2="34" />
            <line x1="52" y1="52" x2="76" y2="32" />
            <line x1="52" y1="52" x2="32" y2="74" />
            <line x1="52" y1="52" x2="74" y2="72" />
          </g>
          {[
            [52, 52, 10, 0.9],
            [30, 34, 6, 0.6],
            [76, 32, 6, 0.6],
            [32, 74, 6, 0.6],
            [74, 72, 6, 0.6],
          ].map(([x, y, r, op], i) => (
            <g key={i}>
              <circle cx={x} cy={y} r={(r as number) + 3} fill="var(--accent)" fillOpacity="0.08" />
              <circle cx={x} cy={y} r={r as number} fill="none" stroke="var(--accent)" strokeOpacity={op as number} strokeWidth="1.5" />
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
