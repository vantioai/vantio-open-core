import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Vantio AI — Absolute Kernel-Level AI Containment",
  description:
    "Physics-based AI governance. Ring-0 eBPF enforcement, cryptographic anomaly records, and zero-trust agent containment for regulated enterprises.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Corporation",
              "name": "Vantio AI, Inc.",
              "foundingLocation": "Delaware",
              "url": "https://vantio.ai",
            }),
          }}
        />
      </head>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <nav className="fixed top-0 z-50 w-full border-b border-[--border] bg-[--background]/90 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2 font-bold tracking-tight text-[--foreground]">
              <span className="text-[--accent]">[ ∅ ]</span> VANTIO
            </Link>
            <div className="hidden items-center gap-6 text-sm md:flex">
              {[
                { href: "/architecture", label: "Architecture" },
                { href: "/pricing",      label: "Pricing" },
                { href: "/enterprise",   label: "Enterprise" },
                { href: "/pro-smb",      label: "PRO / SMB" },
                { href: "/developers",   label: "Developers" },
                { href: "/research",     label: "Research" },
              ].map(({ href, label }) => (
                <a key={href} href={href}
                  className="text-[--muted] transition-colors hover:text-[--foreground]">
                  {label}
                </a>
              ))}
            </div>
            <a
              href="/dashboard"
              className="rounded-md border border-[--border] bg-[--surface] px-4 py-1.5 text-sm font-medium text-[--foreground] transition-colors hover:border-[--accent] hover:text-[--accent]"
            >
              Dashboard
            </a>
          </div>
        </nav>
        <div className="pt-[57px]">{children}</div>
        <footer className="border-t border-[--border] bg-[--background] px-6 py-10">
          <div className="mx-auto max-w-7xl">
            <div className="flex flex-col gap-8 md:flex-row md:justify-between">
              <div>
                <div className="mb-2 flex items-center gap-2 font-bold text-[--foreground]">
                  <span className="text-[--accent]">[ ∅ ]</span> VANTIO
                </div>
                <p className="max-w-xs text-xs text-[--muted]">
                  Physics-based AI governance. Delaware C-Corporation.
                </p>
              </div>
              <div className="flex flex-wrap gap-8 text-sm">
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[--muted]">Product</p>
                  {[
                    ["/architecture", "Architecture"],
                    ["/pricing",      "Pricing"],
                    ["/developers",   "Developers"],
                    ["/research",     "Research"],
                  ].map(([href, label]) => (
                    <a key={href} href={href} className="block text-[--muted] transition-colors hover:text-[--foreground]">{label}</a>
                  ))}
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[--muted]">Company</p>
                  {[
                    ["/trust",         "Trust Center"],
                    ["/enterprise",    "Enterprise"],
                    ["https://github.com/vantioai/vantio-open-core", "GitHub"],
                    ["/dashboard",     "Dashboard"],
                  ].map(([href, label]) => (
                    <a key={href} href={href} className="block text-[--muted] transition-colors hover:text-[--foreground]">{label}</a>
                  ))}
                </div>
                <div className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-widest text-[--muted]">Legal</p>
                  {[
                    ["/privacy", "Privacy Policy"],
                    ["/terms",   "Terms of Service"],
                  ].map(([href, label]) => (
                    <a key={href} href={href} className="block text-[--muted] transition-colors hover:text-[--foreground]">{label}</a>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-8 border-t border-[--border] pt-6 text-xs text-[--muted]">
              © 2026 Vantio AI, Inc. All rights reserved.
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
