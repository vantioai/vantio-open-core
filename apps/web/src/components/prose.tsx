import type { ReactNode } from "react";
import type { Block } from "@/lib/brief";

// Render a small inline-markdown subset: **bold**, `code`, [text](url).
function inline(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let key = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      nodes.push(
        <strong key={key++} className="font-semibold text-[var(--foreground)]">{m[1]}</strong>
      );
    } else if (m[2] !== undefined) {
      nodes.push(
        <code key={key++} className="rounded bg-[var(--surface-2)] px-1.5 py-0.5 font-mono text-[0.85em] text-[var(--accent)]">{m[2]}</code>
      );
    } else if (m[3] !== undefined) {
      const href = m[4];
      const external = /^https?:\/\//.test(href);
      nodes.push(
        <a
          key={key++}
          href={href}
          {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
          className="font-medium text-[var(--accent)] underline decoration-[var(--accent)]/30 underline-offset-2 transition-colors hover:decoration-[var(--accent)]"
        >
          {m[3]}
        </a>
      );
    }
    last = re.lastIndex;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Prose({ blocks }: { blocks: Block[] }) {
  return (
    <div className="space-y-5">
      {blocks.map((b, i) => {
        switch (b.k) {
          case "h2":
            return (
              <h2 key={i} className="scroll-mt-24 pt-5 text-2xl font-bold tracking-tight text-[var(--foreground)]">
                {inline(b.t)}
              </h2>
            );
          case "h3":
            return (
              <h3 key={i} className="pt-3 text-lg font-bold text-[var(--foreground)]">
                {inline(b.t)}
              </h3>
            );
          case "ul":
            return (
              <ul key={i} className="space-y-2.5">
                {b.items.map((it, j) => (
                  <li key={j} className="flex gap-3 text-[15px] leading-relaxed text-[var(--muted)] sm:text-base">
                    <span className="mt-0.5 shrink-0 text-[var(--accent)]">→</span>
                    <span>{inline(it)}</span>
                  </li>
                ))}
              </ul>
            );
          case "quote":
            return (
              <blockquote key={i} className="border-l-2 border-[var(--accent)]/50 pl-5">
                <p className="text-lg font-medium italic leading-relaxed text-[var(--foreground)]">{inline(b.t)}</p>
                {b.cite && <cite className="mt-2 block text-xs not-italic text-[var(--muted)]">— {b.cite}</cite>}
              </blockquote>
            );
          default:
            return (
              <p key={i} className="text-[15px] leading-relaxed text-[var(--muted)] sm:text-base">
                {inline(b.t)}
              </p>
            );
        }
      })}
    </div>
  );
}
