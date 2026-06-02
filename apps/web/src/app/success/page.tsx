import type { Metadata } from "next";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { buildMetadata } from "@/lib/seo";

export const metadata: Metadata = buildMetadata({
  title: "Welcome to Pro",
  description: "Your Vantio AI Pro trial is active. Set up SDK-side enforcement in two minutes.",
  path: "/success",
  noindex: true,
});

export const dynamic = "force-dynamic";

/**
 * Resolve the API key for the checkout session, but ONLY for the tenant that
 * actually owns it. The `session_id` in the URL is NOT an authorization token —
 * it is guessable/shareable — so we require a logged-in Supabase session and
 * only reveal the key when the authenticated user's email matches the tenant
 * row that the session_id resolves to (i.e. they own the tenant).
 */
async function getOwnedApiKey(
  sessionId: string | null
): Promise<{ apiKey: string | null; authenticated: boolean }> {
  // Cookie-based auth client (same pattern as the dashboard).
  const cookieStore = await cookies();
  const authClient = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();
  if (!user?.email) return { apiKey: null, authenticated: false };
  if (!sessionId) return { apiKey: null, authenticated: true };

  try {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
      { auth: { autoRefreshToken: false, persistSession: false } }
    );
    const { data } = await supabase
      .from("tenants")
      .select("email, api_key")
      .eq("stripe_checkout_session_id", sessionId)
      .single();
    const tenant = data as { email?: string; api_key?: string } | null;
    // Ownership check: the session's tenant email must equal the logged-in user.
    if (!tenant?.email || tenant.email !== user.email) {
      return { apiKey: null, authenticated: true };
    }
    return { apiKey: tenant.api_key ?? null, authenticated: true };
  } catch {
    return { apiKey: null, authenticated: true };
  }
}

export default async function SuccessPage({
  searchParams,
}: {
  searchParams: Promise<{ session_id?: string }>;
}) {
  const { session_id } = await searchParams;
  const { apiKey, authenticated } = await getOwnedApiKey(session_id ?? null);

  return (
    <main className="hero-glow dot-grid flex min-h-[85vh] flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-[--accent]/10 text-[--accent] shadow-[0_0_30px_rgba(0,232,122,0.2)]">
            <span className="text-2xl">✓</span>
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[--muted]">
            14-day trial started
          </p>
          <h1 className="mt-2 text-3xl font-bold text-[--foreground]">
            Your Pro plan is live.
          </h1>
          <p className="mt-3 text-sm text-[--muted]">
            Your trial is active — no charge for 14 days. Your tenant has been
            provisioned and your API key is ready.
          </p>
        </div>

        {/* API Key */}
        <div className="mb-6 rounded-2xl border border-[--border] bg-[--surface] p-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[--muted]">
            Your API Key
          </p>
          {apiKey ? (
            <>
              <code className="block break-all rounded-lg bg-black/40 p-3 text-sm text-[--accent]">
                {apiKey}
              </code>
              <p className="mt-2 text-xs text-[--muted]">
                Store this securely. It cannot be shown again — regenerate from
                your dashboard if lost.
              </p>
            </>
          ) : authenticated ? (
            <p className="text-sm text-[--muted]">
              Your API key will appear here shortly, or find it in your{" "}
              <Link href="/dashboard" className="text-[--accent]/80 underline hover:text-[--accent]">
                dashboard
              </Link>
              .
            </p>
          ) : (
            <p className="text-sm text-[--muted]">
              Log in to view your API key on the dashboard.{" "}
              <Link href="/login" className="text-[--accent]/80 underline hover:text-[--accent]">
                Log in
              </Link>{" "}
              and open your{" "}
              <Link href="/dashboard" className="text-[--accent]/80 underline hover:text-[--accent]">
                dashboard
              </Link>
              .
            </p>
          )}
        </div>

        {/* Setup guide */}
        <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">
            SDK Enforcement Setup (2 min)
          </p>

          <ol className="space-y-5 text-sm">
            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-[--border-2]">01</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[--foreground]">Install the SDK</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-black/40 p-3 text-xs text-[--foreground]/70">
                  <code>npm install @vantio/agent-sdk</code>
                </pre>
              </div>
            </li>

            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-[--border-2]">02</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[--foreground]">Set your API key — one env var, that&apos;s it</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-black/40 p-3 text-xs text-[--foreground]/70">
                  <code>{`VANTIO_API_KEY=${apiKey ?? "your-api-key-above"}
VANTIO_INGEST_URL=https://vantio.ai`}</code>
                </pre>
              </div>
            </li>

            <li className="flex gap-3">
              <span className="mt-0.5 font-mono text-xs font-bold text-[--border-2]">03</span>
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[--foreground]">Run your agent — zero code changes</p>
                <pre className="mt-2 overflow-x-auto rounded-lg bg-black/40 p-3 text-xs text-[--foreground]/70">
                  <code>{`# The CLI enforces your policy on every agent run
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
            className="rounded-xl bg-[--accent] px-6 py-3 text-center text-sm font-bold text-black transition-all hover:bg-[--accent-dim] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)]"
          >
            Open Dashboard →
          </Link>
          <a
            href="https://github.com/vantioai/vantio-open-core"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-xl border border-[--border-2] bg-[--surface] px-6 py-3 text-center text-sm font-semibold text-[--muted] transition-all hover:border-[--border] hover:text-[--foreground]"
          >
            SDK Reference
          </a>
        </div>
      </div>
    </main>
  );
}
