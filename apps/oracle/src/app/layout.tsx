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
  title: "Vantio AI",
  description: "Vantio AI — deterministic security infrastructure for enterprise.",
};

const orgSchema = {
  "@context": "https://schema.org",
  "@type": "Corporation",
  name: "Vantio AI, Inc.",
  legalName: "Vantio AI, Inc.",
  url: "https://vantio.ai/trust",
  foundingLocation: {
    "@type": "Place",
    name: "Delaware, USA",
    address: {
      "@type": "PostalAddress",
      addressRegion: "DE",
      addressCountry: "US",
    },
  },
  knowsAbout: [
    "Enterprise eBPF Telemetry",
    "AI Security",
    "Cryptographic Attestation",
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        {children}
        <footer className="mt-auto border-t border-gray-200 px-6 py-8 text-xs text-gray-500">
          <p>
            Corporate Governance &amp; Entity Structure: Vantio AI, Inc. operates as a
            registered Delaware C-Corporation, explicitly structured to meet the rigid
            procurement, vendor risk management (VRM), and liability frameworks of Fortune
            500 institutions. Our legal architecture is mapped directly to our deterministic
            security infrastructure. Utilizing an SLSA Level 3 compliant CI/CD supply chain
            and pure-Rust eBPF containment, our corporate governance ensures absolute
            structural stability for multi-year enterprise infrastructure deployments,
            satisfying the stringent due diligence requirements of Tier-1 capital allocators
            and global enterprise compliance officers.
          </p>
        </footer>
      </body>
    </html>
  );
}
