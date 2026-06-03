import type { Metadata } from "next";

/**
 * Canonical, non-www production origin. The www host should 308-redirect here
 * (configured in Vercel project domains) so search engines only ever see one
 * canonical hostname.
 */
export const SITE = {
  name: "Vantio AI",
  shortName: "Vantio",
  url: "https://vantio.ai",
  locale: "en_US",
  defaultTitle: "Vantio AI — Go Fully Autonomous, Stay Fully Compliant",
  defaultDescription:
    "Vantio is regulated AI governance for autonomous AI agents — secure every agent, prove compliance to regulators, and accelerate deployment with confidence.",
  // Social profiles surfaced in structured data (Organization.sameAs).
  social: {
    linkedin: "https://www.linkedin.com/company/vantio-ai",
    github: "https://github.com/vantioai",
  },
} as const;

interface BuildMetadataInput {
  /** Short page title; the site name is appended automatically. Omit for the homepage default. */
  title?: string;
  /** Meta description. Falls back to the site default. */
  description?: string;
  /** Route path used for the canonical URL and Open Graph URL, e.g. "/pricing". */
  path: string;
  /** Set true for private/transactional pages that must stay out of the index. */
  noindex?: boolean;
}

/**
 * Single source of truth for per-page metadata. Produces an absolute title,
 * a self-referencing canonical, and complete Open Graph + Twitter cards.
 * The Open Graph/Twitter image is supplied automatically by the file-based
 * `opengraph-image`/`twitter-image` routes and merged in by Next.js.
 */
export function buildMetadata({
  title,
  description = SITE.defaultDescription,
  path,
  noindex = false,
}: BuildMetadataInput): Metadata {
  const fullTitle = title ? `${title} — ${SITE.name}` : SITE.defaultTitle;
  const canonical = path === "/" ? "/" : path.replace(/\/$/, "");
  const url = new URL(canonical, SITE.url).toString();

  return {
    title: { absolute: fullTitle },
    description,
    alternates: { canonical },
    robots: noindex
      ? { index: false, follow: false, googleBot: { index: false, follow: false } }
      : { index: true, follow: true },
    openGraph: {
      type: "website",
      siteName: SITE.name,
      locale: SITE.locale,
      url,
      title: fullTitle,
      description,
    },
    twitter: {
      card: "summary_large_image",
      title: fullTitle,
      description,
    },
  };
}

/** JSON-LD describing the company. Rendered once in the root layout. */
export function organizationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Vantio AI, Inc.",
    legalName: "Vantio AI, Inc.",
    url: SITE.url,
    logo: `${SITE.url}/icon`,
    description: SITE.defaultDescription,
    foundingLocation: {
      "@type": "Place",
      name: "Delaware, USA",
    },
    sameAs: [SITE.social.linkedin, SITE.social.github],
  };
}

/** JSON-LD describing the product, with tiered offers. Rendered in the root layout. */
export function softwareApplicationJsonLd() {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Vantio AI",
    applicationCategory: "SecurityApplication",
    operatingSystem: "Linux, macOS",
    url: SITE.url,
    description: SITE.defaultDescription,
    offers: [
      {
        "@type": "Offer",
        name: "Developer",
        price: "0",
        priceCurrency: "USD",
        description: "Real-time visibility into your AI agents. 10,000 events/month, free forever.",
      },
      {
        "@type": "Offer",
        name: "Pro",
        price: "499",
        priceCurrency: "USD",
        description: "SDK-side PII redaction, spend caps, host/policy blocking, and a tamper-proof audit trail.",
      },
      {
        "@type": "Offer",
        name: "Enterprise",
        priceCurrency: "USD",
        description: "Per-agent kernel-level (eBPF) enforcement inside your own Linux/Kubernetes cluster, with a 7-year WORM audit ledger.",
      },
    ],
  };
}

/** BreadcrumbList JSON-LD. Pass the trail from the homepage down to the current page. */
export function breadcrumbJsonLd(items: { name: string; path: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: new URL(item.path, SITE.url).toString(),
    })),
  };
}

/**
 * FAQPage JSON-LD. Per Google's guidelines the questions/answers must also be
 * visible on the page, so only use this alongside a rendered FAQ section.
 */
export function faqJsonLd(items: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: items.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}
