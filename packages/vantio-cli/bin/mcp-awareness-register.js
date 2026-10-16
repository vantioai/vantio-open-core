/**
 * In-process MCP awareness for `vantio run`.
 *
 * This module is not Phantom Engine and it does not open a socket, listen,
 * or spawn a proxy. Observe copies bytes the process already holds and
 * forwards them. Enforce is opt-in and withholds inside this process.
 * Records keep the library's closed fields. Payload text is not a field.
 */

import { createRequire } from "node:module";
import { libraryHref, resolveLibrary } from "./mcp-awareness-paths.js";
import { appendFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const require = createRequire(import.meta.url);
const MAX_FRAME = 256 * 1024;
const MAX_LOG = 1024 * 1024;
const MAX_POLICY = 64 * 1024;
const ID_RE = /^[A-Za-z0-9_.:-]{1,64}$/;
const REASON_RE = /^[a-z0-9_]{1,64}$/;

const enabled = process.env.VANTIO_MCP_AWARENESS === "on" || process.env.VANTIO_MCP_AWARENESS === "1";

if (enabled && !globalThis.__vantioMcpAwareness) {
  globalThis.__vantioMcpAwareness = true;
  await boot();
}

async function boot() {
  try {
    const target = resolveLibrary();
    if (!existsSync(target)) return;
    const loaded = await import(libraryHref());
    if (!loaded || typeof loaded.createRuntime !== "function") return;
    install(loaded.createRuntime());
  } catch {
    // A missing library or a bad policy must not stop the workload.
  }
}

function install(runtime) {
  const policy = loadPolicy();
  const writeLog = openLog();
  process.stderr.write(
    `[ ∅ VANTIO ] mcp awareness mode=${policy.mode} injection=${policy.injection} rug_pull=${policy.rug_pull}\n`,
  );
  patchFetch(runtime, policy, writeLog);
  patchSpawn(runtime, policy, writeLog);
}

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
  return {
    schema: "vantio.mcp_policy.v1",
    mode,
    injection,
    rug_pull: rugPull,
    servers,
  };
}

function openLog() {
  const root = process.env.VANTIO_HOME || join(homedir(), ".vantio");
  const file = join(root, "mcp-observations.jsonl");
  return function writeLog(record) {
    try {
      if (!record || record.schema !== "vantio.mcp_observation.v1") return;
      const reason = record.decision && record.decision.reason;
      if (reason === "ignored_non_json" || reason === "empty") return;
      const line = `${JSON.stringify(record)}\n`;
      mkdirSync(root, { recursive: true });
      const size = existsSync(file) ? statSync(file).size : 0;
      if (size >= MAX_LOG) return;
      appendFileSync(file, line);
    } catch {
      // The log is not an availability dependency.
    }
  };
}

function patchFetch(runtime, policy, writeLog) {
  if (typeof globalThis.fetch !== "function" || globalThis.fetch.__vantioMcpFetch) return;
  const orig = globalThis.fetch;
  function vantioMcpFetch(input, init) {
    const body = bufferedBody(init);
    const mcp = body ? looksLikeJsonRpc(body) : false;
    if (policy.mode === "enforce" && mcp) {
      const judged = judgeRequest(runtime, policy, writeLog, input, body);
      if (judged.blocked) return Promise.resolve(blockedResponse(judged));
    } else if (mcp) {
      judgeRequest(runtime, policy, writeLog, input, body);
    }
    const pending = orig.apply(this, arguments);
    if (mcp && pending && typeof pending.then === "function") {
      pending.then((response) => observeResponse(runtime, policy, writeLog, input, response), () => {});
    }
    return pending;
  }
  vantioMcpFetch.__vantioMcpFetch = true;
  globalThis.fetch = vantioMcpFetch;
}

function judgeRequest(runtime, policy, writeLog, input, body) {
  try {
    const out = runtime.inspectExchange({
      policy,
      serverId: serverIdFromInput(input),
      requestBody: body,
      requestType: "application/json",
    });
    const records = out && Array.isArray(out.records) ? out.records : [];
    for (const record of records) writeLog(record);
    const blocked = policy.mode === "enforce" && records.some((record) => {
      const action = record && record.decision && record.decision.action;
      return action === "BLOCK" || action === "GAP";
    });
    return { blocked, records };
  } catch {
    return { blocked: policy.mode === "enforce", records: [] };
  }
}

