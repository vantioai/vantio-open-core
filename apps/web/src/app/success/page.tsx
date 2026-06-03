import type { Metadata } from "next";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { buildMetadata } from "@/lib/seo";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";
import { Quickstart } from "@/components/quickstart";

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
  // In waitlist mode no checkout can occur, so /success may be reached without a
  // real session. Degrade gracefully: never imply a trial started or expose a
  // key — just offer the waitlist.
  if (isTier2Waitlist()) {
    return (
      <main className="hero-glow dot-grid flex min-h-[85vh] flex-col items-center justify-center px-6 py-16 text-center">
        <div className="w-full max-w-lg">
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
            Tier 2 — Launching soon
          </p>
          <h1 className="mt-2 text-3xl font-bold text-[var(--foreground)]">
            Pro isn&apos;t open for signups yet.
          </h1>
          <p className="mx-auto mt-3 max-w-md text-sm text-[var(--muted)]">
            We&apos;re putting the finishing touches on Tier 2. Join the waitlist and we&apos;ll
            email you the moment it opens.
          </p>
          <div className="mx-auto mt-8 max-w-xs">
            <WaitlistCta
              source="success"
              buttonClassName="w-full rounded-xl bg-[var(--accent)] py-3 text-center text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)]"
            />
          </div>
          <p className="mt-6 text-xs text-[var(--muted)]">
            <Link href="/" className="text-[var(--accent)]/80 underline hover:text-[var(--accent)]">
              Back to home
            </Link>
          </p>
        </div>
      </main>
    );
  }

  const { session_id } = await searchParams;
  const { apiKey, authenticated } = await getOwnedApiKey(session_id ?? null);

  return (
    <main className="hero-glow dot-grid flex min-h-[85vh] flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-lg">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)] shadow-[0_0_30px_rgba(0,232,122,0.2)]">
            <span className="text-2xl">✓</span>
          </div>
          <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
            14-day trial started
          </p>
          <h1 className="mt-2 text-3xl font-bold text-[var(--foreground)]">
            Your Pro plan is live.
          </h1>
          <p className="mt-3 text-sm text-[var(--muted)]">
            Your trial is active — no charge for 14 days. Your tenant has been
            provisioned and your API key is ready.
          </p>
        </div>

        {/* API Key */}
        <div className="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
            Your API Key
          </p>
          {apiKey ? (
            <>
              <code className="block break-all rounded-lg bg-black/40 p-3 text-sm text-[var(--accent)]">
                {apiKey}
              </code>
              <p className="mt-2 text-xs text-[var(--muted)]">
                Store this securely. It cannot be shown again — regenerate from
                your dashboard if lost.
              </p>
            </>
          ) : authenticated ? (
            <p className="text-sm text-[var(--muted)]">
              Your API key will appear here shortly, or find it in your{" "}
              <Link href="/dashboard" className="text-[var(--accent)]/80 underline hover:text-[var(--accent)]">
                dashboard
              </Link>
              .
            </p>
          ) : (
            <p className="text-sm text-[var(--muted)]">
              Log in to view your API key on the dashboard.{" "}
              <Link href="/login" className="text-[var(--accent)]/80 underline hover:text-[var(--accent)]">
                Log in
              </Link>{" "}
              and open your{" "}
              <Link href="/dashboard" className="text-[var(--accent)]/80 underline hover:text-[var(--accent)]">
                dashboard
              </Link>
              .
            </p>
          )}
        </div>

        {/* Quickstart — the real setup, with your key prefilled */}
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5">
          <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">
            Quickstart
          </p>
          <Quickstart apiKey={apiKey} />
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/dashboard"
            className="rounded-xl bg-[var(--accent)] px-6 py-3 text-center text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)]"
          >
            Open Dashboard →
          </Link>
          <a
            href="https://github.com/vantioai/vantio-open-core"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-xl border border-[var(--border-2)] bg-[var(--surface)] px-6 py-3 text-center text-sm font-semibold text-[var(--muted)] transition-all hover:border-[var(--border)] hover:text-[var(--foreground)]"
          >
            SDK Reference
          </a>
        </div>
      </div>
    </main>
  );
}
