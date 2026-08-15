/**
 * Vantio Gate MCP — rules-that-stick dry-run / evaluate only.
 * Does not block traffic, mutate production policy, or expose Phantom Engine.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  DEFAULT_POLICY,
  UPGRADE_PATH,
  normalizePolicy,
  evaluateRequest,
  fetchCloudConfig,
  fetchResidualRisk,
} from "./policy.js";

function text(data) {
  const body = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return { content: [{ type: "text", text: body }] };
}

function err(message) {
  return { content: [{ type: "text", text: message }], isError: true };
}

const policyShape = z
  .object({
    enforce: z.boolean().optional(),
    redact_pii: z.boolean().optional(),
    pii_types: z.array(z.string()).optional(),
    allowed_hosts: z.array(z.string()).optional(),
    blocked_hosts: z.array(z.string()).optional(),
    max_request_bytes: z.number().optional(),
    spend_cap_usd: z.number().optional(),
    dry_run: z.boolean().optional(),
  })
  .optional();

export function createGateMcpServer() {
  const server = new McpServer({
    name: "vantio-gate",
    version: "0.1.0",
  });

  server.tool(
    "gate_evaluate",
    "Dry-run evaluate a hostname/bytes/spend against a Gate policy. Never blocks network I/O. Pass policy JSON or omit to use defaults / last fetched shape.",
    {
      hostname: z.string().describe("Destination hostname, e.g. api.openai.com"),
      request_bytes: z.number().optional().describe("Request body size in bytes"),
      spent_usd: z.number().optional().describe("Session spend so far in USD"),
      policy: policyShape.describe("Policy object to evaluate against"),
    },
    async ({ hostname, request_bytes, spent_usd, policy }) => {
      return text(
        evaluateRequest(policy || DEFAULT_POLICY, {
          hostname,
          request_bytes,
          spent_usd,
        }),
      );
    },
  );

  server.tool(
    "gate_get_policy",
    "Fetch current tenant policy from the Vantio Gate control plane (Pro). Requires VANTIO_API_KEY. Read-only.",
    {
      api_key: z.string().optional().describe("Override VANTIO_API_KEY"),
      api_base: z.string().optional().describe("Override VANTIO_API_BASE"),
    },
    async ({ api_key, api_base }) => {
      const result = await fetchCloudConfig({
        apiKey: api_key,
        apiBase: api_base,
      });
      if (!result.ok) return err(JSON.stringify(result, null, 2));
      return text({
        plane: "Enforce",
        brand: "Vantio Gate",
        tier: result.tier,
        policy: result.policy,
        note: "Use gate_evaluate to dry-run decisions. Live latch is via vantio run + Pro — not this MCP.",
      });
    },
  );

  server.tool(
    "gate_residual_risk",
    "Fetch residual-risk / dry-run / enforcement-gap ledger from Pro. Requires VANTIO_API_KEY. Read-only.",
    {
      api_key: z.string().optional(),
      api_base: z.string().optional(),
    },
    async ({ api_key, api_base }) => {
      const result = await fetchResidualRisk({
        apiKey: api_key,
        apiBase: api_base,
      });
      if (!result.ok) return err(JSON.stringify(result, null, 2));
      return text({
        plane: "Enforce",
        brand: "Vantio Gate",
        ...result,
        upgrade: "Paths that never reach the app wrap need Vantio Phantom Engine on Linux hosts you enroll.",
      });
    },
  );

  server.tool(
    "gate_normalize_policy",
    "Normalize and validate a policy object to Gate's canonical schema (coerce bad fields to safe defaults).",
    {
      policy: z.record(z.unknown()).describe("Raw policy JSON"),
    },
    async ({ policy }) => {
      return text({
        plane: "Enforce",
        brand: "Vantio Gate",
        policy: normalizePolicy(policy),
      });
    },
  );

  server.tool(
    "gate_explain",
    "Explain Vantio Gate (rules that stick), dry-run fence, and what this MCP will never do.",
    {},
    async () =>
      text({
        brand: "Vantio Gate",
        workflow: "Rules that stick",
        sku: "Pro (includes Optics)",
        does: [
          "Evaluate host allow/block, size caps, spend caps, PII redact flags",
          "Dry-run decisions without blocking (this MCP)",
          "Live enforce when wired through vantio run + Gate policy",
        ],
        does_not: [
          "Block or redact traffic from inside this MCP",
          "Push unconstrained policy changes to production",
          "Provide Phantom Engine host protection / Rogue Reconciliation",
          "Capture prompts or completions",
        ],
        enable_live:
          "Set policy.dry_run=true on Gate, run agents under vantio run, review DRY_RUN_* events, then set enforce=true.",
        pricing: "https://vantio.ai/pricing",
        gate: "https://vantio.ai/gate",
      }),
  );

  server.tool(
    "gate_upgrade_path",
    "Return Optics → Gate → Phantom Engine ladder. Use when residual bypass must close.",
    {},
    async () =>
      text({
        ladder: UPGRADE_PATH,
        pricing: "https://vantio.ai/pricing",
      }),
  );

  return server;
}
