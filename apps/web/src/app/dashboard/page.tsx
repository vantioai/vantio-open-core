import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { BillingPortalButton } from "./billing-portal-button";
import { PhantomEngineStatus } from "./phantom-engine-status";
import { buildMetadata } from "@/lib/seo";
import { computeBenchmarks } from "@/lib/benchmarks";

export const metadata: Metadata = buildMetadata({
  title: "Dashboard",
  description: "Your Vantio AI Pro tenant dashboard.",
  path: "/dashboard",
  noindex: true,
});

// Force dynamic so server component always reads fresh Supabase data.
export const dynamic = "force-dynamic";

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL!;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY!;
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

interface Tenant {
  email: string;
  tier: string;
  stripe_subscription_id: string | null;
  api_key: string | null;
  seats_used: number | null;
  seats_total: number | null;
  created_at: string;
}

interface AnomalyEvent {
  id: string;
  tenant_identity: string;
  trace_id: string;
  anomaly_metadata: {
    bytes_severed?: number | null;
    pid?: number | null;
    timestamp_ns?: number | null;
    target_host?: string | null;
    action_taken?: string | null;
  } | null;
  audit_mode: boolean;
  created_at: string;
}

// Action values that represent an actual policy violation / severance.
const VIOLATION_ACTIONS = ["POLICY_VIOLATION", "SEVERED", "HARD_DROP", "BLOCKED"];
// Engine health pings — not anomalies; drive the status card only.
const HEALTH_ACTIONS = ["ENGINE_STARTED", "ENGINE_HEARTBEAT"];

function isViolation(evt: AnomalyEvent): boolean {
  return VIOLATION_ACTIONS.includes((evt.anomaly_metadata?.action_taken ?? "").toUpperCase());
}

/**
 * Outcome badge. Audit mode is observe-only — it never blocks — so audit-mode
 * events are FLAGGED/OBSERVED, never "BLOCKED". A real block only happens in
 * enforce mode (audit_mode === false) on a violation action.
 */
