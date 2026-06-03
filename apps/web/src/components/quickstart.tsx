"use client";

import { useState } from "react";
import { CodeBlock } from "@/components/code-block";

// Key-prefilled CLI quickstart with a "where do you run your agents?" fork.
// Reused on /success and the dashboard. No backend — the fork is local state.
// `apiKey` is the tenant's real key (or null → a placeholder is shown).
export function Quickstart({ apiKey }: { apiKey: string | null }) {
  const [where, setWhere] = useState<"server" | "local">("server");
  const key = apiKey && apiKey.length > 0 ? apiKey : "<YOUR_API_KEY>";

  const Choice = ({ id, label }: { id: "server" | "local"; label: string }) => (
    <button
      type="button"
      onClick={() => setWhere(id)}
      aria-pressed={where === id}
      className={`flex-1 rounded-xl border px-4 py-3 text-sm font-semibold transition-colors ${
        where === id
          ? "border-[var(--accent)]/50 bg-[var(--accent)]/10 text-[var(--accent)]"
          : "border-[var(--border-2)] bg-[var(--surface-2)] text-[var(--muted)] hover:text-[var(--foreground)]"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div>
      {/* Run-location fork */}
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
        How do you run your agents?
      </p>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <Choice id="server" label="On a server / in my code" />
        <Choice id="local" label="On my own computer" />
      </div>

      {where === "local" && (
        <p className="mb-5 rounded-lg border border-[var(--border-2)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--muted)]">
          A one-click desktop app is coming soon. For now, the CLI below works great on your machine too.
        </p>
      )}

      {/* Three-step CLI quickstart */}
      <ol className="space-y-5">
        <li>
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[var(--accent)]">01</span>
            <span className="text-sm font-medium text-[var(--foreground)]">Install the CLI</span>
          </div>
          <CodeBlock code="curl -fsSL https://vantio.ai/install.sh | sh" className="bg-black/40" />
          <p className="mt-1.5 text-xs text-[var(--muted)]">
            or <code className="rounded bg-[var(--surface-2)] px-1 text-[var(--accent)]">npm i -g @vantio/cli</code>
          </p>
        </li>
        <li>
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[var(--accent)]">02</span>
            <span className="text-sm font-medium text-[var(--foreground)]">Log in (saves your key — no env vars after this)</span>
          </div>
          <CodeBlock code={`vantio login ${key}`} className="bg-black/40" />
        </li>
        <li>
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-xs font-bold text-[var(--accent)]">03</span>
            <span className="text-sm font-medium text-[var(--foreground)]">Run your agent — zero code changes</span>
          </div>
          <CodeBlock code={"vantio run node agent.js"} className="bg-black/40" />
        </li>
      </ol>

      {!apiKey && (
        <p className="mt-4 text-xs text-[var(--muted)]">
          Your real API key will be filled into step 2 once it&apos;s provisioned — check the API Key panel above.
        </p>
      )}
    </div>
  );
}
