"use client";

import { useState } from "react";
import Link from "next/link";
import { Cover } from "@/components/brief/cover";
import { Reveal } from "@/components/reveal";
import { CATEGORIES, type Category, type CoverTheme } from "@/lib/brief";

export interface CardItem {
  slug: string;
  title: string;
  excerpt: string;
  category: Category;
  author: string;
  date: string; // pre-formatted
  minutes: number;
  cover: CoverTheme;
}

const FILTERS: ("All" | Category)[] = ["All", ...CATEGORIES];

export function BriefIndex({ items }: { items: CardItem[] }) {
  const [active, setActive] = useState<"All" | Category>("All");
  const shown = active === "All" ? items : items.filter((i) => i.category === active);

  return (
    <div>
      <div className="mb-8 flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setActive(f)}
            aria-pressed={active === f}
            className={`rounded-full border px-4 py-1.5 text-xs font-semibold transition-colors ${
              active === f
                ? "border-[var(--accent)]/40 bg-[var(--accent)]/10 text-[var(--accent)]"
                : "border-[var(--border-2)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)]"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((i, idx) => (
          <Reveal key={i.slug} delayMs={(idx % 3) * 80} className="h-full">
            <Link
              href={`/brief/${i.slug}`}
              className="lift group flex h-full flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-2)]"
            >
              <Cover theme={i.cover} category={i.category} className="aspect-[16/9]" />
              <div className="flex flex-1 flex-col p-5">
                <div className="mb-2 flex items-center gap-2 text-[11px] text-[var(--muted)]">
                  <span>{i.date}</span>
                  <span aria-hidden="true">·</span>
                  <span>{i.minutes} min read</span>
                </div>
                <h3 className="text-base font-bold leading-snug text-[var(--foreground)] transition-colors group-hover:text-[var(--accent)]">
                  {i.title}
                </h3>
                <p className="mt-2 line-clamp-3 flex-1 text-sm leading-relaxed text-[var(--muted)]">{i.excerpt}</p>
                <p className="mt-4 text-xs text-[var(--muted)]">By {i.author}</p>
              </div>
            </Link>
          </Reveal>
        ))}
      </div>

      {shown.length === 0 && (
        <p className="text-sm text-[var(--muted)]">No posts in this category yet.</p>
      )}
    </div>
  );
}
