/**
 * Locate the in-process MCP library.
 * The packed CLI carries a copy under bin/mcp-awareness.
 * A source checkout can still see the package next to the CLI.
 */

import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

export function resolveLibrary() {
  const override = process.env.VANTIO_MCP_LIB;
  if (override) return override;
  const here = dirname(fileURLToPath(import.meta.url));
  const packed = resolve(here, "mcp-awareness/index.js");
  if (existsSync(packed)) return packed;
  return resolve(here, "../../vantio-mcp-awareness/src/index.js");
}

export function libraryHref() {
  return pathToFileURL(resolveLibrary()).href;
}
