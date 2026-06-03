import type { Metadata } from "next";
import type { ReactNode } from "react";
import { buildMetadata, breadcrumbJsonLd, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { PRICING_FAQ } from "@/lib/faq";

// pricing/page.tsx is a Client Component and cannot export metadata or render
// server-only JSON-LD itself, so the segment layout supplies both.
export const metadata: Metadata = buildMetadata({
  title: "Pricing",
  description:
    "Start free, upgrade when you're ready. Developer (free forever), Pro ($499/mo with active blocking), and Enterprise (kernel-level enforcement) tiers for AI agent governance.",
  path: "/pricing",
});

export default function PricingLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Pricing", path: "/pricing" }])} />
      <JsonLd data={faqJsonLd(PRICING_FAQ)} />
      {children}
    </>
  );
}
