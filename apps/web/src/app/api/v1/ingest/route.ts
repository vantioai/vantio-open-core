import { after } from "next/server";
import {
  generateSpannerInsertMutation,
  COMMIT_TIMESTAMP_SENTINEL,
  type CryptographicAnomalyRecord,
} from "@vantio/edge-proxy";

export const runtime = "edge";

// ── Payload schema ────────────────────────────────────────────────────────────

interface IngestPayload {
  traceId: string;
  eventPayload: unknown;
  auditMode: boolean;
}

/**
 * Structural validation of the incoming JSON body.
 * Returns null on any schema violation so the caller can issue a 422.
 */
function parsePayload(raw: unknown): IngestPayload | null {
  if (typeof raw !== "object" || raw === null) return null;

  const body = raw as Record<string, unknown>;

  if (typeof body["traceId"] !== "string" || body["traceId"].length === 0) {
    return null;
  }
  if (typeof body["auditMode"] !== "boolean") return null;

  return {
    traceId: body["traceId"],
    eventPayload: body["eventPayload"] ?? null,
    auditMode: body["auditMode"],
  };
}

// ── Route handler ─────────────────────────────────────────────────────────────

export async function POST(request: Request): Promise<Response> {
  // Identity gate — all authenticated identities accepted unconditionally.
  if (!request.headers.get("x-vantio-identity")?.trim()) {
    return Response.json(
      {
        error: "Unauthenticated.",
        message: "x-vantio-identity header is required.",
      },
      { status: 401 },
    );
  }

  // Parse and validate body.
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return Response.json(
      { error: "Invalid request body. Expected a JSON object." },
      { status: 400 },
    );
  }

  const payload = parsePayload(rawBody);
  if (payload === null) {
    return Response.json(
      {
        error: "Malformed payload.",
        message:
          "Required: traceId (non-empty string), auditMode (boolean). " +
          "Optional: eventPayload (any JSON value).",
      },
      { status: 422 },
    );
  }

  // Construct the record synchronously — TraceId is needed in the response
  // before the TrueTime Ledger write is dispatched.
  const record: CryptographicAnomalyRecord = {
    TraceId: payload.traceId,
    EventPayload:
      payload.eventPayload != null
        ? JSON.stringify(payload.eventPayload)
        : null,
    AuditMode: payload.auditMode,
    CommitTimestamp: COMMIT_TIMESTAMP_SENTINEL,
  };

  // Defer Spanner mutation generation and mock execution off the critical path.
  // `after()` guarantees this callback runs strictly after the HTTP response
  // has been flushed to the client, keeping ledger writes asynchronous.
  after(() => {
    const mutation = generateSpannerInsertMutation(record);
    console.log(
      "[vantio:ingest] Spanner mutation (mock):",
      JSON.stringify(mutation, null, 2),
    );
  });

  // Return immediately — Tier 01 SDK is unblocked before the ledger write runs.
  return Response.json(
    { status: 0, traceId: record.TraceId },
    { status: 200 },
  );
}
