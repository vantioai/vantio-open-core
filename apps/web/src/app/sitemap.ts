import type { MetadataRoute } from "next";
import { SITE } from "@/lib/seo";

/**
 * Public, indexable routes only. Private/transactional routes (dashboard,
 * success, login, auth, api) are intentionally excluded and also blocked in
 * robots.ts. Submit https://vantio.ai/sitemap.xml in Google Search Console.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const routes: { path: string; priority: number; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
    { path: "/", priority: 1.0, changeFrequency: "weekly" },
    { path: "/pricing", priority: 0.9, changeFrequency: "weekly" },
    { path: "/architecture", priority: 0.8, changeFrequency: "monthly" },
    { path: "/enterprise", priority: 0.8, changeFrequency: "monthly" },
    { path: "/pro", priority: 0.8, changeFrequency: "monthly" },
    { path: "/developers", priority: 0.8, changeFrequency: "monthly" },
    { path: "/research", priority: 0.7, changeFrequency: "weekly" },
    { path: "/trust", priority: 0.6, changeFrequency: "monthly" },
    { path: "/privacy", priority: 0.3, changeFrequency: "yearly" },
    { path: "/terms", priority: 0.3, changeFrequency: "yearly" },
  ];

  return routes.map(({ path, priority, changeFrequency }) => ({
    url: new URL(path, SITE.url).toString(),
    lastModified,
    changeFrequency,
    priority,
  }));
}
