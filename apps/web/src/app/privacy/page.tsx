import type { Metadata } from "next";
export const metadata: Metadata = { title: "Privacy Policy — Vantio AI" };
export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Legal</p>
      <h1 className="mb-2 text-3xl font-bold">Privacy Policy</h1>
      <p className="mb-12 text-xs text-[--muted]">Effective date: May 1, 2026 · Vantio AI, Inc. (Delaware C-Corporation)</p>
      {[
        { h: "1. What We Collect", body: "We collect account information (email address) when you sign up, payment information processed by Stripe (we never store raw card data), usage telemetry (structured execution metadata only — bytes_severed, pid, target_host, action_taken, timestamps), and server logs necessary for security and operations." },
        { h: "2. Payload Quarantine", body: "Vantio enforces a strict payload quarantine by design. Raw linguistic content — prompts, model completions, agent reasoning chains, or any personally identifiable information embedded in AI outputs — is structurally excluded from our ingest pipeline. The whitelist of permitted anomaly_metadata fields is enforced at the API layer and is auditable in our open-source ingest route." },
        { h: "3. Data Retention", body: "Tier 02 anomaly events are retained for 90 days. Tier 03 WORM ledger retention is configurable up to 7 years to satisfy SEC Rule 17a-4, MiFID II, and SOC 2 Type II requirements. Account data is retained for the duration of your subscription plus 30 days after cancellation." },
        { h: "4. Data Sharing", body: "We do not sell your data. We share data with: Stripe (payment processing), Supabase (database hosting, SOC 2 Type II certified), Google Cloud (Spanner WORM ledger for Tier 03), and Vercel (edge proxy hosting). Each sub-processor is contractually bound to process data only as instructed by Vantio AI, Inc." },
        { h: "5. Your Rights", body: "You may request access to, correction of, or deletion of your personal data at any time by emailing privacy@vantio.ai. Requests are fulfilled within 30 days. Data portability is available via the CSV export in your dashboard." },
        { h: "6. Security", body: "All data in transit is encrypted via TLS 1.3. Data at rest is encrypted using AES-256. API keys are stored as salted hashes. The Supabase service role key used for writes is scoped to INSERT only — no SELECT, UPDATE, or DELETE on sensitive tables." },
        { h: "7. Contact", body: "Vantio AI, Inc. · privacy@vantio.ai · Incorporated in Delaware, United States." },
      ].map(({ h, body }) => (
        <section key={h} className="mb-8">
          <h2 className="mb-2 text-lg font-semibold">{h}</h2>
          <p className="text-sm text-[--muted]">{body}</p>
        </section>
      ))}
    </main>
  );
}
