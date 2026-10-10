/**
 * Pure evaluate helpers for the gate-mcp compatibility layer (Phantom Engine dry-run plane).
 * Mirrors interceptor normalizePolicy + host/size/spend checks without side effects.
 */

export const DEFAULT_POLICY = {
  enforce: false,
  redact_pii: false,
  pii_types: ["ssn", "email", "credit_card", "phone"],
  allowed_hosts: [],
  blocked_hosts: [],
  max_request_bytes: 0,
  spend_cap_usd: 0,
  dry_run: true,
};

export const UPGRADE_PATH = [
  {
    plane: "Observe",
    brand: "Vantio Optics",
    sku: "Free · Open Core",
    workflow: "Sight Loop",
    surface: "@vantio/optics-mcp",
  },
  {
    plane: "Observe + Enforce + Control",
    brand: "Vantio Phantom Engine",
    sku: "Contact Vantio",
    workflow: "Rogue Reconciliation",
    note: "Runtime protection on enrolled Linux hosts — Observe, Enforce, and Control in one purchase.",
    url: "https://vantio.ai/phantom",
  },
  {
    plane: "Enterprise",
    brand: "Enterprise",
    sku: "Talk to sales",
    workflow: "Governance + proof at scale",
    url: "https://vantio.ai/enterprise",
  },
];

function asBool(v, d) {
  return typeof v === "boolean" ? v : d;
}
function asStrArray(v, d) {
  return Array.isArray(v) ? v.filter((x) => typeof x === "string") : d.slice();
}
function asNonNegNum(v, d) {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n >= 0 ? n : d;
}

export function normalizePolicy(raw) {
  const p = raw && typeof raw === "object" ? raw : {};
  return {
    enforce: asBool(p.enforce, DEFAULT_POLICY.enforce),
    redact_pii: asBool(p.redact_pii, DEFAULT_POLICY.redact_pii),
    pii_types: asStrArray(p.pii_types, DEFAULT_POLICY.pii_types),
    allowed_hosts: asStrArray(p.allowed_hosts, DEFAULT_POLICY.allowed_hosts),
    blocked_hosts: asStrArray(p.blocked_hosts, DEFAULT_POLICY.blocked_hosts),
    max_request_bytes: asNonNegNum(p.max_request_bytes, DEFAULT_POLICY.max_request_bytes),
    spend_cap_usd: asNonNegNum(p.spend_cap_usd, DEFAULT_POLICY.spend_cap_usd),
    dry_run: asBool(p.dry_run, DEFAULT_POLICY.dry_run),
  };
}

/**
 * Evaluate a hypothetical request against a policy.
 * Always returns a decision object — never blocks network I/O from this MCP.
 *
 * @param {object} policyRaw
 * @param {{ hostname: string, request_bytes?: number, spent_usd?: number }} req
 */
export function evaluateRequest(policyRaw, req) {
  const policy = normalizePolicy(policyRaw);
  const hostname = String(req.hostname || "").toLowerCase();
  const requestBytes = Number(req.request_bytes) || 0;
  const spentUsd = Number(req.spent_usd) || 0;
  // This MCP does not preview host, size, or spend blocks. Runtime enforcement
  // is Phantom Engine, including regional hosts. A preview that only matches
  // exact names would disagree with that runtime, so the preview is not offered.
  return {
    plane: "Enforce",
    brand: "Phantom Engine",
    mode: "observe",
    would_block: false,
    primary_action: "OBSERVED",
    reasons: ["This MCP does not preview enforcement. Enforcement is provided by Phantom Engine."],
    policy,
    input: { hostname, request_bytes: requestBytes, spent_usd: spentUsd },
    decisions: [{ action: "OBSERVED", reason: "optics_observational" }],
    fence:
      "This MCP does not preview or apply policy. No network call was blocked. Enforcement is provided by Phantom Engine.",
  };
}

const DEFAULT_CONTROL_PLANE_BASE = "https://api.vantio.ai";

// Host that receives VANTIO_API_KEY. Environment only. Arguments are ignored.
export function controlPlaneBase() {
  const raw = process.env.VANTIO_API_BASE;
  if (typeof raw !== "string") return DEFAULT_CONTROL_PLANE_BASE;
  const trimmed = raw.trim().replace(/\/+$/, "");
  return trimmed || DEFAULT_CONTROL_PLANE_BASE;
}

export async function fetchCloudConfig() {
  const key = process.env.VANTIO_API_KEY;
  if (!key) {
    return {
      ok: false,
      error: "missing_api_key",
      hint: "Set VANTIO_API_KEY. Free Optics needs no key; Phantom Engine control-plane config requires a key.",
      policy: DEFAULT_POLICY,
    };
  }
  const base = controlPlaneBase();
  const res = await fetch(`${base}/api/v1/config`, {
    headers: {
      "x-vantio-identity": key,
      accept: "application/json",
    },
    // Bound the call so a stalled control plane cannot hang the MCP tool.
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    return {
      ok: false,
      error: `config_http_${res.status}`,
      policy: DEFAULT_POLICY,
    };
  }
  const body = await res.json();
  return {
    ok: true,
    tier: body.tier,
    policy: normalizePolicy(body.policy),
  };
}

export async function fetchResidualRisk() {
  const key = process.env.VANTIO_API_KEY;
  if (!key) {
    return {
      ok: false,
      error: "missing_api_key",
      hint: "Residual-risk ledger requires VANTIO_API_KEY.",
    };
  }
  const base = controlPlaneBase();
  const res = await fetch(`${base}/api/v1/residual-risk`, {
    headers: {
      "x-vantio-identity": key,
      accept: "application/json",
    },
    // Bound the call so a stalled control plane cannot hang the MCP tool.
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) {
    return { ok: false, error: `residual_http_${res.status}` };
  }
  const body = await res.json();
  return { ok: true, ...body };
}
