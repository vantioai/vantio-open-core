import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { buildMetadata } from "@/lib/seo";
import { AlertsEditor, type AlertSettings } from "./alerts-editor";

export const metadata: Metadata = buildMetadata({
  title: "Alert Settings",
  description: "Route your Vantio AI anomaly alerts to your own Slack and email.",
  path: "/dashboard/alerts",
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

function rowToSettings(row: Record<string, unknown> | null): AlertSettings {
  return {
    alert_slack_webhook_url:
      typeof row?.["alert_slack_webhook_url"] === "string" ? (row["alert_slack_webhook_url"] as string) : "",
    alert_email:
      typeof row?.["alert_email"] === "string" ? (row["alert_email"] as string) : "",
    alerts_enabled: row?.["alerts_enabled"] !== false,
  };
}

export default async function AlertsPage() {
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
    .select("id, email, tier, alert_slack_webhook_url, alert_email, alerts_enabled")
    .eq("email", user.email)
    .single();

  const tenant = tenantData as ({ id: string; email: string; tier: string } & Record<string, unknown>) | null;

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

  const settings = rowToSettings(tenant as Record<string, unknown>);

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
          <h1 className="text-2xl font-bold text-[--foreground]">Alert Settings</h1>
          <p className="mt-1 max-w-2xl text-sm text-[--muted]">
            Route your policy-violation alerts to your OWN Slack channel and email. Vantio
            sends each anomaly only to the destinations you configure here — your alert data
            never lands in a shared channel.
          </p>
        </div>

        <AlertsEditor initialSettings={settings} />
      </div>
    </main>
  );
}
