"use client";

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";

interface EngineEvent {
  created_at: string;
  anomaly_metadata: {
    action_taken?: string;
    pid?: number;
  } | null;
}

export function PhantomEngineStatus({ tenantEmail }: { tenantEmail: string }) {
  const [status, setStatus] = useState<"checking" | "active" | "offline">("checking");
  const [lastSeen, setLastSeen] = useState<string | null>(null);
  const [pid, setPid] = useState<number | null>(null);

  useEffect(() => {
    const supabase = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );

    async function check() {
      // The loader emits ENGINE_STARTED at startup and ENGINE_HEARTBEAT every
      // 4 minutes. A 10-minute window tolerates an occasional dropped ping
      // without flapping to Offline, while still catching a truly dead engine.
      const since = new Date(Date.now() - 10 * 60 * 1000).toISOString();
      const { data } = await supabase
        .from("anomaly_events")
        .select("created_at, anomaly_metadata")
        .eq("tenant_identity", tenantEmail)
        .gte("created_at", since)
        .order("created_at", { ascending: false })
        .limit(10);

      // Find the most recent engine health ping (ignoring ordinary anomalies).
      const health = (data as EngineEvent[] | null)?.find((e) => {
        const a = (e.anomaly_metadata?.action_taken ?? "").toUpperCase();
        return a === "ENGINE_STARTED" || a === "ENGINE_HEARTBEAT";
      });

      if (health) {
        setStatus("active");
        setLastSeen(health.created_at);
        setPid(health.anomaly_metadata?.pid ?? null);
      } else {
        setStatus("offline");
      }
    }

    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [tenantEmail]);

  const items = [
    {
      label: "Engine Status",
      value: status === "checking" ? "Checking..." : status === "active" ? "Running" : "Offline",
      color: status === "active" ? "text-[var(--accent)]" : status === "offline" ? "text-red-400" : "text-[var(--muted)]",
      dot: status === "active" ? "bg-[var(--accent)]" : status === "offline" ? "bg-red-400" : "bg-[var(--muted)]",
    },
    { label: "Loader PID", value: pid ? String(pid) : "—", color: "text-[var(--foreground)]/80", dot: null },
    { label: "Last heartbeat", value: lastSeen ? new Date(lastSeen).toLocaleTimeString() : "—", color: "text-[var(--foreground)]/80", dot: null },
    { label: "Trace map", value: "/sys/fs/bpf/vantio_trace_map", color: "text-red-400", dot: null },
  ];

  return (
    <ul className="space-y-2.5">
      {items.map(({ label, value, color, dot }) => (
        <li key={label} className="flex items-center justify-between text-xs">
          <span className="font-mono text-[var(--muted)]">{label}</span>
          <span className={`flex items-center gap-1 font-medium ${color}`}>
            {dot && <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />}
            {value}
          </span>
        </li>
      ))}
      {status === "offline" && (
        <li className="pt-2 text-xs text-[var(--muted)]">
          Start with:{" "}
          <code className="rounded bg-[var(--surface-2)] px-1">sudo vantio-loader</code>
        </li>
      )}
    </ul>
  );
}
