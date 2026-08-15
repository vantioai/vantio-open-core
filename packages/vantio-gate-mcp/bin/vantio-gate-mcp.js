#!/usr/bin/env node
/**
 * stdio entry for Vantio Gate MCP (dry-run / evaluate).
 * stdout is reserved for MCP framing — log only to stderr.
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createGateMcpServer } from "../src/server.js";

async function main() {
  const server = createGateMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(
    "[vantio-gate-mcp] Vantio Gate MCP listening on stdio (dry-run evaluate only)",
  );
}

main().catch((err) => {
  console.error("[vantio-gate-mcp] fatal:", err);
  process.exit(1);
});
