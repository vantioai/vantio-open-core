import { NextResponse } from "next/server";
import { createClient }             from "@supabase/supabase-js";
import { createServerClient }       from "@supabase/ssr";
import { cookies }                  from "next/headers";

function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}

interface AnomalyRow {
  id:               string;
  trace_id:         string;
  audit_mode:       boolean;
  created_at:       string;
  anomaly_metadata: {
    bytes_severed?: number | null;
    pid?:           number | null;
    timestamp_ns?:  number | null;
    target_host?:   string | null;
    action_taken?:  string | null;
  } | null;
}

function toCSV(rows: AnomalyRow[]): string {
  const headers = [
    "id",
    "trace_id",
    "target_host",
    "action_taken",
    "bytes_severed",
    "pid",
    "timestamp_ns",
    "audit_mode",
    "created_at",
  ];

  const escape = (v: unknown): string => {
    if (v == null) return "";
    const s = String(v);
    return s.includes(",") || s.includes('"') || s.includes("\n")
      ? `"${s.replace(/"/g, '""')}"`
      : s;
  };

  const lines = [
    headers.join(","),
    ...rows.map((r) =>
      [
        r.id,
        r.trace_id,
        r.anomaly_metadata?.target_host ?? "",
        r.anomaly_metadata?.action_taken ?? "",
        r.anomaly_metadata?.bytes_severed ?? "",
        r.anomaly_metadata?.pid ?? "",
        r.anomaly_metadata?.timestamp_ns ?? "",
        r.audit_mode,
        r.created_at,
      ]
        .map(escape)
        .join(",")
    ),
  ];

  return lines.join("\r\n");
}

export async function GET(): Promise<NextResponse> {
  // ── Auth gate ─────────────────────────────────────────────────────────────
  const cookieStore = await cookies();
  const authClient  = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();

  if (!user?.email) {
    return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });
  }

  // ── Fetch all events for this tenant ──────────────────────────────────────
  const supabase = getSupabaseAdmin();
  const { data, error } = await supabase
    .from("anomaly_events")
    .select("id, trace_id, anomaly_metadata, audit_mode, created_at")
    .eq("tenant_identity", user.email)
    .order("created_at", { ascending: false })
    .limit(10000);

  if (error) {
    return NextResponse.json({ error: "Failed to fetch events." }, { status: 500 });
  }

  const csv      = toCSV((data ?? []) as AnomalyRow[]);
  const filename = `vantio-anomaly-events-${new Date().toISOString().slice(0, 10)}.csv`;

  return new NextResponse(csv, {
    status:  200,
    headers: {
      "Content-Type":        "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
