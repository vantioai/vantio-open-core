import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PRO / SMB — Vantio AI",
  description: "Active AI governance for growing teams. Block unauthorized agent behavior automatically — no servers, no code changes, no ops burden.",
};

export default function ProSmbPage() {
  return (
    <main>
      <section className="mx-auto max-w-4xl px-6 pb-16 pt-24 text-center">
        <span className="mb-4 inline-block rounded-full border border-blue-400/30 bg-blue-400/10 px-4 py-1 text-xs font-semibold uppercase tracking-widest text-blue-400">
          PRO / SMB — $499/month
        </span>
        <h1 className="mb-4 text-4xl font-bold sm:text-5xl">
          Stop unauthorized AI behavior<br />
          <span className="text-blue-400">automatically.</span>
        </h1>
        <p className="mx-auto mb-10 max-w-2xl text-lg text-[--muted]">
          When your AI agent tries to do something it shouldn&apos;t — contact an unauthorized
          server, access sensitive data, make unexpected API calls — Vantio blocks it instantly
          and tells your team. No servers to manage. No code to change.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <a href="/pricing"
            className="rounded-md bg-blue-400 px-6 py-3 text-sm font-semibold text-black hover:bg-blue-300">
            Start 14-Day Free Trial
          </a>
          <a href="/dashboard"
            className="rounded-md border border-blue-400/30 px-6 py-3 text-sm font-medium text-blue-400 hover:bg-blue-400/5">
            View Demo Dashboard
          </a>
        </div>
      </section>

      {/* What you actually get */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">What You Get</h2>
          <p className="mb-12 text-center text-2xl font-bold">Everything you need. Nothing you don&apos;t.</p>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: "🚫", title: "Automatic blocking", body: "Non-compliant AI calls are stopped before they reach the model. You define the rules — Vantio enforces them." },
              { icon: "📊", title: "Live dashboard", body: "See every AI agent action in real time. Filter by agent, by date, by outcome. Export to CSV for compliance review." },
              { icon: "🔔", title: "Instant Slack alerts", body: "The moment an AI agent does something it shouldn't, your team gets a Slack message with the full context." },
              { icon: "📝", title: "30-day compliance log", body: "Every AI decision stored in a tamper-proof log for 30 days. Ready for audits, incident reviews, or just peace of mind." },
              { icon: "🔑", title: "API key in 60 seconds", body: "Pay, get your API key, set two environment variables. You're done. No infrastructure, no Kubernetes, no ops team." },
              { icon: "💳", title: "Cancel any time", body: "14-day free trial, then $499/month. Cancel from your dashboard. No sales calls, no lock-in contracts." },
            ].map(({ icon, title, body }) => (
              <div key={title} className="rounded-xl border border-[--border] bg-[--background] p-5">
                <div className="mb-3 text-2xl">{icon}</div>
                <h3 className="mb-1 font-semibold">{title}</h3>
                <p className="text-sm text-[--muted]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Setup */}
      <section className="mx-auto max-w-4xl px-6 py-20">
        <h2 className="mb-2 text-2xl font-bold">Running in under 60 seconds.</h2>
        <p className="mb-10 text-[--muted]">Seriously. Here&apos;s the entire integration.</p>
        <div className="space-y-6">
          {[
            { n: "1", title: "Start your trial", body: "Click the button, enter your card. No charge for 14 days. Your account and API key are created instantly." },
            { n: "2", title: "Set two environment variables", body: "VANTIO_API_KEY=your-key-here\nVANTIO_INGEST_URL=https://vantio.ai\n\nThat's the entire configuration." },
            { n: "3", title: "Run your agent through Vantio", body: "vantio run node agent.js\n\nOr: vantio run python agent.py\n\nYour code doesn't change. The CLI handles everything." },
            { n: "4", title: "Watch the dashboard", body: "Open /dashboard. Every AI call your agent makes shows up in real time — what it called, when, and whether it was allowed." },
          ].map(({ n, title, body }) => (
            <div key={n} className="flex gap-6 rounded-xl border border-[--border] bg-[--surface] p-6">
              <span className="mt-0.5 shrink-0 text-2xl font-bold text-blue-400">{n}</span>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-1 whitespace-pre-line text-sm text-[--muted]">{body}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-10 text-sm text-[--muted]">
          Need kernel-level enforcement instead of proxy-layer blocking?{" "}
          <a href="/enterprise" className="text-red-400 underline">See Enterprise →</a>
        </p>
      </section>
    </main>
  );
}
