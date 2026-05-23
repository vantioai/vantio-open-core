import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Dashboard — Vantio AI SMB",
  description: "Your Vantio AI PRO tenant dashboard.",
};

// Simulated data representing what a real SMB tenant would see
// once the Supabase tenant table is wired to a server component.
const mockTenant = {
  email: "ops@acme-corp.io",
  tier: "PRO",
  stripe_subscription_id: "sub_1QxABC123def456",
  seats_used: 3,
  seats_total: 10,
};

const mockRecentEvents = [
  {
    id: "evt_001",
    trace_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    pid: 18243,
    action: "SEVERED",
    bytes: 14382,
    audit_mode: true,
    timestamp: "2026-05-22T22:18:04.000Z",
  },
  {
    id: "evt_002",
    trace_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    pid: 18299,
    action: "SEVERED",
    bytes: 8910,
    audit_mode: true,
    timestamp: "2026-05-22T22:17:51.000Z",
  },
  {
    id: "evt_003",
    trace_id: "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    pid: 18243,
    action: "PASSED",
    bytes: 512,
    audit_mode: false,
    timestamp: "2026-05-22T22:17:33.000Z",
  },
  {
    id: "evt_004",
    trace_id: "c9d8e7f6-5432-10ab-cdef-987654321fed",
    pid: 19012,
    action: "SEVERED",
    bytes: 22100,
    audit_mode: true,
    timestamp: "2026-05-22T22:16:55.000Z",
  },
];

const stats = [
  { label: "Events Today", value: "1,284", delta: "+12% vs yesterday" },
  { label: "Payloads Severed", value: "1,101", delta: "85.7% of total" },
  { label: "Bytes Blocked", value: "4.2 MB", delta: "Ring-0 boundary" },
  { label: "Active Traces", value: "7", delta: "3 agents running" },
];

function StatusBadge({ action }: { action: string }) {
  const isSevered = action === "SEVERED";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        isSevered
          ? "bg-red-50 text-red-700"
          : "bg-green-50 text-green-700"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${isSevered ? "bg-red-500" : "bg-green-500"}`}
      />
      {action}
    </span>
  );
}

export default function DashboardPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-bold tracking-tight text-gray-900">
              [ ∅ ] Vantio AI
            </span>
            <span className="rounded-full bg-gray-900 px-2.5 py-0.5 text-xs font-bold text-white">
              PRO
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-500">
            <span>{mockTenant.email}</span>
            <Link
              href="/pricing"
              className="font-medium text-gray-700 hover:text-gray-900"
            >
              Manage Plan
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Page title */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">
            SMB Control Plane
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Real-time Ring-0 enforcement telemetry for your LLM agents.
            Subscription:{" "}
            <code className="rounded bg-gray-100 px-1 py-0.5 text-xs text-gray-600">
              {mockTenant.stripe_subscription_id}
            </code>
          </p>
        </div>

        {/* Stats row */}
        <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div
              key={s.label}
              className="rounded-xl border border-gray-200 bg-white p-5"
            >
              <p className="text-xs font-medium uppercase tracking-widest text-gray-400">
                {s.label}
              </p>
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
                <h2 className="text-sm font-semibold text-gray-900">
                  Recent Anomaly Events
                </h2>
                <span className="text-xs text-gray-400">
                  TrueTime Ledger — last 90 days
                </span>
              </div>
              <div className="divide-y divide-gray-50">
                {mockRecentEvents.map((evt) => (
                  <div
                    key={evt.id}
                    className="flex items-center gap-4 px-6 py-4 text-sm"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-mono text-xs text-gray-500">
                        {evt.trace_id}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-400">
                        PID {evt.pid} · {evt.bytes.toLocaleString()} bytes ·{" "}
                        {new Date(evt.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {evt.audit_mode && (
                        <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-600">
                          AUDIT
                        </span>
                      )}
                      <StatusBadge action={evt.action} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="border-t border-gray-100 px-6 py-3">
                <button className="text-xs font-medium text-gray-400 hover:text-gray-700">
                  View full ledger →
                </button>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-5">
            {/* Seat usage */}
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold text-gray-900">
                Seat Usage
              </h3>
              <div className="mb-2 flex justify-between text-xs text-gray-500">
                <span>{mockTenant.seats_used} active</span>
                <span>{mockTenant.seats_total} total</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
                <div
                  className="h-full rounded-full bg-gray-900"
                  style={{
                    width: `${(mockTenant.seats_used / mockTenant.seats_total) * 100}%`,
                  }}
                />
              </div>
              <p className="mt-3 text-xs text-gray-400">
                {mockTenant.seats_total - mockTenant.seats_used} seats remaining
              </p>
            </div>

            {/* Phantom Engine status */}
            <div className="rounded-xl border border-gray-200 bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold text-gray-900">
                Phantom Engine
              </h3>
              <ul className="space-y-2.5">
                {[
                  { label: "vantio-loader", status: "Running" },
                  { label: "vantio_trace_map", status: "Pinned" },
                  {
                    label: "sched_process_fork",
                    status: "Attached",
                  },
                  { label: "raw_syscalls probe", status: "Attached" },
                  { label: "ssl_write uprobe", status: "Attached" },
                ].map((item) => (
                  <li
                    key={item.label}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="font-mono text-gray-600">
                      {item.label}
                    </span>
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
              <h3 className="mb-3 text-sm font-semibold text-gray-900">
                Quick Install
              </h3>
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
