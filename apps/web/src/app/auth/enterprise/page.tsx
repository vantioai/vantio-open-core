"use client";

import { useState } from "react";

export default function EnterpriseAuthPage() {
  const [tab, setTab] = useState<"call" | "form">("form");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", email: "", company: "", size: "", message: "" });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/contact", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error();
      setSubmitted(true);
    } catch {
      setError("Something went wrong. Email us at security@vantio.ai.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-24">
      <div className="grid gap-16 md:grid-cols-2">
        {/* Left: value prop */}
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-red-400">Enterprise — Tier 03</p>
          <h1 className="mb-4 text-4xl font-bold">
            Your enrolled AI agents<br />
            <span className="text-red-400">can&apos;t reach off-policy hosts.</span>
          </h1>
          <p className="mb-8 text-[--muted]">
            Enterprise deploys Vantio&apos;s enforcement layer as a de-privileged DaemonSet inside
            your own Kubernetes cluster (or on bare-metal Linux). For the workloads you enroll,
            it enforces egress policy in the Linux kernel — below your applications and your
            network. Off-policy packets from an enrolled agent are dropped before they leave the node.
          </p>
          <div className="space-y-4">
            {[
              { icon: "🏢", title: "Stays inside your VPC", body: "Nothing leaves your infrastructure. Your anomaly records are stored in your own database." },
              { icon: "⚡", title: "Under 1 millisecond enforcement", body: "Blocking happens at the kernel level. Your agents run at full speed until they cross a boundary." },
              { icon: "📜", title: "7-year audit records", body: "Tamper-proof, immutable records ready for SEC, FINRA, HIPAA, or any other regulator." },
              { icon: "🔐", title: "SAML / Okta federation", body: "Your existing identity provider. No separate login system to manage." },
            ].map(({ icon, title, body }) => (
              <div key={title} className="flex gap-3">
                <span className="mt-0.5 text-xl">{icon}</span>
                <div>
                  <p className="font-semibold">{title}</p>
                  <p className="text-sm text-[--muted]">{body}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="mt-8 text-sm text-[--muted]">
            Pricing starts at $50,000/year. Every Enterprise deployment begins with a
            technical architecture review — no obligation.
          </p>
        </div>

        {/* Right: contact form */}
        <div className="rounded-xl border border-[--border] bg-[--surface] p-8">
          <div className="mb-6 flex rounded-lg border border-[--border] bg-[--background] p-1">
            {(["form", "call"] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`flex-1 rounded-md py-2 text-sm font-medium transition-colors ${tab === t ? "bg-[--surface] text-[--foreground]" : "text-[--muted] hover:text-[--foreground]"}`}>
                {t === "form" ? "Send a Message" : "Schedule a Call"}
              </button>
            ))}
          </div>

          {tab === "call" ? (
            <iframe
              src={`${process.env.NEXT_PUBLIC_CALENDLY_URL ?? "https://calendly.com/vantio-ai/enterprise"}?hide_gdpr_banner=1&background_color=0d0d14&text_color=f0f0f5&primary_color=00ff88`}
              width="100%" height="520" frameBorder="0" title="Schedule Enterprise Call"
              className="rounded-lg"
            />
          ) : submitted ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 text-4xl">✓</div>
              <h3 className="font-semibold">Message received.</h3>
              <p className="mt-2 text-sm text-[--muted]">We&apos;ll reply within one business day.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <h2 className="mb-4 font-semibold">Talk to our team</h2>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-[--muted]">Name *</label>
                  <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Jane Smith"
                    className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm outline-none focus:border-[--accent]" />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[--muted]">Work Email *</label>
                  <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                    placeholder="jane@company.com"
                    className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm outline-none focus:border-[--accent]" />
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-[--muted]">Company *</label>
                  <input required value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })}
                    placeholder="Acme Corp"
                    className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm outline-none focus:border-[--accent]" />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-[--muted]">Team Size</label>
                  <select value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })}
                    className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm outline-none focus:border-[--accent]">
                    <option value="">Select...</option>
                    {["1–50", "51–500", "501–5,000", "5,000+"].map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs text-[--muted]">What are you trying to solve?</label>
                <textarea value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })}
                  placeholder="Tell us about your AI deployment and what you need to control."
                  rows={4}
                  className="w-full rounded-lg border border-[--border] bg-[--background] px-3 py-2 text-sm outline-none focus:border-[--accent]" />
              </div>
              {error && <p className="text-xs text-red-400">{error}</p>}
              <button type="submit" disabled={submitting}
                className="w-full rounded-lg bg-red-400 py-3 text-sm font-semibold text-black transition-colors hover:bg-red-300 disabled:opacity-50">
                {submitting ? "Sending…" : "Send Message"}
              </button>
            </form>
          )}

          <p className="mt-4 text-center text-xs text-[--muted]">
            Or email us: <a href="mailto:security@vantio.ai" className="text-[--accent] underline">security@vantio.ai</a>
          </p>
        </div>
      </div>
    </main>
  );
}
