import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { buildMetadata } from "@/lib/seo";
import { DEFAULT_POLICY, type TenantPolicy } from "@/lib/policy";
import { PolicyEditor } from "./policy-editor";

export const metadata: Metadata = buildMetadata({
  title: "Policy Editor",
  description: "Edit your Vantio AI enforcement policy.",
  path: "/dashboard/policy",
  noindex: true,
});

export const dynamic = "force-dynamic";

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

function rowToPolicy(row: Record<string, unknown> | null): TenantPolicy {
  if (!row) return DEFAULT_POLICY;
  return {
    enforce:           row["enforce"] === true,
    redact_pii:        row["redact_pii"] === true,
    pii_types:         Array.isArray(row["pii_types"])     ? (row["pii_types"]     as string[]) : [],
    allowed_hosts:     Array.isArray(row["allowed_hosts"]) ? (row["allowed_hosts"] as string[]) : [],
    blocked_hosts:     Array.isArray(row["blocked_hosts"]) ? (row["blocked_hosts"] as string[]) : [],
    max_request_bytes: typeof row["max_request_bytes"] === "number" ? row["max_request_bytes"] : Number(row["max_request_bytes"] ?? 0),
    spend_cap_usd:     typeof row["spend_cap_usd"]     === "number" ? row["spend_cap_usd"]     : Number(row["spend_cap_usd"] ?? 0),
  };
}

export default async function PolicyPage() {
  // ── Auth gate ────────────────────────────────────────────────────────────
  const cookieStore = await cookies();
  const authClient = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();
  if (!user?.email) redirect("/login");

  const supabase = getSupabaseAdmin();

  const { data: tenantData } = await supabase
    .from("tenants")
    .select("id, email, tier")
    .eq("email", user.email)
    .single();

  const tenant = tenantData as { id: string; email: string; tier: string } | null;

  if (!tenant) {
    return (
      <main className="flex min-h-[70vh] items-center justify-center px-6">
        <div className="rounded-2xl border border-[--border] bg-[--surface] p-10 text-center">
          <p className="text-sm text-[--muted]">No PRO tenant found for this account.</p>
          <Link
            href="/pricing"
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-[--accent] px-6 py-3 text-sm font-bold text-black transition-all hover:bg-[--accent-dim] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)]"
          >
            Upgrade to PRO →
          </Link>
        </div>
      </main>
    );
  }

  const { data: policyRow } = await supabase
    .from("tenant_policies")
    .select("enforce, redact_pii, pii_types, allowed_hosts, blocked_hosts, max_request_bytes, spend_cap_usd")
    .eq("tenant_id", tenant.id)
    .maybeSingle();

  const policy = rowToPolicy(policyRow as Record<string, unknown> | null);
  const isPaid = tenant.tier === "PRO" || tenant.tier === "ENTERPRISE";

  return (
    <main className="min-h-screen">
      {/* Top bar */}
      <header className="border-b border-[--border] bg-[--surface]/60 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-2.5 font-bold tracking-tight">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[--accent]/10 text-sm font-black text-[--accent]">∅</span>
              <span className="text-sm font-semibold tracking-wider text-[--foreground]">VANTIO</span>
            </span>
            <span className="rounded-full bg-[--accent]/15 px-2.5 py-0.5 text-xs font-bold text-[--accent]">{tenant.tier}</span>
          </div>
          <Link
            href="/dashboard"
            className="rounded-lg border border-[--border-2] bg-[--surface-2] px-4 py-1.5 text-xs font-semibold text-[--foreground] transition-all hover:border-[--accent]/40 hover:text-[--accent]"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[--foreground]">Enforcement Policy</h1>
          <p className="mt-1 max-w-2xl text-sm text-[--muted]">
            These rules are synced to your SDK/CLI, which enforces them locally — redacting
            PII, capping spend, and blocking hosts before any data leaves your environment.
            Vantio stores the policy; your runtime does the enforcing.
          </p>
        </div>

        {!isPaid && (
          <div className="mb-6 rounded-xl border border-blue-400/30 bg-blue-400/5 p-4 text-sm text-[--muted]">
            Policy enforcement applies to{" "}
            <span className="font-semibold text-blue-400">PRO &amp; Enterprise</span> tiers. You can
            configure it now, but the SDK only receives an active policy on a paid plan.{" "}
            <Link href="/pricing" className="text-[--accent] underline hover:text-[--accent-dim]">
              Upgrade →
            </Link>
          </div>
        )}

        <PolicyEditor initialPolicy={policy} />
      </div>
    </main>
  );
}
