import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import {
  sendTenantAnomalyAlert,
  type AnomalyAlertRecord,
  type TenantAlertSettings,
} from "@/lib/alerts";

// Optional alternate trigger for per-tenant anomaly alerts: a Supabase DB
// webhook on INSERT into anomaly_events. The primary trigger is now the ingest
// route (which fires inline), but this route is kept working so alerts can also
// be driven by the DB if configured. All sending goes through the SINGLE shared
// implementation in lib/alerts.ts. Runs on the Node runtime.
export const runtime = "nodejs";

// Lazy service-role client — used only to look up the tenant's own alert routing.
function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  // Verify the request is from Supabase using a shared secret.
  // Fail closed: if the secret is not configured the endpoint must not be open.
  const webhookSecret = process.env.SUPABASE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json(
      { error: "Webhook secret not configured." },
      { status: 503 }
    );
  }
  const authHeader = req.headers.get("authorization");
  if (authHeader !== `Bearer ${webhookSecret}`) {
    return NextResponse.json({ error: "Unauthorized." }, { status: 401 });
  }

  let body: { type?: string; record?: AnomalyAlertRecord };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  // Supabase sends type: "INSERT" | "UPDATE" | "DELETE"
  if (body.type !== "INSERT" || !body.record) {
    return NextResponse.json({ ok: true });
  }
  const record = body.record;

  // Look up THIS tenant's own alert settings by tenant_identity (= the tenant's
  // email), then delegate to the shared send path.
  const supabase = getSupabaseAdmin();
  const { data: tenantRow } = await supabase
    .from("tenants")
    .select("alerts_enabled, alert_slack_webhook_url, alert_email")
    .eq("email", record.tenant_identity)
    .maybeSingle();

  const tenant = tenantRow as TenantAlertSettings | null;

  // Unknown tenant → ack and do nothing.
  if (!tenant) {
    return NextResponse.json({ ok: true, skipped: "no tenant" });
  }

  await sendTenantAnomalyAlert(tenant, record);

  return NextResponse.json({ ok: true });
}