function observeResponse(runtime, policy, writeLog, input, response) {
  try {
    if (!response || typeof response.clone !== "function" || !response.headers || typeof response.headers.get !== "function") return;
    const type = String(response.headers.get("content-type") || "");
    if (!type.includes("application/json") && !type.includes("text/event-stream")) return;
    const clone = response.clone();
    if (!clone || typeof clone.arrayBuffer !== "function") return;
    clone.arrayBuffer().then((bytes) => {
      const buf = Buffer.from(bytes);
      if (buf.length > MAX_FRAME) {
        writeLog(gapRecord(serverIdFromInput(input), "oversize", "server_to_client", "http"));
        return;
      }
      const out = runtime.inspectExchange({
        policy,
        serverId: serverIdFromInput(input),
        responseBody: buf,
        responseType: type.includes("text/event-stream") ? "text/event-stream" : "application/json",
      });
      const records = out && Array.isArray(out.records) ? out.records : [];
      for (const record of records) writeLog(record);
    }, () => {});
  } catch {
    // Response logging stays off the caller path.
  }
}

function patchSpawn(runtime, policy, writeLog) {
  const cp = require("node:child_process");
  if (!cp || typeof cp.spawn !== "function" || cp.spawn.__vantioMcpPatched) return;
  const orig = cp.spawn;
  function vantioMcpSpawn(command) {
    const child = orig.apply(this, arguments);
    try {
      attachChild(runtime, policy, writeLog, child, command);
    } catch {
      // Spawn itself already succeeded. Awareness must not throw after that.
    }
    return child;
  }
  vantioMcpSpawn.__vantioMcpPatched = true;
  cp.spawn = vantioMcpSpawn;
}

function attachChild(runtime, policy, writeLog, child, command) {
  if (!child) return;
  const serverId = serverIdFromCommand(command);
  const meta = { transport: "stdio", serverId, policy, pending: Buffer.alloc(0) };
  if (policy.mode === "enforce" && canWrite(child.stdin)) {
    if (canRead(child.stdout) && installPairGate(runtime, writeLog, child, meta)) return;
    if (canRead(child.stdout)) writeLog(gapRecord(serverId, "gate_unavailable", "client_to_server", "stdio"));
    attachEnforceLines(runtime, writeLog, child, meta);
    return;
  }
  attachObserve(runtime, writeLog, child, meta);
}

function installPairGate(runtime, writeLog, child, meta) {
  const realStdin = child.stdin;
  const realStdout = child.stdout;
  const gate = runtime.createStdioPairGate({
    fromChild: realStdout,
    toChild: realStdin,
    serverId: meta.serverId,
    policy: meta.policy,
    onRecord: writeLog,
  });
  if (!gate || !gate.ok || !gate.stdin || !gate.stdout) return false;
  gate.stdin.on("finish", () => {
    try {
      realStdin.end();
    } catch {
      // The child pipe is already closed.
    }
  });
  child.stdin = gate.stdin;
  child.stdout = gate.stdout;
  if (Array.isArray(child.stdio)) {
    child.stdio[0] = gate.stdin;
    child.stdio[1] = gate.stdout;
  }
  return true;
}

