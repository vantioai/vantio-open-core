#!/usr/bin/env node
/**
 * stdio entry for the @vantio/gate-mcp compatibility layer (Phantom Engine dry-run / evaluate).
 * stdout is reserved for MCP framing — log only to stderr.
 * Gate is not a separate Vantio product or subscription; this is a legacy package name.
 */
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createGateMcpServer } from "../src/server.js";

async function main() {
  const server = createGateMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(
    "[vantio-gate-mcp] Phantom Engine compatibility — application-path enforce dry-run. " +
    "(@vantio/gate-mcp is a legacy package name; Gate is not a separate Vantio product.)",
  );
}

main().catch((err) => {
  console.error("[vantio-gate-mcp] fatal:", err);
  process.exit(1);
});
