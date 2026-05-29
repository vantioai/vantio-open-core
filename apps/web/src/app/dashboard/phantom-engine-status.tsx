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
      // Look for ENGINE_STARTED event in the last 5 minutes
      const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
      const { data } = await supabase
        .from("anomaly_events")
        .select("created_at, anomaly_metadata")
        .eq("tenant_identity", tenantEmail)
        .gte("created_at", fiveMinutesAgo)
        .order("created_at", { ascending: false })
        .limit(1);

      if (data && data.length > 0) {
        const evt = data[0] as EngineEvent;
        const action = evt.anomaly_metadata?.action_taken;
        if (action === "ENGINE_STARTED") {
          setStatus("active");
          setLastSeen(evt.created_at);
          setPid(evt.anomaly_metadata?.pid ?? null);
          return;
        }
      }
      setStatus("offline");
    }

    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, [tenantEmail]);

  const items = [
    {
      label: "Engine Status",
      value: status === "checking" ? "Checking..." : status === "active" ? "Running" : "Offline",
      color: status === "active" ? "text-green-600" : status === "offline" ? "text-red-500" : "text-gray-400",
      dot: status === "active" ? "bg-green-500" : status === "offline" ? "bg-red-400" : "bg-gray-300",
    },
    { label: "Loader PID", value: pid ? String(pid) : "—", color: "text-gray-600", dot: null },
    { label: "Last heartbeat", value: lastSeen ? new Date(lastSeen).toLocaleTimeString() : "—", color: "text-gray-600", dot: null },
    { label: "Trace map", value: "/sys/fs/bpf/vantio_trace_map", color: "text-red-500", dot: null },
  ];

  return (
    <ul className="space-y-2.5">
      {items.map(({ label, value, color, dot }) => (
        <li key={label} className="flex items-center justify-between text-xs">
          <span className="font-mono text-gray-600">{label}</span>
          <span className={`flex items-center gap-1 font-medium ${color}`}>
            {dot && <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />}
            {value}
          </span>
        </li>
      ))}
      {status === "offline" && (
        <li className="pt-2 text-xs text-gray-400">
          Start with:{" "}
          <code className="rounded bg-gray-100 px-1">sudo vantio-loader</code>
        </li>
      )}
    </ul>
  );
}
