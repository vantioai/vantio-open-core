import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vantio AI — Deterministic AI Governance",
  description:
    "Kernel-enforced eBPF containment for LLM agents. From open-source SDK to Fortune 500 deployment.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "Corporation",
              "name": "Vantio AI, Inc.",
              "foundingLocation": "Delaware",
            }),
          }}
        />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <nav className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
          <a href="/" className="font-bold tracking-tight text-gray-900">
            [ ∅ ] Vantio AI
          </a>
          <div className="flex items-center gap-6 text-sm">
            <a href="/pricing" className="text-gray-500 hover:text-gray-900">
              Pricing
            </a>
            <a href="/trust" className="text-gray-500 hover:text-gray-900">
              Trust
            </a>
            <a
              href="/auth/enterprise"
              className="text-gray-500 hover:text-gray-900"
            >
              Enterprise
            </a>
            <a
              href="/login"
              className="text-gray-500 hover:text-gray-900"
            >
              Sign In
            </a>
            <a
              href="/dashboard"
              className="rounded-lg bg-gray-900 px-4 py-1.5 text-white transition-colors hover:bg-gray-700"
            >
              Dashboard
            </a>
          </div>
        </nav>
        {children}
        <footer className="w-full border-t border-gray-200 py-4 text-center text-sm text-gray-500">
          © 2026 Vantio AI, Inc. All rights reserved.
        </footer>
      </body>
    </html>
  );
}