function attachEnforceLines(runtime, writeLog, child, meta) {
  const stdin = child.stdin;
  const origWrite = stdin.write.bind(stdin);
  const origEnd = stdin.end.bind(stdin);
  function take(extra, final) {
    if (extra && extra.length) {
      if (meta.pending.length + extra.length > MAX_FRAME) {
        meta.pending = Buffer.alloc(0);
        writeLog(gapRecord(meta.serverId, "oversize", "client_to_server", "stdio"));
        if (final) return;
        extra = Buffer.alloc(0);
      } else {
        meta.pending = Buffer.concat([meta.pending, extra]);
      }
    }
    let newline = meta.pending.indexOf(0x0a);
    while (newline >= 0) {
      const line = meta.pending.subarray(0, newline + 1);
      meta.pending = Buffer.from(meta.pending.subarray(newline + 1));
      decideLine(runtime, writeLog, child, meta, line, origWrite);
      newline = meta.pending.indexOf(0x0a);
    }
    if (final && meta.pending.length) {
      const tail = meta.pending;
      meta.pending = Buffer.alloc(0);
      decideLine(runtime, writeLog, child, meta, tail, origWrite);
    }
  }
  stdin.write = function vantioMcpEnforceWrite(chunk, encoding, cb) {
    try {
      take(asBuffer(chunk, encoding), false);
    } catch {
      // Enforce must not throw into the workload.
    }
    const done = typeof encoding === "function" ? encoding : cb;
    if (typeof done === "function") done();
    return true;
  };
  stdin.end = function vantioMcpEnforceEnd(chunk, encoding, cb) {
    try {
      if (chunk != null && typeof chunk !== "function") take(asBuffer(chunk, encoding), true);
      else take(Buffer.alloc(0), true);
    } catch {
      // Same rule as write.
    }
    const ended = origEnd();
    const done = typeof cb === "function" ? cb : typeof encoding === "function" ? encoding : typeof chunk === "function" ? chunk : null;
    if (done) done();
    return ended;
  };
}

function decideLine(runtime, writeLog, child, meta, line, origWrite) {
  let records = [];
  try {
    const out = runtime.observeBuffer(line, {
      transport: "stdio",
      direction: "client_to_server",
      serverId: meta.serverId,
      policy: meta.policy,
    });
    records = out && Array.isArray(out.records) ? out.records : [];
  } catch {
    records = [gapRecord(meta.serverId, "malformed_frame", "client_to_server", "stdio")];
  }
  for (const record of records) writeLog(record);
  const blocked = records.some((record) => {
    const action = record && record.decision && record.decision.action;
    return action === "BLOCK" || action === "GAP";
  });
  if (!blocked) {
    try {
      origWrite(line);
    } catch {
      // The child pipe is already closed.
    }
    return;
  }
  if (child.stdout && typeof child.stdout.write === "function") {
    try {
      child.stdout.write(policyError(records));
    } catch {
      // A missing return path does not turn the withhold into a forward.
    }
  }
}

function policyError(records) {
  let id = null;
  let finding = "policy";
  for (const record of records) {
    if (record && record.id_type === "number" && Number.isSafeInteger(record.id_number)) id = record.id_number;
    const reason = record && record.decision && record.decision.reason;
    if (typeof reason === "string" && REASON_RE.test(reason)) finding = reason;
  }
  const idJson = id === null ? "null" : String(id);
  return `{"jsonrpc":"2.0","id":${idJson},"error":{"code":-32001,"message":"vantio_mcp_policy_block","data":{"finding":${JSON.stringify(finding)}}}}\n`;
}

function canWrite(stream) {
  return Boolean(stream && typeof stream.write === "function" && typeof stream.end === "function");
}

function canRead(stream) {
  return Boolean(stream && typeof stream.on === "function");
}

function attachObserve(runtime, writeLog, child, meta) {
  if (piped(child.stdin)) wrapWrite(child.stdin, (buf) => observeChunks(runtime, writeLog, meta, buf));
  if (piped(child.stdout)) armTap(runtime, writeLog, child.stdout, meta);
}

function observeChunks(runtime, writeLog, meta, buf) {
  const state = meta;
  if (!state.pending) state.pending = Buffer.alloc(0);
  if (state.pending.length + buf.length > MAX_FRAME) {
    state.pending = Buffer.alloc(0);
    writeLog(gapRecord(meta.serverId, "oversize", "client_to_server", "stdio"));
    return;
  }
  state.pending = Buffer.concat([state.pending, buf]);
  let newline = state.pending.indexOf(0x0a);
  while (newline >= 0) {
    const line = state.pending.subarray(0, newline + 1);
    state.pending = state.pending.subarray(newline + 1);
    const out = runtime.observeBuffer(line, {
      transport: "stdio",
      direction: "client_to_server",
      serverId: meta.serverId,
      policy: meta.policy,
    });
    const records = out && Array.isArray(out.records) ? out.records : [];
    for (const record of records) writeLog(record);
    newline = state.pending.indexOf(0x0a);
  }
}

