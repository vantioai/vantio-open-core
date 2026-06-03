import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SITE, buildMetadata, breadcrumbJsonLd, blogPostingJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { getAllPosts, getPost, getRelated, readingMinutes, formatDate } from "@/lib/brief";
import { Prose } from "@/components/prose";
import { Cover } from "@/components/brief/cover";
import { ShareBar } from "@/components/brief/share-bar";
import { SubscribeForm } from "@/components/brief/subscribe-form";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllPosts().map((p) => ({ slug: p.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return buildMetadata({ title: "The Brief", description: "Not found.", path: `/brief/${slug}`, noindex: true });
  return buildMetadata({ title: post.title, description: post.excerpt, path: `/brief/${slug}` });
}

const TIER_CTA: Record<string, { href: string; label: string; note: string; box: string; btn: string }> = {
  developers: {
    href: "/developers",
    label: "Start free with the Developer SDK",
    note: "See exactly what your agents do — free, no credit card.",
    box: "border-[var(--accent)]/25 bg-[var(--accent)]/5",
    btn: "bg-[var(--accent)] text-black hover:bg-[var(--accent-dim)]",
  },
  pro: {
    href: "/pricing",
    label: "Put real guardrails on your agents",
    note: "PII redaction, spend caps, and host blocking — live in under an hour.",
    box: "border-blue-400/30 bg-blue-400/5",
    btn: "bg-blue-500 text-white hover:bg-blue-400",
  },
  enterprise: {
    href: "/enterprise",
    label: "Talk to sales about Enterprise",
    note: "Kernel-level enforcement inside your own cloud, with audit-ready proof.",
    box: "border-red-400/30 bg-red-400/5",
    btn: "bg-red-500 text-white hover:bg-red-400",
  },
};

export default async function BriefArticle({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const url = new URL(`/brief/${post.slug}`, SITE.url).toString();
  const related = getRelated(post.slug, 2);
  const cta = TIER_CTA[post.tierCta];

  return (
    <main className="relative px-6 py-16">
      <JsonLd data={breadcrumbJsonLd([
        { name: "Home", path: "/" },
        { name: "The Brief", path: "/brief" },
        { name: post.title, path: `/brief/${post.slug}` },
      ])} />
      <JsonLd data={blogPostingJsonLd({
        title: post.title,
        description: post.excerpt,
        slug: post.slug,
        author: post.author,
        datePublished: post.date,
        section: post.category,
      })} />

      <div className="pointer-events-none absolute left-1/2 top-0 h-72 w-[680px] -translate-x-1/2 rounded-full bg-[var(--accent)]/5 blur-3xl" />

      <article className="relative mx-auto max-w-3xl">
        <Link href="/brief" className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)]">
          ← The Brief
        </Link>

        <div className="mt-5 flex items-center gap-2 text-[11px] uppercase tracking-widest text-[var(--muted)]">
          <span className="font-bold text-[var(--accent)]">{post.category}</span>
          <span aria-hidden="true">·</span>
          <span>{formatDate(post.date)}</span>
          <span aria-hidden="true">·</span>
          <span>{readingMinutes(post)} min read</span>
        </div>

        <h1 className="mt-3 text-3xl font-bold leading-tight tracking-tight text-[var(--foreground)] sm:text-4xl">
          {post.title}
        </h1>
        <p className="mt-4 text-lg leading-relaxed text-[var(--muted)]">{post.excerpt}</p>

        <div className="mt-6 flex items-center gap-3 border-y border-[var(--border)] py-4">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--accent)]/10 text-sm font-bold text-[var(--accent)]">
            {post.author.split(" ").map((w) => w[0]).join("").slice(0, 2)}
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">{post.author}</p>
            <p className="text-xs text-[var(--muted)]">{post.authorRole}</p>
          </div>
        </div>

        <Cover theme={post.cover} category={post.category} className="mt-8 aspect-[2/1] rounded-2xl border border-[var(--border)]" />

        <div className="mt-10">
          <Prose blocks={post.body} />
        </div>

        {post.sources && post.sources.length > 0 && (
          <div className="mt-12 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Sources</p>
            <ul className="space-y-2">
              {post.sources.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="text-sm text-[var(--accent)] underline decoration-[var(--accent)]/30 underline-offset-2 hover:decoration-[var(--accent)]">
                    {s.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-10 border-t border-[var(--border)] pt-6">
          <ShareBar url={url} title={post.title} />
        </div>

        {/* Tier CTA */}
        <div className={`mt-12 rounded-2xl border ${cta.box} p-7 text-center`}>
          <p className="text-sm text-[var(--muted)]">{cta.note}</p>
          <Link href={cta.href} className={`mt-4 inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-bold transition-all ${cta.btn}`}>
            {cta.label} →
          </Link>
        </div>

        {/* Subscribe */}
        <div className="mt-12 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-7">
          <h2 className="text-lg font-bold text-[var(--foreground)]">Get the next one</h2>
          <p className="mt-1.5 text-sm text-[var(--muted)]">Subscribe to The Brief — occasional, signal-only.</p>
          <SubscribeForm source="article" className="mt-4" />
        </div>
      </article>

      {/* Related */}
      {related.length > 0 && (
        <section className="relative mx-auto mt-20 max-w-5xl">
          <h2 className="mb-6 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Keep reading</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {related.map((r) => (
              <Link
                key={r.slug}
                href={`/brief/${r.slug}`}
                className="lift group flex flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-2)]"
              >
                <Cover theme={r.cover} category={r.category} className="aspect-[16/9]" />
                <div className="p-5">
                  <div className="mb-2 text-[11px] text-[var(--muted)]">{formatDate(r.date)} · {readingMinutes(r)} min read</div>
                  <h3 className="text-base font-bold leading-snug text-[var(--foreground)] transition-colors group-hover:text-[var(--accent)]">{r.title}</h3>
                  <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-[var(--muted)]">{r.excerpt}</p>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
