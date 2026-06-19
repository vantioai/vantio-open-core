import { NextResponse } from "next/server";
import { SITE } from "@/lib/seo";
import { getAllPosts } from "@/lib/brief";

function escapeXml(raw: string): string {
  return raw
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET() {
  const posts = getAllPosts();

  const items = posts
    .map((post) => {
      const url = `${SITE.url}/brief/${post.slug}`;
      const pubDate = new Date(`${post.date}T00:00:00Z`).toUTCString();
      return `    <item>
      <title>${escapeXml(post.title)}</title>
      <link>${url}</link>
      <guid isPermaLink="true">${url}</guid>
      <description>${escapeXml(post.excerpt)}</description>
      <pubDate>${pubDate}</pubDate>
      <dc:creator>${escapeXml(post.author)}</dc:creator>
      <category>${escapeXml(post.category)}</category>
    </item>`;
    })
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:dc="http://purl.org/dc/elements/1.1/">
  <channel>
    <title>${escapeXml(`The Brief — ${SITE.name}`)}</title>
    <link>${SITE.url}/brief</link>
    <description>Field notes on autonomous AI agents — cost, reliability, security, and governance. Grounded in what's actually happening in production.</description>
    <language>en-us</language>
    <atom:link href="${SITE.url}/brief/feed.xml" rel="self" type="application/rss+xml" />
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <managingEditor>hello@vantio.ai (${SITE.name})</managingEditor>
    <webMaster>hello@vantio.ai (${SITE.name})</webMaster>
${items}
  </channel>
</rss>`;

  return new NextResponse(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}
