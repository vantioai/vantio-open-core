/**
 * One-shot evaluation of a single MCP frame.
 * Python `vantio run` hands a copy here. This process does not own the child pipe.
 */

import { readFileSync, statSync } from "node:fs";
import { libraryHref } from "./mcp-awareness-paths.js";

const MAX_POLICY = 64 * 1024;

function loadPolicy() {
  const mode = process.env.VANTIO_MCP_MODE === "enforce" ? "enforce" : "observe";
  const injection = process.env.VANTIO_MCP_INJECTION === "block" ? "block" : "log";
  const rugPull = process.env.VANTIO_MCP_RUG_PULL === "block" ? "block" : "log";
  let servers = {};
  const file = process.env.VANTIO_MCP_POLICY;
  if (file) {
    try {
      const info = statSync(file);
      if (info.isFile() && info.size <= MAX_POLICY) {
        const parsed = JSON.parse(readFileSync(file, "utf8"));
        if (parsed && typeof parsed === "object" && parsed.servers && typeof parsed.servers === "object") {
          servers = parsed.servers;
        }
      }
    } catch {
      servers = {};
    }
  }
  return { schema: "vantio.mcp_policy.v1", mode, injection, rug_pull: rugPull, servers };
}

function isBlocked(records, mode) {
  if (mode !== "enforce") return false;
  return records.some((record) => {
    const action = record && record.decision && record.decision.action;
    return action === "BLOCK" || action === "GAP";
  });
}

function policyError(records) {
  let id = null;
  let finding = "policy";
  for (const record of records) {
    if (record && record.id_type === "number" && Number.isSafeInteger(record.id_number)) id = record.id_number;
    const reason = record && record.decision && record.decision.reason;
    if (typeof reason === "string" && /^[a-z0-9_]{1,64}$/.test(reason)) finding = reason;
  }
  const idJson = id === null ? "null" : String(id);
  return `{"jsonrpc":"2.0","id":${idJson},"error":{"code":-32001,"message":"vantio_mcp_policy_block","data":{"finding":${JSON.stringify(finding)}}}}\n`;
}

const chunks = [];
for await (const chunk of process.stdin) chunks.push(chunk);
const frame = Buffer.concat(chunks);
const policy = loadPolicy();
let records = [];
try {
  const loaded = await import(libraryHref());
  const runtime = loaded.createRuntime();
  const out = runtime.observeBuffer(frame, {
    transport: "stdio",
    direction: "client_to_server",
    serverId: process.argv[2] && /^[A-Za-z0-9_.:-]{1,64}$/.test(process.argv[2]) ? process.argv[2] : "child",
    policy,
  });
  records = out && Array.isArray(out.records) ? out.records : [];
} catch {
  records = [];
}
const withhold = isBlocked(records, policy.mode) || (policy.mode === "enforce" && records.length === 0);
process.stdout.write(JSON.stringify({ records, error: withhold ? policyError(records) : null }));
