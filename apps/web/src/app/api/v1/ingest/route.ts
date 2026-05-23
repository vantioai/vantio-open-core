import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

interface IngestPayload {
  traceId: string;
  eventPayload: unknown;
  auditMode: boolean;
}

function parsePayload(raw: unknown): IngestPayload | null {
  if (typeof raw !== "object" || raw === null) return null;
  const body = raw as Record<string, unknown>;
  if (typeof body["traceId"] !== "string" || body["traceId"].length === 0) return null;
  if (typeof body["auditMode"] !== "boolean") return null;
  return {
    traceId: body["traceId"],
    eventPayload: body["eventPayload"] ?? null,
    auditMode: body["auditMode"],
  };
}

function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) throw new Error("Missing Supabase env vars");
  return createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
}

export const runtime = "edge";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const identity = request.headers.get("x-vantio-identity")?.trim();
  if (!identity) {
    return NextResponse.json(
      { error: "Unauthenticated.", message: "x-vantio-identity header is required." },
      { status: 401 }
    );
  }

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid request body. Expected a JSON object." },
      { status: 400 }
    );
  }

  const payload = parsePayload(rawBody);
  if (!payload) {
    return NextResponse.json(
      {
        error: "Malformed payload.",
        message: "Required: traceId (non-empty string), auditMode (boolean). Optional: eventPayload (any JSON value).",
      },
      { status: 422 }
    );
  }

  // Payload Quarantine — absolute enforcement.
  // anomaly_metadata is strictly deterministic execution context only:
  // bytes_severed, pid, timestamp_ns, target_host, action_taken.
  // Linguistic content (prompts, responses, PII) is NEVER written here.
  // The ssl_write uprobe severs the buffer at Ring-0; the Layer-7 ledger
  // must reflect that severance by containing zero linguistic data.
  const buildAnomalyMetadata = (p: IngestPayload): Record<string, unknown> => {
    const raw =
      typeof p.eventPayload === "object" && p.eventPayload !== null
        ? (p.eventPayload as Record<string, unknown>)
        : {};
    return {
      bytes_severed:  typeof raw["bytes_severed"]  === "number" ? raw["bytes_severed"]  : null,
      pid:            typeof raw["pid"]             === "number" ? raw["pid"]             : null,
      timestamp_ns:   typeof raw["timestamp_ns"]   === "number" ? raw["timestamp_ns"]   : null,
      target_host:    typeof raw["target_host"]    === "string" ? raw["target_host"]    : null,
      action_taken:   typeof raw["action_taken"]   === "string" ? raw["action_taken"]   : null,
      // Explicitly omit any key that could carry linguistic content.
    };
  };

  const writeToSupabase = async () => {
    try {
      const supabase = getSupabaseAdmin();
      await supabase.from("anomaly_events").insert({
        tenant_identity: identity,
        trace_id: payload.traceId,
        anomaly_metadata: buildAnomalyMetadata(payload),
        audit_mode: payload.auditMode,
        created_at: new Date().toISOString(),
      });
    } catch (err) {
      console.error("[vantio:ingest] Supabase write failed:", err);
    }
  };

  // Non-blocking: use waitUntil if available (Vercel Edge), otherwise fire-and-forget.
  if (typeof (request as NextRequest & { waitUntil?: (p: Promise<unknown>) => void }).waitUntil === "function") {
    (request as NextRequest & { waitUntil: (p: Promise<unknown>) => void }).waitUntil(writeToSupabase());
  } else {
    void writeToSupabase();
  }

  return NextResponse.json(
    { status: 0, traceId: payload.traceId },
    { status: 200 }
  );
}
