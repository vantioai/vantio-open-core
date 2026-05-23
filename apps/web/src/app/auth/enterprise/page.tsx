"use client";

import { useState } from "react";

// Calendly URL configured via NEXT_PUBLIC_CALENDLY_URL env var.
// If not set, the "Schedule a Call" tab is hidden and the form is shown by default.
const CALENDLY_URL = process.env.NEXT_PUBLIC_CALENDLY_URL ?? "";

export default function EnterpriseAuthPage() {
  const [tab, setTab] = useState<"call" | "form">(CALENDLY_URL ? "call" : "form");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  const [form, setForm] = useState({
    name: "", email: "", company: "", size: "", message: "",
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/contact", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Submission failed.");
      setSubmitted(true);
    } catch {
      setError("Something went wrong. Email us directly at security@vantio.ai.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-6 py-16">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="mb-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Vantio AI — Enterprise
          </p>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">
            Let&apos;s talk about Ring-0 enforcement.
          </h1>
          <p className="mt-3 text-sm text-gray-500">
            Tier 3 includes the Phantom Engine, dedicated GCP Spanner, SAML/SSO,
            and a custom SLA. Pricing starts at $50,000 ARR.
          </p>
        </div>

        {/* Tab switcher — only show if Calendly is configured */}
        {CALENDLY_URL && (
          <div className="mb-6 flex rounded-lg border border-gray-200 bg-white p-1">
            {(["call", "form"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${
                  tab === t
                    ? "bg-gray-900 text-white"
                    : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {t === "call" ? "Schedule a Call" : "Send a Message"}
              </button>
            ))}
          </div>
        )}

        {/* Calendly embed */}
        {tab === "call" && CALENDLY_URL && (
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
            <iframe
              src={`${CALENDLY_URL}?hide_gdpr_banner=1&background_color=ffffff&text_color=111827&primary_color=111827`}
              width="100%"
              height="580"
              frameBorder="0"
              title="Schedule Enterprise Call"
            />
          </div>
        )}

        {/* Contact form */}
        {tab === "form" && (
          <div className="rounded-xl border border-gray-200 bg-white p-8">
            {submitted ? (
              <div className="text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-50">
                  <span className="text-xl">✓</span>
                </div>
                <h3 className="font-semibold text-gray-900">Message received.</h3>
                <p className="mt-2 text-sm text-gray-500">
                  We&apos;ll respond within one business day at the email you provided.
                </p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Name *</label>
                    <input
                      required
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      placeholder="Jane Smith"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Work Email *</label>
                    <input
                      required
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="jane@company.com"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                    />
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Company *</label>
                    <input
                      required
                      value={form.company}
                      onChange={(e) => setForm({ ...form, company: e.target.value })}
                      placeholder="Acme Corp"
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-700">Team Size</label>
                    <select
                      value={form.size}
                      onChange={(e) => setForm({ ...form, size: e.target.value })}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                    >
                      <option value="">Select...</option>
                      <option value="1-50">1–50</option>
                      <option value="51-500">51–500</option>
                      <option value="501-5000">501–5,000</option>
                      <option value="5000+">5,000+</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-700">Message</label>
                  <textarea
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                    placeholder="Tell us about your deployment environment and compliance requirements."
                    rows={4}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-gray-900 focus:ring-1 focus:ring-gray-900"
                  />
                </div>
                {error && <p className="text-xs text-red-600">{error}</p>}
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-lg bg-gray-900 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
                >
                  {submitting ? "Sending…" : "Send Message"}
                </button>
              </form>
            )}
          </div>
        )}

        <p className="mt-6 text-center text-xs text-gray-400">
          Or email us directly at{" "}
          <a href="mailto:security@vantio.ai" className="underline hover:text-gray-600">
            security@vantio.ai
          </a>
        </p>
      </div>
    </main>
  );
}
