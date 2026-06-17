import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SITE, organizationJsonLd, softwareApplicationJsonLd } from "@/lib/seo";
import { Logo } from "@/components/logo";
import { Nav } from "@/components/nav";

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
  icons: { icon: "/logo.png", apple: "/logo.png" },
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
        {/* Without JS the scroll-reveal class never flips — keep content visible. */}
        <noscript dangerouslySetInnerHTML={{
          __html: "<style>.reveal-hidden{opacity:1 !important;transform:none !important;}</style>",
        }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Nav />

        <div className="pt-20">{children}</div>

        {/* Footer */}
        <footer className="relative mt-24 border-t border-[var(--border)] bg-[var(--surface)]">
          <div className="mx-auto max-w-7xl px-6 py-16">
            <div className="flex flex-col gap-10 md:flex-row md:justify-between">
              <div className="max-w-xs">
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
                    <Logo size={18} />
                  </span>
                  <span className="font-semibold tracking-wider">VANTIO</span>
                </div>
                <p className="text-xs leading-relaxed text-[var(--muted)]">
                  Physics-based AI governance.<br />Delaware C-Corporation.
                </p>
              </div>
              <div className="flex flex-wrap gap-10 text-sm">
                {[
                  { heading: "Product",   links: [["/developers","Developers"],["/pro","Pro"],["/enterprise","Enterprise"],["/pricing","Pricing"]] },
                  { heading: "Resources", links: [["/architecture","Architecture"],["/brief","The Brief"],["https://github.com/vantioai/vantio-open-core","GitHub"]] },
                  { heading: "Company",   links: [["/trust","Trust Center"],["/dashboard","Dashboard"]] },
                  { heading: "Legal",     links: [["/privacy","Privacy Policy"],["/terms","Terms of Service"]] },
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
