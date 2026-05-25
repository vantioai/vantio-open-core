import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Vantio AI — Know What Your AI Agents Are Doing",
  description:
    "AI agents make decisions and take actions you can't see. Vantio watches every move, stops unauthorized behavior instantly, and creates a tamper-proof record you can hand to an auditor.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <script type="application/ld+json" dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Corporation",
            "name": "Vantio AI, Inc.",
            "foundingLocation": "Delaware",
            "url": "https://vantio.ai",
          }),
        }} />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        {/* Nav */}
        <nav className="fixed top-0 z-50 w-full">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            {/* Frosted glass pill */}
            <div className="flex w-full items-center justify-between rounded-2xl border border-[--border] bg-[--surface]/80 px-5 py-2.5 shadow-lg shadow-black/20 backdrop-blur-xl">
              <Link href="/" className="flex items-center gap-2.5 font-bold tracking-tight">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[--accent]/10 text-sm font-black text-[--accent]">∅</span>
                <span className="text-sm font-semibold tracking-wider text-[--foreground]">VANTIO</span>
              </Link>
              <div className="hidden items-center gap-1 md:flex">
                {[
                  ["/architecture", "Architecture"],
                  ["/pricing",      "Pricing"],
                  ["/enterprise",   "Enterprise"],
                  ["/pro-smb",      "PRO / SMB"],
                  ["/developers",   "Developers"],
                  ["/research",     "Research"],
                ].map(([href, label]) => (
                  <a key={href} href={href}
                    className="rounded-lg px-3 py-1.5 text-xs font-medium text-[--muted] transition-all hover:bg-white/5 hover:text-[--foreground]">
                    {label}
                  </a>
                ))}
              </div>
              <a href="/dashboard"
                className="rounded-lg border border-[--border-2] bg-[--surface-2] px-4 py-1.5 text-xs font-semibold text-[--foreground] transition-all hover:border-[--accent]/40 hover:text-[--accent]">
                Dashboard
              </a>
            </div>
          </div>
        </nav>

        <div className="pt-20">{children}</div>

        {/* Footer */}
        <footer className="relative mt-24 border-t border-[--border] bg-[--surface]">
          <div className="mx-auto max-w-7xl px-6 py-16">
            <div className="flex flex-col gap-10 md:flex-row md:justify-between">
              <div className="max-w-xs">
                <div className="mb-3 flex items-center gap-2">
                  <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[--accent]/10 text-sm font-black text-[--accent]">∅</span>
                  <span className="font-semibold tracking-wider">VANTIO</span>
                </div>
                <p className="text-xs leading-relaxed text-[--muted]">
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
                    <p className="text-xs font-semibold uppercase tracking-widest text-[--muted]">{heading}</p>
                    {links.map(([href, label]) => (
                      <a key={href} href={href}
                        className="block text-xs text-[--muted] transition-colors hover:text-[--foreground]">
                        {label}
                      </a>
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-12 flex items-center justify-between border-t border-[--border] pt-6 text-xs text-[--muted]">
              <span>© 2026 Vantio AI, Inc. All rights reserved.</span>
              <span className="flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
                All systems operational
              </span>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
