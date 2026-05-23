import type { Metadata } from "next";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";

export const metadata: Metadata = {
  title: "Dashboard — Vantio AI SMB",
  description: "Your Vantio AI PRO tenant dashboard.",
};

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
  seats_used: number | null;
  seats_total: number | null;
  created_at: string;
}

interface AnomalyEvent {
  id: string;
  tenant_identity: string;
  trace_id: string;
  event_payload: string | null;
  audit_mode: boolean;
  created_at: string;
}

function StatusBadge({ auditMode }: { auditMode: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        auditMode ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${auditMode ? "bg-red-500" : "bg-green-500"}`} />
      {auditMode ? "SEVERED" : "PASSED"}
    </span>
  );
}

export default async function DashboardPage() {
  const supabase = getSupabaseAdmin();

  // Fetch the first PRO tenant for demo — in production this is gated by auth session.
  const { data: tenantData } = await supabase
    .from("tenants")
    .select("email, tier, stripe_subscription_id, seats_used, seats_total, created_at")
    .eq("tier", "PRO")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  const tenant = tenantData as Tenant | null;

  // Fetch the 20 most recent anomaly events for this tenant.
  const { data: eventsData } = tenant
    ? await supabase
        .from("anomaly_events")
        .select("id, tenant_identity, trace_id, event_payload, audit_mode, created_at")
        .eq("tenant_identity", tenant.email)
        .order("created_at", { ascending: false })
        .limit(20)
    : { data: [] };

  const events = (eventsData ?? []) as AnomalyEvent[];

  const severedCount = events.filter((e) => e.audit_mode).length;
  const totalBytes = events.reduce((acc, e) => {
    try {
      const p = e.event_payload ? JSON.parse(e.event_payload) : null;
      return acc + (typeof p?.bytes === "number" ? p.bytes : 0);
    } catch {
      return acc;
    }
  }, 0);

  const stats = [
    { label: "Events Today", value: events.length.toLocaleString(), delta: "last 20 shown" },
    { label: "Payloads Severed", value: severedCount.toLocaleString(), delta: `${events.length ? Math.round((severedCount / events.length) * 100) : 0}% of total` },
    { label: "Bytes Blocked", value: totalBytes > 0 ? `${(totalBytes / 1024).toFixed(1)} KB` : "—", delta: "Ring-0 boundary" },
    { label: "Active Traces", value: new Set(events.map((e) => e.trace_id)).size.toLocaleString(), delta: "unique trace IDs" },
  ];

  if (!tenant) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-sm text-gray-500">No PRO tenant found.</p>
          <Link href="/pricing" className="mt-4 inline-block text-sm font-medium text-gray-900 underline">
            Upgrade to PRO →
          </Link>
        </div>
      </main>
    );
  }

  const seatsUsed = tenant.seats_used ?? 1;
  const seatsTotal = tenant.seats_total ?? 10;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-bold tracking-tight text-gray-900">[ ∅ ] Vantio AI</span>
            <span className="rounded-full bg-gray-900 px-2.5 py-0.5 text-xs font-bold text-white">PRO</span>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{tenant.email}</span>
            <Link href="/pricing" className="font-medium text-gray-700 hover:text-gray-900">
              Manage Plan
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">SMB Control Plane</h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time Ring-0 enforcement telemetry.{" "}
            {tenant.stripe_subscription_id && (
              <code className="rounded bg-gray-100 px-1 py-0.5 text-xs text-gray-600">
                {tenant.stripe_subscription_id}
              </code>
            )}
          </p>
        </div>

        {/* Stats */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl border border-gray-200 bg-white p-5">
              <p className="text-xs font-medium uppercase tracking-widest text-gray-400">{s.label}</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">{s.value}</p>
              <p className="mt-1 text-xs text-gray-400">{s.delta}</p>
            </div>
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Event table */}
          <div className="lg:col-span-2">
            <div className="rounded-xl border border-gray-200 bg-white">
              <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
                <h2 className="text-sm font-semibold text-gray-900">Anomaly Events</h2>
                <span className="text-xs text-gray-400">Live from Supabase ledger</span>
              </div>
              {events.length === 0 ? (
                <div className="px-6 py-12 text-center text-sm text-gray-400">
                  No events yet. Wrap your agent with{" "}
                  <code className="rounded bg-gray-100 px-1">withVantio()</code> to start tracing.
                </div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {events.map((evt) => (
                    <div key={evt.id} className="flex items-center gap-4 px-6 py-4 text-sm">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-xs text-gray-500">{evt.trace_id}</p>
                        <p className="mt-0.5 text-xs text-gray-400">
                          {evt.tenant_identity} · {new Date(evt.created_at).toLocaleTimeString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {evt.audit_mode && (
                          <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-600">
                            AUDIT
                          </span>
                        )}
                        <StatusBadge auditMode={evt.audit_mode} />
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
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold text-gray-900">Seat Usage</h3>
              <div className="mb-2 flex justify-between text-xs text-gray-500">
                <span>{seatsUsed} active</span>
                <span>{seatsTotal} total</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-gray-900"
                  style={{ width: `${Math.min((seatsUsed / seatsTotal) * 100, 100)}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-gray-400">{seatsTotal - seatsUsed} seats remaining</p>
            </div>

            {/* Phantom Engine status */}
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold text-gray-900">Phantom Engine</h3>
              <ul className="space-y-2.5">
                {[
                  { label: "vantio-loader", status: "Running" },
                  { label: "vantio_trace_map", status: "Pinned" },
                  { label: "sched_process_fork", status: "Attached" },
                  { label: "ssl_write uprobe", status: "Attached" },
                ].map((item) => (
                  <li key={item.label} className="flex items-center justify-between text-xs">
                    <span className="font-mono text-gray-600">{item.label}</span>
                    <span className="flex items-center gap-1 font-medium text-green-600">
                      <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                      {item.status}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Quick install */}
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <h3 className="mb-3 text-sm font-semibold text-gray-900">Quick Install</h3>
              <pre className="overflow-x-auto rounded-lg bg-gray-950 p-3 text-xs leading-relaxed text-gray-300">
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
