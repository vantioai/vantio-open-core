/**
 * Vantio Optics MCP — observe / explain only.
 * No Gate enforcement tools. Upgrade path is explicit in tool copy + optics_upgrade_path.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  listRunLogs,
  loadRun,
  proveMarkdown,
  discoverLocal,
  UPGRADE_PATH,
  runsDir,
} from "./runs.js";

function text(data) {
  const body = typeof data === "string" ? data : JSON.stringify(data, null, 2);
  return { content: [{ type: "text", text: body }] };
}

function err(message) {
  return { content: [{ type: "text", text: message }], isError: true };
}

export function createOpticsMcpServer() {
  const server = new McpServer({
    name: "vantio-optics",
    version: "0.1.0",
  });

  server.tool(
    "optics_list_runs",
    "List local Vantio Optics run logs from ~/.vantio/runs (written by `vantio run`). Read-only observe. No prompts/completions.",
    {
      limit: z.number().int().min(1).max(100).optional().describe("Max runs to return (default 20)"),
    },
    async ({ limit }) => {
      const n = limit ?? 20;
      const runs = listRunLogs().slice(0, n).map(({ path, mtime_ms, ...rest }) => rest);
      return text({
        plane: "Observe",
        brand: "Vantio Optics",
        runs_dir: runsDir(),
        count: runs.length,
        runs,
        note: runs.length
          ? "Use optics_get_run or optics_prove with a trace_id."
          : "No runs yet. Instrument an agent: vantio run <command>",
        upgrade: "Enforcement is Vantio Gate — see optics_upgrade_path.",
      });
    },
  );

  server.tool(
    "optics_get_run",
    "Load one Optics run log by trace_id (or 'latest'). Returns traffic metadata only — never prompts or completions. Read-only.",
    {
      trace_id: z
        .string()
        .optional()
        .describe("Trace ID or prefix; omit or 'latest' for most recent run"),
    },
    async ({ trace_id }) => {
      const result = loadRun(trace_id || "latest");
      if (result.error) return err(JSON.stringify(result, null, 2));
      const log = result.log;
      // Strip any accidental content fields if present in future logs
      const safe = {
        vantio_run_log: log.vantio_run_log,
        trace_id: log.trace_id,
        pid: log.pid,
        machine: log.machine,
        started_at: log.started_at,
        generated_at: log.generated_at,
        duration_ms: log.duration_ms,
        cli_version: log.cli_version,
        summary: log.summary,
        calls: (log.calls || []).map((c) => ({
          hostname: c.hostname,
          action: c.action,
          bytes: c.bytes,
          ts: c.ts,
          redactions: c.redactions,
        })),
      };
      return text({
        plane: "Observe",
        brand: "Vantio Optics",
        path: result.path,
        run: safe,
        fence: UPGRADE_PATH.fence,
      });
    },
  );

  server.tool(
    "optics_prove",
    "Generate a Markdown Sight Loop proof artifact for a local Optics run (auditor-ready; no prompts). Read-only export.",
    {
      trace_id: z
        .string()
        .optional()
        .describe("Trace ID or prefix; omit or 'latest' for most recent"),
    },
    async ({ trace_id }) => {
      const result = loadRun(trace_id || "latest");
      if (result.error) return err(JSON.stringify(result, null, 2));
      return text(proveMarkdown(result.log));
    },
  );

  server.tool(
    "optics_discover_local",
    "Aggregate LLM/agent hostnames from local Optics run logs (Free-tier discover). Read-only; no policy changes.",
    {
      since_days: z
        .number()
        .int()
        .min(1)
        .max(90)
        .optional()
        .describe("Lookback window in days (default 7)"),
    },
    async ({ since_days }) => {
      const days = since_days ?? 7;
      const hosts = discoverLocal(days * 24 * 60 * 60 * 1000);
      return text({
        plane: "Observe",
        brand: "Vantio Optics",
        since_days: days,
        host_count: hosts.length,
        hosts,
        note: "Fleet-wide Shadow AI Discover with enforce status requires Vantio Gate (Pro).",
        upgrade: UPGRADE_PATH.next[0],
      });
    },
  );

  server.tool(
    "optics_explain",
    "Explain Vantio Optics (Observe / Sight Loop), privacy boundary, and what this MCP will never do. Optionally attach a short summary of the latest run.",
    {
      include_latest_run: z
        .boolean()
        .optional()
        .describe("If true, include a one-line summary of the latest local run"),
    },
    async ({ include_latest_run }) => {
      const latest = include_latest_run ? listRunLogs()[0] : null;
      return text({
        brand: "Vantio Optics",
        company: "Vantio AI, Inc.",
        plane: "Observe",
        workflow: "Sight Loop",
        does: [
          "Intercept LLM/agent egress metadata (host, process, bytes, time, trace)",
          "Write local run logs for prove/discover",
          "Export auditor-ready proofs with zero prompts/completions",
        ],
        does_not: [
          "Capture prompts or completions (blind by design)",
          "Block, redact, or cap spend (that is Vantio Gate)",
          "Provide Absolute Control / Rogue Reconciliation (that is Phantom Engine)",
        ],
        fence: UPGRADE_PATH.fence,
        latest_run: latest
          ? {
              trace_id: latest.trace_id,
              total_calls: latest.total_calls,
              hosts: latest.hosts,
              started_at: latest.started_at,
            }
          : null,
        docs: {
          optics: "https://vantio.ai/optics",
          pricing: "https://vantio.ai/pricing",
        },
      });
    },
  );

  server.tool(
    "optics_upgrade_path",
    "Return the Vantio upgrade ladder from Optics (this MCP) → Gate (enforce) → Phantom Engine (Absolute Control). Use when the user needs policy or bypass proof.",
    {},
    async () => text(UPGRADE_PATH),
  );

  return server;
}
