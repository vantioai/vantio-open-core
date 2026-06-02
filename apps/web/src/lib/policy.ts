// Shared Tier 2 policy contract.
// This is the cloud-managed policy served by GET /api/v1/config and edited
// through the dashboard policy editor. The ACTUAL enforcement (PII redaction,
// spend caps, host/policy blocking) runs client-side in the customer's
// SDK/CLI — Vantio only stores and serves these rules. No prompt content,
// completions, or PII ever live in a policy.

export interface TenantPolicy {
  enforce:           boolean;
  redact_pii:        boolean;
  pii_types:         string[];
  allowed_hosts:     string[];
  blocked_hosts:     string[];
  max_request_bytes: number;
  spend_cap_usd:     number;
}

// Permissive default — the SDK "fails open" so free tenants and tenants
// without a saved policy are never broken.
export const DEFAULT_POLICY: TenantPolicy = {
  enforce:           false,
  redact_pii:        false,
  pii_types:         [],
  allowed_hosts:     [],
  blocked_hosts:     [],
  max_request_bytes: 0,
  spend_cap_usd:     0,
};

// Categories the SDK knows how to redact. The editor offers exactly these,
// and the write path filters incoming values to this allowlist.
//
// Canonical storage is LOWERCASE so the values line up 1:1 with the SDK/CLI
// pattern keys (PII_PATTERNS in interceptor.cjs and the SDK's redactPII).
// Mismatched case here used to silently disable cloud-driven redaction.
export const PII_TYPES = [
  "email",
  "phone",
  "ssn",
  "credit_card",
  "ip_address",
  "api_key",
  "person_name",
  "address",
] as const;

export type PiiType = (typeof PII_TYPES)[number];

// Human-friendly labels for the dashboard editor. The stored value stays
// lowercase/canonical; only the display text is prettified.
export const PII_TYPE_LABELS: Record<PiiType, string> = {
  email:       "Email",
  phone:       "Phone",
  ssn:         "SSN",
  credit_card: "Credit Card",
  ip_address:  "IP Address",
  api_key:     "API Key",
  person_name: "Person Name",
  address:     "Address",
};

const MAX_HOSTS      = 200;
const MAX_HOST_LEN   = 255;
const MAX_BYTES      = 1_000_000_000; // 1 GB ceiling on max_request_bytes
const MAX_SPEND_USD  = 1_000_000;

function sanitizeHosts(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const out = new Set<string>();
  for (const h of raw) {
    if (typeof h !== "string") continue;
    const host = h.trim().toLowerCase().slice(0, MAX_HOST_LEN);
    if (host.length > 0) out.add(host);
    if (out.size >= MAX_HOSTS) break;
  }
  return Array.from(out);
}

function sanitizePiiTypes(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const allow = new Set<string>(PII_TYPES);
  const out = new Set<string>();
  for (const t of raw) {
    if (typeof t !== "string") continue;
    // Normalize to the canonical lowercase form so values match the SDK/CLI
    // pattern keys. Accepts any case on input (e.g. legacy "EMAIL").
    const lower = t.trim().toLowerCase();
    if (allow.has(lower)) out.add(lower);
  }
  return Array.from(out);
}

function clampNumber(raw: unknown, min: number, max: number): number {
  const n = typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(n) || n < min) return min;
  return Math.min(n, max);
}

/**
 * Normalize an untrusted policy payload into a safe TenantPolicy. Unknown
 * fields are dropped; only the allowlisted policy fields are ever persisted.
 */
export function sanitizePolicy(raw: unknown): TenantPolicy {
  const b = (typeof raw === "object" && raw !== null ? raw : {}) as Record<string, unknown>;
  return {
    enforce:           b["enforce"] === true,
    redact_pii:        b["redact_pii"] === true,
    pii_types:         sanitizePiiTypes(b["pii_types"]),
    allowed_hosts:     sanitizeHosts(b["allowed_hosts"]),
    blocked_hosts:     sanitizeHosts(b["blocked_hosts"]),
    max_request_bytes: Math.floor(clampNumber(b["max_request_bytes"], 0, MAX_BYTES)),
    spend_cap_usd:     clampNumber(b["spend_cap_usd"], 0, MAX_SPEND_USD),
  };
}
