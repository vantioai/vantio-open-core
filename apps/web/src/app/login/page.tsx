"use client";
import { useState, useMemo } from "react";
import { createBrowserClient } from "@supabase/ssr";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Stable client across renders — never recreated unless env vars change.
  const supabase = useMemo(
    () =>
      createBrowserClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
      ),
    []
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error: otpError } = await supabase.auth.signInWithOtp({
      email,
      options: {
        // Route through the PKCE callback so the `?code=...` is exchanged for a
        // session cookie before landing on the (server-rendered) dashboard.
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/dashboard`,
      },
    });

    setLoading(false);
    if (otpError) {
      setError(otpError.message);
    } else {
      setSent(true);
    }
  }

  return (
    <main className="hero-glow dot-grid flex min-h-[80vh] flex-col items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-2xl border border-[--border] bg-[--surface]/80 p-8 shadow-2xl shadow-black/40 backdrop-blur-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[--accent]/10 text-lg font-black text-[--accent]">∅</span>
          <h1 className="text-2xl font-bold text-[--foreground]">
            Sign in to your dashboard
          </h1>
          <p className="mt-2 text-sm text-[--muted]">
            We&apos;ll send a magic link to your email.
          </p>
        </div>

        {sent ? (
          <div className="rounded-xl border border-[--accent]/30 bg-[--accent]/5 p-5 text-center text-sm text-[--accent]">
            Check your inbox — magic link sent to <strong className="text-[--foreground]">{email}</strong>.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="email"
              required
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-[--border-2] bg-[--surface-2] px-4 py-3 text-sm text-[--foreground] placeholder-[--muted] outline-none transition-colors focus:border-[--accent]/50 focus:ring-1 focus:ring-[--accent]/30"
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-[var(--accent)] px-4 py-3 text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)] disabled:opacity-50"
            >
              {loading ? "Sending…" : "Send magic link"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-xs text-[--muted]">
          No account?{" "}
          <a href="/pricing" className="text-[--accent]/80 underline hover:text-[--accent]">
            Start with PRO →
          </a>
        </p>
      </div>
    </main>
  );
}
