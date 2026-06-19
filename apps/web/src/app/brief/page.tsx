import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd, blogJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { getAllPosts, getFeatured, readingMinutes, formatDate } from "@/lib/brief";
import { Cover } from "@/components/brief/cover";
import { BriefIndex, type CardItem } from "@/components/brief/brief-index";
import { SubscribeForm } from "@/components/brief/subscribe-form";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = buildMetadata({
  title: "The Brief",
  description:
    "Field notes on autonomous AI agents — cost, reliability, security, and governance. Grounded in what's actually happening in production, written for the people shipping it.",
  path: "/brief",
  rssAlternate: "/brief/feed.xml",
});

export default function BriefHub() {
  const all = getAllPosts();
  const featured = getFeatured();
  const rest = all.filter((p) => p.slug !== featured.slug);

  const cards: CardItem[] = rest.map((p) => ({
    slug: p.slug,
    title: p.title,
    excerpt: p.excerpt,
    category: p.category,
    author: p.author,
    date: formatDate(p.date),
    minutes: readingMinutes(p),
    cover: p.cover,
  }));

  return (
    <main className="relative mx-auto max-w-6xl px-6 py-20">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "The Brief", path: "/brief" }])} />
      <JsonLd data={blogJsonLd(all.map((p) => ({ title: p.title, slug: p.slug, datePublished: p.date })))} />
      <div className="pointer-events-none absolute left-1/2 top-0 h-72 w-[640px] -translate-x-1/2 rounded-full bg-[var(--accent)]/5 blur-3xl" />

      <header className="relative mb-14">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">The Brief</p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Field notes on autonomous AI.</h1>
        <p className="mt-4 max-w-2xl text-lg text-[var(--muted)]">
          What agents actually do in production — where they burn money, where they leak, where they
          get stuck — and what to do about it. Grounded in real reporting, written by people shipping
          this stuff.
        </p>
      </header>

      {/* Featured */}
      <Reveal className="relative mb-16">
        <Link
          href={`/brief/${featured.slug}`}
          className="lift group grid overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-2)] md:grid-cols-2"
        >
          <Cover theme={featured.cover} category={featured.category} className="aspect-[16/10] md:aspect-auto md:h-full" />
          <div className="flex flex-col justify-center p-8">
            <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-widest text-[var(--muted)]">
              <span className="font-bold text-[var(--accent)]">Featured</span>
              <span aria-hidden="true">·</span>
              <span>{formatDate(featured.date)}</span>
              <span aria-hidden="true">·</span>
              <span>{readingMinutes(featured)} min read</span>
            </div>
            <h2 className="text-2xl font-bold leading-tight text-[var(--foreground)] transition-colors group-hover:text-[var(--accent)] sm:text-3xl">
              {featured.title}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--muted)] sm:text-base">{featured.excerpt}</p>
            <p className="mt-5 text-xs text-[var(--muted)]">
              By {featured.author} · {featured.authorRole}
            </p>
          </div>
        </Link>
      </Reveal>

      {/* Filterable grid */}
      <BriefIndex items={cards} />

      {/* Subscribe */}
      <section className="relative mt-20 overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 sm:p-10">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-[var(--accent)]/10 blur-3xl" />
        <div className="relative max-w-xl">
          <h2 className="text-2xl font-bold text-[var(--foreground)]">Subscribe to The Brief</h2>
          <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
            A new piece when we have something worth your time — no filler, no cadence quota. Just the
            signal on where agents are headed and how to keep yours in line.
          </p>
          <SubscribeForm source="brief" className="mt-5" />
        </div>
      </section>
    </main>
  );
}
