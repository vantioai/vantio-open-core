import type { Metadata } from "next";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";

export const metadata: Metadata = {
  title: "Welcome to Vantio AI PRO",
};

export const dynamic = "force-dynamic";

async function getApiKey(sessionId: string | null): Promise<string | null> {
  if (!sessionId) return null;
  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
      { auth: { autoRefreshToken: false, persistSession: false } }
    );
    const { data } = await supabase
      .from("tenants")
      .select("api_key")
      .eq("stripe_checkout_session_id", sessionId)
      .single();
    return (data as { api_key?: string } | null)?.api_key ?? null;
  } catch {
    return null;
  }
}

export default async function SuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ session_id?: string }>;
}) {
  const { session_id } = await searchParams;
  const apiKey = await getApiKey(session_id ?? null);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white px-6">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-green-50">
            <span className="text-2xl">✓</span>
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            14-day trial started
          </p>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">
            Your Managed Edge Proxy is live.
          </h1>
          <p className="mt-3 text-sm text-gray-500">
            Your trial is active — no charge for 14 days. Your tenant has been
            provisioned and your API key is ready.
          </p>
        </div>

        {/* API Key */}
        <div className="mb-6 rounded-xl border border-gray-200 bg-gray-50 p-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Your API Key
          </p>
          {apiKey ? (
            <>
              <code className="block break-all rounded-lg bg-gray-900 p-3 text-sm text-green-400">
                {apiKey}
              </code>
              <p className="mt-2 text-xs text-gray-400">
                Store this securely. It cannot be shown again — regenerate from
                your dashboard if lost.
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-500">
              Your API key will appear here shortly, or find it in your{" "}
              <Link href="/dashboard" className="underline">
                dashboard
              </Link>
              .
            </p>
          )}
        </div>

        {/* Setup guide */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Managed Edge Proxy Setup (2 min)
          </p>

          <ol className="space-y-5 text-sm">
            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-gray-300">01</span>
              <div>
                <p className="font-medium text-gray-900">Install the SDK</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
                  <code>npm install @vantio/agent-sdk</code>
                </pre>
              </div>
            </li>

            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-gray-300">02</span>
              <div>
                <p className="font-medium text-gray-900">Set your API key — one env var, that&apos;s it</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
                  <code>{`VANTIO_API_KEY=${apiKey ?? "your-api-key-above"}
VANTIO_INGEST_URL=https://app.vantio.ai`}</code>
                </pre>
              </div>
            </li>

            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-gray-300">03</span>
              <div>
                <p className="font-medium text-gray-900">Run your agent — zero code changes</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
                  <code>{`# The CLI auto-intercepts all outbound LLM calls
vantio run node agent.js
vantio run --audit tsx agent.ts

# Anomalies appear on your dashboard automatically`}</code>
                </pre>
              </div>
            </li>
          </ol>
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="rounded-lg bg-gray-900 px-6 py-3 text-center text-sm font-semibold text-white transition-colors hover:bg-gray-700"
          >
            Open Dashboard →
          </Link>
          <a
            href="https://github.com/vantioai/vantio-open-core"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-300 px-6 py-3 text-center text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50"
          >
            SDK Reference
          </a>
        </div>
      </div>
    </main>
  );
}
