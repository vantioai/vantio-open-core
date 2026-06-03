import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { SITE, organizationJsonLd, softwareApplicationJsonLd } from "@/lib/seo";
import { MobileNav } from "@/components/mobile-nav";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: {
    default: SITE.defaultTitle,
    template: "%s — Vantio AI",
  },
  description: SITE.defaultDescription,
  applicationName: SITE.name,
  authors: [{ name: "Vantio AI, Inc.", url: SITE.url }],
  creator: "Vantio AI, Inc.",
  publisher: "Vantio AI, Inc.",
  category: "technology",
  keywords: [
    "AI governance",
    "AI agent security",
    "AI agent monitoring",
    "AI compliance",
    "agent observability",
    "LLM security",
    "AI audit trail",
    "data exfiltration prevention",
    "AI agent guardrails",
  ],
  alternates: { canonical: "/" },
  formatDetection: { email: false, address: false, telephone: false },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  openGraph: {
    type: "website",
    siteName: SITE.name,
    locale: SITE.locale,
    url: SITE.url,
    title: SITE.defaultTitle,
    description: SITE.defaultDescription,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE.defaultTitle,
    description: SITE.defaultDescription,
  },
};

export const viewport: Viewport = {
  themeColor: "#030305",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <script type="application/ld+json" dangerouslySetInnerHTML={{
          __html: JSON.stringify(organizationJsonLd()),
        }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{
          __html: JSON.stringify(softwareApplicationJsonLd()),
        }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* Nav */}
        <nav className="fixed top-0 z-50 w-full">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            {/* Frosted glass pill */}
            <div className="relative flex w-full items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 px-5 py-2.5 shadow-lg shadow-black/20 backdrop-blur-xl">
              <Link href="/" className="flex items-center gap-2.5 font-bold tracking-tight">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-sm font-black text-[var(--accent)]">∅</span>
                <span className="text-sm font-semibold tracking-wider text-[var(--foreground)]">VANTIO</span>
              </Link>
              <div className="hidden items-center gap-1 md:flex">
                {[
                  ["/architecture", "Architecture"],
                  ["/pricing",      "Pricing"],
                  ["/enterprise",   "Enterprise"],
                  ["/pro",          "Pro"],
                  ["/developers",   "Developers"],
                  ["/research",     "Research"],
                ].map(([href, label]) => (
                  <a key={href} href={href}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-[var(--muted)] transition-all hover:bg-white/5 hover:text-[var(--foreground)]">
                    {label}
                  </a>
                ))}
              </div>
              <a href="/dashboard"
                className="hidden md:inline-flex items-center rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] px-4 py-1.5 text-xs font-semibold text-[var(--foreground)] transition-all hover:border-[var(--accent)]/40 hover:text-[var(--accent)]">
                Dashboard
              </a>
              <MobileNav />
            </div>
          </div>
        </nav>

        <div className="pt-20">{children}</div>

        {/* Footer */}
        <footer className="relative mt-24 border-t border-[var(--border)] bg-[var(--surface)]">
          <div className="mx-auto max-w-7xl px-6 py-16">
            <div className="flex flex-col gap-10 md:flex-row md:justify-between">
              <div className="max-w-xs">
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-sm font-black text-[var(--accent)]">∅</span>
                  <span className="font-semibold tracking-wider">VANTIO</span>
                </div>
                <p className="text-xs leading-relaxed text-[var(--muted)]">
                  Physics-based AI governance.<br />Delaware C-Corporation.
                </p>
              </div>
              <div className="flex flex-wrap gap-10 text-sm">
                {[
                  { heading: "Product", links: [["/architecture","Architecture"],["/pricing","Pricing"],["/developers","Developers"],["/research","Research"]] },
                  { heading: "Company", links: [["/trust","Trust Center"],["/enterprise","Enterprise"],["https://github.com/vantioai/vantio-open-core","GitHub"],["/dashboard","Dashboard"]] },
                  { heading: "Legal",   links: [["/privacy","Privacy Policy"],["/terms","Terms of Service"]] },
                ].map(({ heading, links }) => (
                  <div key={heading} className="space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">{heading}</p>
                    {links.map(([href, label]) => (
                      <a key={href} href={href}
                        className="block text-xs text-[var(--muted)] transition-colors hover:text-[var(--foreground)]">
                        {label}
                      </a>
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-12 flex items-center justify-between border-t border-[var(--border)] pt-6 text-xs text-[var(--muted)]">
              <span>© 2026 Vantio AI, Inc. All rights reserved.</span>
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" />
                All systems operational
              </span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
