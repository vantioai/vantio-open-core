/**
 * Pure evaluate helpers for Gate MCP (dry-run plane).
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
    plane: "Enforce",
    brand: "Vantio Gate",
    sku: "Pro",
    workflow: "Rules that stick",
    surface: "@vantio/gate-mcp (this MCP — dry-run evaluate only)",
  },
  {
    plane: "Control",
    brand: "Vantio Phantom Engine",
    sku: "Enterprise",
    workflow: "Rogue Reconciliation",
    note: "Not exposed as free-form agent tools",
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

  const would = [];
  let would_block = false;
  let primary_action = "ALLOWED";

  if (!policy.enforce) {
    return {
      plane: "Enforce",
      brand: "Vantio Gate",
      mode: "evaluate",
      would_block: false,
      primary_action: "OBSERVED",
      reasons: ["enforce=false — policy is open; traffic would only be observed"],
      policy,
      input: { hostname, request_bytes: requestBytes, spent_usd: spentUsd },
      fence: "This MCP never enforces. Wire dry_run + vantio run / Gate for live enforce.",
    };
  }

  if (policy.blocked_hosts.includes(hostname)) {
    would_block = true;
    primary_action = "DRY_RUN_BLOCKED_HOST";
    would.push({ action: primary_action, reason: "host_not_permitted" });
  } else if (
    policy.allowed_hosts.length > 0 &&
    !policy.allowed_hosts.includes(hostname)
  ) {
    would_block = true;
    primary_action = "DRY_RUN_BLOCKED_HOST";
    would.push({ action: primary_action, reason: "not_in_allowed_hosts" });
  }

  if (policy.max_request_bytes > 0 && requestBytes > policy.max_request_bytes) {
    would_block = true;
    primary_action = "DRY_RUN_BLOCKED_SIZE";
    would.push({
      action: "DRY_RUN_BLOCKED_SIZE",
      reason: `request_bytes ${requestBytes} > max_request_bytes ${policy.max_request_bytes}`,
    });
  }

  if (policy.spend_cap_usd > 0 && spentUsd >= policy.spend_cap_usd) {
    would_block = true;
    primary_action = "DRY_RUN_BLOCKED_SPEND";
    would.push({
      action: "DRY_RUN_BLOCKED_SPEND",
      reason: `spent_usd ${spentUsd} >= spend_cap_usd ${policy.spend_cap_usd}`,
    });
  }

  if (policy.redact_pii) {
    would.push({
      action: "REDACTED",
      reason: `pii_types=${policy.pii_types.join(",")}`,
      note: "Redaction applies at runtime in Gate interceptor; evaluate does not scan bodies here.",
    });
  }

  return {
    plane: "Enforce",
    brand: "Vantio Gate",
    mode: "evaluate",
    would_block,
    primary_action: would_block ? primary_action : "ALLOWED",
    decisions: would.length ? would : [{ action: "ALLOWED", reason: "passes_policy" }],
    policy,
    input: { hostname, request_bytes: requestBytes, spent_usd: spentUsd },
    fence:
      "Dry-run evaluate only. No network call was blocked. Enable Gate with dry_run=true in production to validate, then latch enforce.",
  };
}

export async function fetchCloudConfig({
  apiKey,
  apiBase = process.env.VANTIO_API_BASE || "https://api.vantio.ai",
} = {}) {
  const key = apiKey || process.env.VANTIO_API_KEY;
  if (!key) {
    return {
      ok: false,
      error: "missing_api_key",
      hint: "Set VANTIO_API_KEY or pass api_key. Free Optics needs no key; Gate cloud config requires Pro.",
      policy: DEFAULT_POLICY,
    };
  }
  const base = apiBase.replace(/\/$/, "");
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

export async function fetchResidualRisk({
  apiKey,
  apiBase = process.env.VANTIO_API_BASE || "https://api.vantio.ai",
} = {}) {
  const key = apiKey || process.env.VANTIO_API_KEY;
  if (!key) {
    return {
      ok: false,
      error: "missing_api_key",
      hint: "Residual-risk ledger requires Pro (VANTIO_API_KEY).",
    };
  }
  const base = apiBase.replace(/\/$/, "");
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
