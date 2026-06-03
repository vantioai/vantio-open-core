import type { Category, CoverTheme } from "@/lib/brief";

// Code-built gradient/pattern cover — no images. Used on cards and article
// heroes. Theme classes are literal so Tailwind's static scanner emits them.
const THEME: Record<CoverTheme, { grad: string; glow: string; text: string; border: string }> = {
  emerald: { grad: "from-[var(--accent)]/25", glow: "bg-[var(--accent)]/20", text: "text-[var(--accent)]", border: "border-[var(--accent)]/30" },
  blue:    { grad: "from-blue-500/25",         glow: "bg-blue-500/20",        text: "text-blue-400",        border: "border-blue-400/30" },
  red:     { grad: "from-red-500/25",          glow: "bg-red-500/20",         text: "text-red-400",         border: "border-red-400/30" },
  violet:  { grad: "from-violet-500/25",       glow: "bg-violet-500/20",      text: "text-violet-300",      border: "border-violet-400/30" },
  amber:   { grad: "from-amber-400/25",        glow: "bg-amber-400/20",       text: "text-amber-400",       border: "border-amber-400/30" },
};

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
      <span className={`absolute left-4 top-4 rounded-full border ${t.border} bg-[var(--background)]/50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest ${t.text} backdrop-blur-sm`}>
        {category}
      </span>
      <span className={`pointer-events-none absolute -bottom-3 right-3 text-7xl font-black opacity-15 ${t.text}`} aria-hidden="true">∅</span>
    </div>
  );
}
