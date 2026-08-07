#!/usr/bin/env node
/**
 * stdio entry for Vantio Optics MCP (read-only Observe / Sight Loop).
 * stdout is reserved for MCP framing — log only to stderr.
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createOpticsMcpServer } from "../src/server.js";

async function main() {
  const server = createOpticsMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[vantio-optics-mcp] Vantio Optics MCP listening on stdio (observe only)");
}

main().catch((err) => {
  console.error("[vantio-optics-mcp] fatal:", err);
  process.exit(1);
});
