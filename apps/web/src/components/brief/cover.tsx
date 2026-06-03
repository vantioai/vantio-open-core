import type { Category, CoverTheme } from "@/lib/brief";

// Code-built covers — gradient base + a per-category SVG motif (no images, no
// deps). The motif is keyed off `category`; its color comes from the post's
// `theme`. Drawn in a 400×225 viewBox with `slice` so it fills both the large
// article cover (2:1) and the small card thumbnails (16:9) without overflow.
const THEME: Record<CoverTheme, { grad: string; glow: string; text: string; border: string }> = {
  emerald: { grad: "from-[var(--accent)]/25", glow: "bg-[var(--accent)]/20", text: "text-[var(--accent)]", border: "border-[var(--accent)]/30" },
  blue:    { grad: "from-blue-500/25",         glow: "bg-blue-500/20",        text: "text-blue-400",        border: "border-blue-400/30" },
  red:     { grad: "from-red-500/25",          glow: "bg-red-500/20",         text: "text-red-400",         border: "border-red-400/30" },
  violet:  { grad: "from-violet-500/25",       glow: "bg-violet-500/20",      text: "text-violet-300",      border: "border-violet-400/30" },
  amber:   { grad: "from-amber-400/25",        glow: "bg-amber-400/20",       text: "text-amber-400",       border: "border-amber-400/30" },
};

// Market → rising bars + a spend curve trending up.
function MarketMotif() {
  const bars = [
    { x: 56, top: 150 }, { x: 104, top: 134 }, { x: 152, top: 118 },
    { x: 200, top: 98 }, { x: 248, top: 78 }, { x: 296, top: 56 },
  ];
  return (
    <>
      <line x1="40" y1="180" x2="364" y2="180" strokeOpacity="0.18" strokeWidth="1.5" />
      {bars.map((b) => (
        <rect key={b.x} x={b.x} y={b.top} width="28" height={180 - b.top} rx="2" fill="currentColor" fillOpacity="0.12" strokeOpacity="0.3" strokeWidth="1" />
      ))}
      <path d="M48 168 C 130 150, 200 120, 270 90 S 348 58, 362 48" strokeOpacity="0.75" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx="362" cy="48" r="11" fill="currentColor" fillOpacity="0.15" />
      <circle cx="362" cy="48" r="5" fill="currentColor" />
    </>
  );
}

// Guide → a connected path of ringed step-nodes, each with a check.
function GuideMotif() {
  const nodes = [92, 206, 320];
  return (
    <>
      {/* connectors between ring edges (radius 20) */}
      <line x1="112" y1="112" x2="186" y2="112" strokeOpacity="0.22" strokeWidth="2" />
      <line x1="226" y1="112" x2="300" y2="112" strokeOpacity="0.22" strokeWidth="2" />
      {nodes.map((cx) => (
        <g key={cx}>
          <circle cx={cx} cy="112" r="20" strokeOpacity="0.5" strokeWidth="2" />
          <circle cx={cx} cy="112" r="20" fill="currentColor" fillOpacity="0.05" />
          <polyline
            points={`${cx - 8},112 ${cx - 2},118 ${cx + 9},105`}
            strokeOpacity="0.85"
            strokeWidth="2.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
      ))}
    </>
  );
}

// Deep Dive → concentric containment rings + circuit traces (homepage echo).
function DeepDiveMotif() {
  const cx = 196;
  const cy = 112;
  return (
    <>
      <circle cx={cx} cy={cy} r="66" strokeOpacity="0.14" strokeWidth="1.5" strokeDasharray="3 7" />
      <circle cx={cx} cy={cy} r="44" strokeOpacity="0.3" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r="22" strokeOpacity="0.6" strokeWidth="2" />
      <circle cx={cx} cy={cy} r="6" fill="currentColor" />
      {/* circuit traces with terminal nodes */}
      <path d="M218 100 H 296 V 58" strokeOpacity="0.4" strokeWidth="1.5" />
      <rect x="291" y="53" width="10" height="10" rx="1.5" fill="currentColor" fillOpacity="0.8" />
      <path d="M262 112 H 366" strokeOpacity="0.4" strokeWidth="1.5" />
      <rect x="361" y="107" width="10" height="10" rx="1.5" fill="currentColor" fillOpacity="0.8" />
      <path d="M218 126 H 316 V 172" strokeOpacity="0.4" strokeWidth="1.5" />
      <rect x="311" y="167" width="10" height="10" rx="1.5" fill="currentColor" fillOpacity="0.8" />
      <path d="M174 112 H 64" strokeOpacity="0.4" strokeWidth="1.5" />
      <rect x="55" y="107" width="10" height="10" rx="1.5" fill="currentColor" fillOpacity="0.8" />
    </>
  );
}

// Fallback → a small constellation / node graph.
function DefaultMotif() {
  const cx = 200;
  const cy = 112;
  const sats = [
    [120, 68], [292, 78], [148, 168], [300, 158],
  ];
  return (
    <>
      <circle cx={cx} cy={cy} r="42" strokeOpacity="0.18" strokeWidth="1.5" />
      {sats.map(([x, y]) => (
        <line key={`${x}-${y}`} x1={cx} y1={cy} x2={x} y2={y} strokeOpacity="0.22" strokeWidth="1.5" />
      ))}
      {sats.map(([x, y]) => (
        <circle key={`d-${x}-${y}`} cx={x} cy={y} r="3.5" fill="currentColor" fillOpacity="0.7" />
      ))}
      <circle cx={cx} cy={cy} r="5.5" fill="currentColor" />
    </>
  );
}

function Motif({ category }: { category: Category }) {
  switch (category) {
    case "Market":
      return <MarketMotif />;
    case "Guide":
      return <GuideMotif />;
    case "Deep Dive":
      return <DeepDiveMotif />;
    default:
      return <DefaultMotif />;
  }
}

export function Cover({
  theme,
  category,
  className = "",
}: {
  theme: CoverTheme;
  category: Category;
  className?: string;
}) {
  const t = THEME[theme];
  return (
    <div className={`dot-grid relative overflow-hidden bg-gradient-to-br ${t.grad} via-[var(--surface)] to-[var(--surface)] ${className}`}>
      <div className={`pointer-events-none absolute -right-12 -top-12 h-44 w-44 rounded-full ${t.glow} blur-3xl`} />

      {/* Category-themed coded motif — scales/crops cleanly via slice. */}
      <svg
        viewBox="0 0 400 225"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
        stroke="currentColor"
        aria-hidden="true"
        className={`pointer-events-none absolute inset-0 h-full w-full ${t.text}`}
      >
        <Motif category={category} />
      </svg>

      {/* soften the bottom for label legibility */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[var(--surface)]/70 to-transparent" />

      <span className={`absolute left-4 top-4 rounded-full border ${t.border} bg-[var(--background)]/50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${t.text} backdrop-blur-sm`}>
        {category}
      </span>
    </div>
  );
}