function wrapWrite(stdin, onBytes) {
  const origWrite = stdin.write.bind(stdin);
  const origEnd = stdin.end.bind(stdin);
  stdin.write = function vantioMcpWrite(chunk, encoding, cb) {
    try {
      onBytes(asBuffer(chunk, encoding));
    } catch {
      // Observe must not throw into the workload.
    }
    return origWrite(chunk, encoding, cb);
  };
  stdin.end = function vantioMcpEnd(chunk, encoding, cb) {
    if (chunk != null && typeof chunk !== "function") {
      try {
        onBytes(asBuffer(chunk, encoding));
      } catch {
        // Same rule as write.
      }
    }
    return origEnd(chunk, encoding, cb);
  };
}

function armTap(runtime, writeLog, stdout, meta) {
  if (stdout.__vantioMcpTapArmed) return;
  stdout.__vantioMcpTapArmed = true;
  let tapping = false;
  const origOn = stdout.on.bind(stdout);
  stdout.on = function vantioMcpOn(event, listener) {
    const returned = origOn(event, listener);
    if (event === "data" && !tapping) {
      tapping = true;
      try {
        const tap = runtime.tapReadable(stdout, {
          transport: "stdio",
          direction: "server_to_client",
          serverId: meta.serverId,
          policy: meta.policy,
          onRecord: writeLog,
        });
        if (tap && tap.ok) stdout.__vantioMcpTapped = true;
      } catch {
        // A tap that cannot attach leaves the existing listener in place.
      } finally {
        tapping = false;
      }
    }
    return returned;
  };
}

function piped(stream) {
  return Boolean(stream && typeof stream.write === "function" && typeof stream.on === "function");
}

function asBuffer(chunk, encoding) {
  if (Buffer.isBuffer(chunk)) return chunk;
  if (chunk instanceof Uint8Array) return Buffer.from(chunk);
  const enc = typeof encoding === "string" ? encoding : "utf8";
  return Buffer.from(chunk, enc);
}

function bufferedBody(init) {
  if (!init || typeof init !== "object" || !Object.prototype.hasOwnProperty.call(init, "body")) return null;
  const body = init.body;
  if (typeof body === "string") return Buffer.from(body);
  if (Buffer.isBuffer(body)) return body;
  if (body instanceof Uint8Array) return Buffer.from(body);
  return null;
}

function looksLikeJsonRpc(buf) {
  if (!Buffer.isBuffer(buf) || buf.length === 0 || buf.length > MAX_FRAME) return false;
  const head = buf.subarray(0, Math.min(buf.length, 256)).toString("utf8").trimStart();
  if (!head.startsWith("{")) return false;
  return /"jsonrpc"\s*:/.test(head);
}

function serverIdFromInput(input) {
  try {
    const href = typeof input === "string" ? input : input instanceof URL ? input.href : input && input.url;
    return safeId(new URL(href).hostname, "http");
  } catch {
    return "http";
  }
}

function serverIdFromCommand(command) {
  const base = String(command || "").split(/[\\/]/).pop().replace(/\.exe$/i, "");
  return safeId(base, "child");
}

function safeId(value, fallback) {
  return ID_RE.test(value) ? value : fallback;
}

function gapRecord(serverId, reason, direction, transport) {
  return {
    schema: "vantio.mcp_observation.v1",
    at: new Date().toISOString(),
    transport,
    direction,
    server_id: serverId,
    findings: [{ kind: reason }],
    decision: { action: "GAP", reason },
    retention: { payload: false, values: false },
  };
}

function blockedResponse(judged) {
  const id = numericId(judged);
  const finding = findingToken(judged.records);
  const payload = JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code: -32001, message: "vantio_mcp_policy_block", data: { finding } },
  });
  return new Response(payload, { status: 200, headers: { "content-type": "application/json" } });
}

function numericId(judged) {
  const records = judged && Array.isArray(judged.records) ? judged.records : [];
  for (const record of records) {
    if (record && record.id_type === "number" && Number.isSafeInteger(record.id_number)) return record.id_number;
  }
  return null;
}

function findingToken(records) {
  for (const record of records || []) {
    const reason = record && record.decision && record.decision.reason;
    if (typeof reason === "string" && REASON_RE.test(reason)) return reason;
  }
  return "policy";
}
