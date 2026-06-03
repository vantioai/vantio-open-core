import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { DEFAULT_POLICY, sanitizePolicy, type TenantPolicy } from "@/lib/policy";

// Tier 2 policy editor backend. Authenticated by the logged-in Supabase user
// (session cookie) — NOT by an API key. Reads/writes the caller's own
// tenant_policies row only. GET returns the saved policy (or the default);
// POST validates + upserts it. No prompt content or PII is ever stored here.

function getSupabaseAdmin() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { autoRefreshToken: false, persistSession: false } }
  );
}

async function getAuthedEmail(): Promise<string | null> {
  const cookieStore = await cookies();
  const authClient  = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await authClient.auth.getUser();
  return user?.email ?? null;
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

export async function GET(): Promise<NextResponse> {
  const email = await getAuthedEmail();
  if (!email) return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });

  const supabase = getSupabaseAdmin();
  const { data: tenant } = await supabase
    .from("tenants")
    .select("id")
    .eq("email", email)
    .single();

  if (!tenant) return NextResponse.json({ error: "No tenant found." }, { status: 404 });

  const { data } = await supabase
    .from("tenant_policies")
    .select("enforce, redact_pii, pii_types, allowed_hosts, blocked_hosts, max_request_bytes, spend_cap_usd")
    .eq("tenant_id", (tenant as { id: string }).id)
    .maybeSingle();

  return NextResponse.json({ policy: rowToPolicy(data as Record<string, unknown> | null) });
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const email = await getAuthedEmail();
  if (!email) return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });

  // Resolve the caller's tenant. We key the policy on tenant_id and only ever
  // touch the row belonging to the authenticated user's email.
  const supabase = getSupabaseAdmin();
  const { data: tenant, error: tenantErr } = await supabase
    .from("tenants")
    .select("id, email")
    .eq("email", email)
    .single();

  if (tenantErr || !tenant) {
    return NextResponse.json({ error: "No tenant found for this account." }, { status: 404 });
  }
  const t = tenant as { id: string; email: string };

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  // Accept either a bare policy object or { policy: {...} }.
  const candidate =
    typeof rawBody === "object" && rawBody !== null && "policy" in (rawBody as Record<string, unknown>)
      ? (rawBody as Record<string, unknown>)["policy"]
      : rawBody;

  const policy = sanitizePolicy(candidate);

  const { error: upsertErr } = await supabase
    .from("tenant_policies")
    .upsert(
      {
        tenant_id:         t.id,
        tenant_email:      t.email,
        ...policy,
        updated_at:        new Date().toISOString(),
      },
      { onConflict: "tenant_id" }
    );

  if (upsertErr) {
    console.error("[vantio:policy] upsert failed:", upsertErr);
    return NextResponse.json({ error: "Failed to save policy." }, { status: 500 });
  }

  return NextResponse.json({ ok: true, policy });
}
