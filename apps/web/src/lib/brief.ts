// The Brief — typed, zero-dependency content collection. Each post is one file
// under lib/brief/posts/*.ts, registered in POSTS below. Everything is plain
// data (no JSX) so it stays fully static/prerenderable; rendering lives in
// <Prose>. Body is an array of typed blocks; block text supports a small inline
// markdown subset (**bold**, `code`, [text](url)) parsed in the Prose renderer.

export type Category = "Market" | "Deep Dive" | "Guide";
export const CATEGORIES: Category[] = ["Market", "Deep Dive", "Guide"];

export type CoverTheme = "emerald" | "blue" | "red" | "violet" | "amber";

export type Block =
  | { k: "p"; t: string }
  | { k: "h2"; t: string }
  | { k: "h3"; t: string }
  | { k: "ul"; items: string[] }
  | { k: "quote"; t: string; cite?: string };

export interface Source {
  label: string;
  url: string;
}

export interface Post {
  slug: string;
  title: string;
  excerpt: string;
  category: Category;
  author: string;
  authorRole: string;
  date: string; // ISO yyyy-mm-dd
  cover: CoverTheme;
  featured?: boolean;
  /** Which tier the closing CTA points at. */
  tierCta: "developers" | "pro" | "enterprise";
  body: Block[];
  sources?: Source[];
}

import { post as p47k } from "@/lib/brief/posts/the-47000-dollar-agent";
import { post as pLoops } from "@/lib/brief/posts/coding-agents-stuck-in-loops";
import { post as pShadow } from "@/lib/brief/posts/shadow-agents-new-shadow-it";
import { post as pAudit } from "@/lib/brief/posts/audit-trail-for-ai-agents";
import { post as pLing } from "@/lib/brief/posts/linguistics-cannot-secure-compute";
import { post as pLedger } from "@/lib/brief/posts/the-cryptographic-anomaly-record";
import { post as pProducts } from "@/lib/brief/posts/hot-agent-products-2026";
import { post as pNineSec } from "@/lib/brief/posts/it-deleted-the-database-in-nine-seconds";
import { post as pPhysical } from "@/lib/brief/posts/governing-agents-in-the-physical-world";
import { post as pControl } from "@/lib/brief/posts/control-not-capability";
import { post as pComputer } from "@/lib/brief/posts/computer-use-agents-prompt-injection";
import { post as pMcp } from "@/lib/brief/posts/mcp-tool-supply-chain-risk";
import { post as pEuAct } from "@/lib/brief/posts/eu-ai-act-omnibus-june-2026";
import { post as pPermissions } from "@/lib/brief/posts/agents-inherit-your-permission-debt";

const POSTS: Post[] = [
  p47k, pLoops, pShadow, pAudit, pLing, pLedger,
  pProducts, pNineSec, pPhysical, pControl,
  pComputer, pMcp, pEuAct, pPermissions,
];

/** All posts, newest first. */
export function getAllPosts(): Post[] {
  return [...POSTS].sort((a, b) => (a.date < b.date ? 1 : -1));
}

export function getPost(slug: string): Post | undefined {
  return POSTS.find((x) => x.slug === slug);
}

export function getFeatured(): Post {
  return getAllPosts().find((x) => x.featured) ?? getAllPosts()[0];
}

/** Up to `n` related posts: same category first, then most recent. */
export function getRelated(slug: string, n = 2): Post[] {
  const current = getPost(slug);
  const rest = getAllPosts().filter((x) => x.slug !== slug);
  if (!current) return rest.slice(0, n);
  const sameCat = rest.filter((x) => x.category === current.category);
  const others = rest.filter((x) => x.category !== current.category);
  return [...sameCat, ...others].slice(0, n);
}

function wordCount(post: Post): number {
  let words = 0;
  for (const b of post.body) {
    if (b.k === "ul") words += b.items.join(" ").split(/\s+/).length;
    else words += b.t.split(/\s+/).length;
  }
  return words;
}

/** Estimated reading time in whole minutes (~220 wpm, floor 1). */
export function readingMinutes(post: Post): number {
  return Math.max(1, Math.round(wordCount(post) / 220));
}

export function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}
