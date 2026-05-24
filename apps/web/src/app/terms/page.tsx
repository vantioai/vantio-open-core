import type { Metadata } from "next";
export const metadata: Metadata = { title: "Terms of Service — Vantio AI" };
export default function TermsPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Legal</p>
      <h1 className="mb-2 text-3xl font-bold">Terms of Service</h1>
      <p className="mb-12 text-xs text-[--muted]">Effective date: May 1, 2026 · Vantio AI, Inc. (Delaware C-Corporation)</p>
      {[
        { h: "1. Acceptance", body: "By accessing or using any Vantio AI product or service, you agree to these Terms of Service and our Privacy Policy. If you are using Vantio on behalf of an organization, you represent that you have authority to bind that organization." },
        { h: "2. Permitted Use", body: "Vantio products may be used for lawful AI governance, observability, and compliance purposes. You may not use Vantio to circumvent security controls, interfere with other users, or violate any applicable law." },
        { h: "3. API Keys and Credentials", body: "You are responsible for the security of your API keys. You must not share API keys with unauthorized parties or commit them to public version control. Vantio reserves the right to revoke API keys that show evidence of misuse." },
        { h: "4. Tier 02 — Managed Edge Proxy", body: "The 14-day trial requires a valid payment method on file. After the trial period, your payment method will be charged at the then-current Tier 02 rate. You may cancel at any time before the trial ends to avoid charges. Cancellation takes effect at the end of the current billing period." },
        { h: "5. Tier 03 — Enterprise", body: "Tier 03 deployments are governed by a separately executed Enterprise Agreement. The Enterprise Agreement supersedes these Terms with respect to any conflicting provisions." },
        { h: "6. Data and Privacy", body: "Your use of Vantio is subject to our Privacy Policy. Vantio's payload quarantine architecture means raw linguistic content is structurally excluded from our systems — you retain full ownership of your model inputs and outputs." },
        { h: "7. Uptime and SLA", body: "Tier 01 is provided with a community SLA and no uptime guarantee. Tier 02 targets 99.9% monthly uptime for the ingest pipeline. Tier 03 SLA terms are defined in the Enterprise Agreement." },
        { h: "8. Limitation of Liability", body: "Vantio AI, Inc. is not liable for indirect, incidental, or consequential damages arising from your use of our products. Our total liability to you in any calendar month shall not exceed the amount you paid us in that month." },
        { h: "9. Governing Law", body: "These Terms are governed by the laws of the State of Delaware, United States. Any disputes shall be resolved in the courts of the State of Delaware." },
        { h: "10. Contact", body: "Vantio AI, Inc. · legal@vantio.ai · Incorporated in Delaware, United States." },
      ].map(({ h, body }) => (
        <section key={h} className="mb-8">
          <h2 className="mb-2 text-lg font-semibold">{h}</h2>
          <p className="text-sm text-[--muted]">{body}</p>
        </section>
      ))}
    </main>
  );
}