function EventStatusBadge({ evt }: { evt: AnomalyEvent }) {
  const violation = isViolation(evt);
  let label: string, cls: string, dot: string;
  if (evt.audit_mode) {
    if (violation) { label = "FLAGGED";  cls = "bg-amber-400/10 text-amber-400"; dot = "bg-amber-400"; }
    else           { label = "OBSERVED"; cls = "bg-[--muted]/15 text-[--muted]"; dot = "bg-[--muted]"; }
  } else {
    if (violation) { label = "BLOCKED"; cls = "bg-red-500/10 text-red-400";    dot = "bg-red-500"; }
    else           { label = "ALLOWED"; cls = "bg-[--accent]/10 text-[--accent]"; dot = "bg-[--accent]"; }
  }
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

export default async function DashboardPage() {
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

  // Scope all queries to the authenticated user's email.
  const { data: tenantData } = await supabase
    .from("tenants")
    .select("email, tier, stripe_subscription_id, api_key, seats_used, seats_total, created_at")
    .eq("email", user.email)
    .single();

  const tenant = tenantData as Tenant | null;

  // Fetch a wide window, then drop engine health pings — they are not anomalies
  // (they only feed the Phantom Engine status card) and must not pollute the
  // anomaly table or the stats.
  const { data: eventsData } = tenant
    ? await supabase
        .from("anomaly_events")
        .select("id, tenant_identity, trace_id, anomaly_metadata, audit_mode, created_at")
        .eq("tenant_identity", user.email)
        .order("created_at", { ascending: false })
        .limit(100)
    : { data: [] };

  const events = ((eventsData ?? []) as AnomalyEvent[])
    .filter((e) => !HEALTH_ACTIONS.includes((e.anomaly_metadata?.action_taken ?? "").toUpperCase()))
    .slice(0, 20);

  // A "block" only happens in enforce mode; audit-mode violations are "flagged".
  const blockedCount = events.filter((e) => isViolation(e) && !e.audit_mode).length;
  const flaggedCount = events.filter((e) => isViolation(e) && e.audit_mode).length;
  const totalBytes = events.reduce((acc, e) => {
    const b = e.anomaly_metadata?.bytes_severed;
    return acc + (typeof b === "number" ? b : 0);
  }, 0);

  const stats = [
    { label: "Events", value: events.length.toLocaleString(), delta: "last 20 shown" },
    { label: "Blocked", value: blockedCount.toLocaleString(), delta: flaggedCount > 0 ? `${flaggedCount} flagged in audit mode` : "enforce mode" },
    { label: "Bytes Inspected", value: totalBytes > 0 ? `${(totalBytes / 1024).toFixed(1)} KB` : "—", delta: "across shown events" },
    { label: "Active Traces", value: new Set(events.map((e) => e.trace_id)).size.toLocaleString(), delta: "unique trace IDs" },
  ];

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

  const seatsUsed = tenant.seats_used ?? 1;
  const seatsTotal = tenant.seats_total ?? 10;

  // Anonymized cross-tenant benchmarks (same computation as GET /api/v1/benchmarks).
  // Rendered server-side so the tenant's API key is never shipped to the browser.
  const benchmarks = await computeBenchmarks(supabase, user.email);
  const pct = (v: number | null) => (v == null ? "—" : `${(v * 100).toFixed(1)}%`);
  const num = (v: number | null) => (v == null ? "—" : v.toLocaleString());
  const hasPeerData = benchmarks.peer_p50_calls_7d != null;

  return (
    <main className="min-h-screen">
      {/* Top bar */}
      <header className="border-b border-[--border] bg-[--surface]/60 px-6 py-4 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-2.5 font-bold tracking-tight">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[--accent]/10 text-sm font-black text-[--accent]">∅</span>
              <span className="text-sm font-semibold tracking-wider text-[--foreground]">VANTIO</span>
            </span>
            <span className="rounded-full bg-[--accent]/15 px-2.5 py-0.5 text-xs font-bold text-[--accent]">PRO</span>
          </div>
          <div className="flex items-center gap-4 text-sm text-[--muted]">
            <span className="hidden sm:inline">{tenant.email}</span>
            <Link
              href="/dashboard/policy"
              className="rounded-lg border border-[--border-2] bg-[--surface-2] px-4 py-1.5 text-xs font-semibold text-[--foreground] transition-all hover:border-[--accent]/40 hover:text-[--accent]"
            >
              Policy
            </Link>
            <BillingPortalButton />
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[--foreground]">Pro Control Plane</h1>
          <p className="mt-1 text-sm text-[--muted]">
            Real-time SDK enforcement telemetry.{" "}
            {tenant.stripe_subscription_id && (
              <code className="rounded bg-[--surface-2] px-1.5 py-0.5 text-xs text-[--muted]">
                {tenant.stripe_subscription_id}
              </code>
            )}
          </p>
        </div>

        {/* Stats */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-2xl border border-[--border] bg-[--surface] p-5 transition-all hover:border-[--border-2]">
              <p className="text-xs font-medium uppercase tracking-widest text-[--muted]">{s.label}</p>
              <p className="mt-2 text-3xl font-bold text-[--foreground]">{s.value}</p>
              <p className="mt-1 text-xs text-[--muted]">{s.delta}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Event table */}
          <div className="lg:col-span-2">
            <div className="rounded-2xl border border-[--border] bg-[--surface]">
              <div className="flex items-center justify-between border-b border-[--border] px-6 py-4">
                <h2 className="text-sm font-semibold text-[--foreground]">Anomaly Events</h2>
                <a
                  href="/api/v1/export"
                  download
                  className="rounded-lg border border-[--border-2] px-3 py-1 text-xs font-medium text-[--muted] transition-colors hover:border-[--accent]/40 hover:text-[--accent]"
                >
                  Export CSV
                </a>
              </div>
              {events.length === 0 ? (
                <div className="px-6 py-12 text-center text-sm text-[--muted]">
                  No events yet. Wrap your agent with{" "}
                  <code className="rounded bg-[--surface-2] px-1">withVantio()</code> to start tracing.
                </div>
              ) : (
                <div className="divide-y divide-[--border]">
                  {events.map((evt) => (
                    <div key={evt.id} className="flex items-center gap-4 px-6 py-4 text-sm transition-colors hover:bg-[--surface-2]/50">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-xs text-[--foreground]/80">{evt.trace_id}</p>
                        <p className="mt-0.5 text-xs text-[--muted]">
                          {evt.anomaly_metadata?.pid && <>PID {evt.anomaly_metadata.pid} · </>}
                          {evt.anomaly_metadata?.bytes_severed != null && <>{evt.anomaly_metadata.bytes_severed.toLocaleString()} bytes · </>}
                          {evt.anomaly_metadata?.target_host && <>{evt.anomaly_metadata.target_host} · </>}
                          {new Date(evt.created_at).toLocaleTimeString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {evt.audit_mode && (
                          <span className="rounded bg-blue-400/10 px-1.5 py-0.5 text-xs font-medium text-blue-400">
                            AUDIT
                          </span>
                        )}
                        <EventStatusBadge evt={evt} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-5">
            {/* Seat usage */}
            <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
              <h3 className="mb-4 text-sm font-semibold text-[--foreground]">Seat Usage</h3>
              <div className="mb-2 flex justify-between text-xs text-[--muted]">
                <span>{seatsUsed} active</span>
                <span>{seatsTotal} total</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-[--surface-2]">
                <div
                  className="h-full rounded-full bg-[--accent]"
                  style={{ width: `${Math.min((seatsUsed / seatsTotal) * 100, 100)}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-[--muted]">{seatsTotal - seatsUsed} seats remaining</p>
            </div>

            {/* API Key */}
            {tenant.api_key && (
              <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
                <h3 className="mb-3 text-sm font-semibold text-[--foreground]">API Key</h3>
                <code className="block break-all rounded-lg bg-black/40 p-2.5 text-xs text-[--accent]">
                  {tenant.api_key.slice(0, 16)}•••••••••••••••••
                </code>
                <p className="mt-2 text-xs text-[--muted]">
                  Use as{" "}
                  <code className="rounded bg-[--surface-2] px-1">VANTIO_API_KEY</code>{" "}
                  in your agent environment.
                </p>
              </div>
            )}

            {/* Phantom Engine status — shown for Enterprise tenants */}
            {tenant.tier === "ENTERPRISE" && (
              <div className="rounded-2xl border border-red-400/20 bg-red-500/5 p-5">
                <h3 className="mb-4 text-sm font-semibold text-[--foreground]">Phantom Engine</h3>
                <PhantomEngineStatus tenantEmail={tenant.email} />
              </div>
            )}

            {/* Benchmarks — anonymized peer comparison */}
            <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
              <h3 className="text-sm font-semibold text-[--foreground]">Benchmarks</h3>
              <p className="mb-4 mt-0.5 text-xs text-[--muted]">Anonymized peers · last 7 days</p>
              <ul className="space-y-2.5">
                {[
                  { label: "Your calls", value: num(benchmarks.your_calls_7d) },
                  { label: "Peer median", value: num(benchmarks.peer_p50_calls_7d) },
                  { label: "Peer p90", value: num(benchmarks.peer_p90_calls_7d) },
                  { label: "Your block rate", value: pct(benchmarks.your_block_rate) },
                  { label: "Peer block rate", value: pct(benchmarks.peer_block_rate) },
                ].map((item) => (
                  <li key={item.label} className="flex items-center justify-between text-xs">
                    <span className="text-[--muted]">{item.label}</span>
                    <span className="font-mono font-medium text-[--foreground]">{item.value}</span>
                  </li>
                ))}
              </ul>
              {benchmarks.top_hosts.length > 0 && (
                <div className="mt-4 border-t border-[--border] pt-3">
                  <p className="mb-2 text-xs font-medium uppercase tracking-widest text-[--muted]">Top hosts</p>
                  <ul className="space-y-1.5">
                    {benchmarks.top_hosts.map((h) => (
                      <li key={h.host} className="flex items-center justify-between text-xs">
                        <span className="truncate font-mono text-[--foreground]/80">{h.host}</span>
                        <span className="ml-2 shrink-0 text-[--muted]">{(h.share * 100).toFixed(0)}%</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!hasPeerData && (
                <p className="mt-4 border-t border-[--border] pt-3 text-xs text-[--muted]">
                  Peer percentiles appear once enough tenants are active. Your own usage is shown above.
                </p>
              )}
            </div>

            {/* SDK enforcement status */}
            <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
              <h3 className="mb-4 text-sm font-semibold text-[--foreground]">SDK Enforcement</h3>
              <ul className="space-y-2.5">
                {[
                  { label: "Policy Sync", status: "Active" },
                  { label: "Anomaly Ledger", status: "Writing" },
                  { label: "RLS Policies", status: "Enforced" },
                  { label: "90-day Retention", status: "Active" },
                ].map((item) => (
                  <li key={item.label} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-[--muted]">{item.label}</span>
                    <span className="flex items-center gap-1 font-medium text-[--accent]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
                      {item.status}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 border-t border-[--border] pt-3">
                <p className="text-xs text-[--muted]">
                  Ring-0 enforcement on{" "}
                  <a href="/auth/enterprise" className="text-[--accent]/80 underline hover:text-[--accent]">Enterprise</a>.
                </p>
              </div>
            </div>

            {/* Quick install */}
            <div className="rounded-2xl border border-[--border] bg-[--surface] p-5">
              <h3 className="mb-3 text-sm font-semibold text-[--foreground]">Quick Install</h3>
              <pre className="overflow-x-auto rounded-lg bg-black/40 p-3 text-xs leading-relaxed text-[--foreground]/70">
                <code>{`npm i @vantio/agent-sdk

import { withVantio } from
  "@vantio/agent-sdk";

await withVantio(async () => {
  await runMyAgent();
});`}</code>
              </pre>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
