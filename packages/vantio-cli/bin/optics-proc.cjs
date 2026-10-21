"use strict";

// Read-only local process table. Linux /proc only. No writes, no DNS.

const { existsSync, readdirSync, readFileSync, readlinkSync } = require("node:fs");
const { join, basename } = require("node:path");

const INTERPRETERS = new Set(["node", "nodejs", "python", "python3", "bun", "deno"]);
const NAMED_AI = new Set(["ollama", "llama-server"]);
const COMMAND_HINTS = ["agent", "openai", "anthropic", "mcp", "ollama", "langchain", "llm"];

function parseIpv4(hex) {
  const value = Number.parseInt(hex, 16);
  if (!Number.isFinite(value)) return null;
  return [value & 0xff, (value >> 8) & 0xff, (value >> 16) & 0xff, (value >> 24) & 0xff].join(".");
}

function parseIpv6(hex) {
  if (!hex || hex.length !== 32) return null;
  const bytes = [];
  for (let word = 0; word < 4; word += 1) {
    const part = Number.parseInt(hex.slice(word * 8, word * 8 + 8), 16);
    if (!Number.isFinite(part)) return null;
    bytes.push(part & 0xff, (part >> 8) & 0xff, (part >> 16) & 0xff, (part >> 24) & 0xff);
  }
  const groups = [];
  for (let i = 0; i < 16; i += 2) groups.push(((bytes[i] << 8) | bytes[i + 1]).toString(16));
  return groups.join(":");
}

function parseAddress(token, ipv6) {
  const [addr, portHex] = String(token || "").split(":");
  if (!addr || !portHex) return null;
  const ip = ipv6 ? parseIpv6(addr) : parseIpv4(addr);
  const port = Number.parseInt(portHex, 16);
  if (!ip || !Number.isInteger(port)) return null;
  return { ip, port };
}

function parseTcpTable(text, ipv6) {
  const rows = new Map();
  const lines = String(text || "").split("\n").slice(1);
  for (const line of lines) {
    const fields = line.trim().split(/\s+/);
    if (fields.length < 10) continue;
    const remote = parseAddress(fields[2], ipv6);
    const state = fields[3];
    const inode = fields[9];
    if (!remote || !inode || inode === "0") continue;
    rows.set(inode, { ip: remote.ip, port: remote.port, state });
  }
  return rows;
}

function isLoopback(ip) {
  const host = String(ip || "").toLowerCase();
  return host === "127.0.0.1" || host === "::1" || host === "0:0:0:0:0:0:0:1";
}

function parseHosts(text) {
  const byIp = new Map();
  for (const raw of String(text || "").split("\n")) {
    const line = raw.replace(/#.*$/, "").trim();
    if (!line) continue;
    const parts = line.split(/\s+/);
    const ip = parts.shift();
    if (!ip) continue;
    const names = byIp.get(ip) || [];
    for (const name of parts) names.push(name.toLowerCase());
    byIp.set(ip, names);
  }
  return byIp;
}

function commandArgv(cmdline) {
  return String(cmdline || "").split("\0").map((part) => part.trim()).filter(Boolean);
}

function programFromArgv(argv) {
  const args = argv.length ? argv : ["unknown"];
  const interp = basename(args[0] || "unknown");
  for (let i = 1; i < args.length; i += 1) {
    const part = args[i];
    if (!part || part.startsWith("-")) continue;
    return basename(part);
  }
  return interp;
}

function commandLooksLikeAi(argv) {
  const base = basename(argv[0] || "").toLowerCase();
  if (NAMED_AI.has(base)) return true;
  if (!INTERPRETERS.has(base)) return false;
  const rest = argv.slice(1).join(" ").toLowerCase();
  return COMMAND_HINTS.some((hint) => rest.includes(hint));
}

function loadSockets(procRoot) {
  const sockets = new Map();
  for (const [name, ipv6] of [["tcp", false], ["tcp6", true]]) {
    let text = "";
    try {
      text = readFileSync(join(procRoot, "net", name), "utf8");
    } catch {
      continue;
    }
    for (const [inode, row] of parseTcpTable(text, ipv6)) sockets.set(inode, row);
  }
  return sockets;
}

function socketInodes(fdDir) {
  const inodes = [];
  let names = [];
  try {
    names = readdirSync(fdDir);
  } catch {
    return inodes;
  }
  for (const name of names) {
    try {
      const target = readlinkSync(join(fdDir, name));
      const match = /^socket:\[(\d+)\]$/.exec(target);
      if (match) inodes.push(match[1]);
    } catch {
      // A file descriptor can vanish while it is being read.
    }
  }
  return inodes;
}

function coveredMatch(pid, program, covered) {
  return (covered || []).some((row) => {
    if (row == null || String(row.pid) !== String(pid)) return false;
    if (!row.program || !program) return false;
    return program === row.program || program.endsWith(`/${row.program}`);
  });
}

function discoverUncovered(options) {
  const procRoot = options && options.procRoot;
  if (!procRoot || !existsSync(procRoot)) {
    return {
      readable: false,
      reason: "This system has no local process table to read.",
      processes: [],
    };
  }
  let entries;
  try {
    entries = readdirSync(procRoot);
  } catch (err) {
    return {
      readable: false,
      reason: `The process table could not be read: ${err && err.message ? err.message.split("\n")[0] : "failed"}`,
      processes: [],
    };
  }
  let hostsText = "";
  try {
    hostsText = readFileSync(options.hostsPath || "/etc/hosts", "utf8");
  } catch {
    hostsText = "";
  }
  const byIp = parseHosts(hostsText);
  const sockets = loadSockets(procRoot);
  const isAiHost = typeof options.isAiHost === "function" ? options.isAiHost : () => false;
  const processes = [];
  const seen = new Set();
  for (const name of entries) {
    if (!/^\d+$/.test(name)) continue;
    if (options.selfPid != null && String(options.selfPid) === name) continue;
    let cmdline = "";
    try {
      cmdline = readFileSync(join(procRoot, name, "cmdline"), "utf8");
    } catch {
      continue;
    }
    const argv = commandArgv(cmdline);
    if (!argv.length) continue;
    const program = programFromArgv(argv);
    if (coveredMatch(name, program, options.covered)) continue;
    const hint = commandLooksLikeAi(argv);
    for (const inode of socketInodes(join(procRoot, name, "fd"))) {
      const socket = sockets.get(inode);
      if (!socket || socket.state !== "01") continue;
      const loopback = isLoopback(socket.ip);
      if (loopback && socket.port !== 11434) continue;
      const names = byIp.get(socket.ip) || [];
      const aiName = names.find((host) => isAiHost(host, socket.port)) || null;
      const ollamaLocal = loopback && socket.port === 11434;
      if (!aiName && !hint && !ollamaLocal) continue;
      const destination = aiName || (ollamaLocal ? "127.0.0.1" : (names[0] || socket.ip));
      const key = `${name}\n${destination}`;
      if (seen.has(key)) continue;
      seen.add(key);
      processes.push({
        pid: Number(name),
        program,
        destination,
        port: socket.port,
        reason: aiName || ollamaLocal ? "in_scope_socket" : "command_hint",
        covered: false,
        source: "proc",
      });
    }
  }
  return { readable: true, reason: null, processes };
}

function parseStat(text) {
  const close = String(text || "").lastIndexOf(")");
  if (close < 0) return null;
  const open = String(text).indexOf("(");
  if (open < 0 || open > close) return null;
  const rest = String(text).slice(close + 1).trim().split(/\s+/);
  const ppid = Number(rest[1]);
  if (!Number.isInteger(ppid)) return null;
  return { comm: String(text).slice(open + 1, close), ppid };
}

function readProcList(procRoot) {
  const out = [];
  let names = [];
  try {
    names = readdirSync(procRoot);
  } catch {
    return out;
  }
  for (const name of names) {
    if (!/^\d+$/.test(name)) continue;
    let stat = "";
    try {
      stat = readFileSync(join(procRoot, name, "stat"), "utf8");
    } catch {
      continue;
    }
    const parsed = parseStat(stat);
    if (!parsed) continue;
    let cmdline = "";
    try {
      cmdline = readFileSync(join(procRoot, name, "cmdline"), "utf8");
    } catch {
      cmdline = "";
    }
    const argv = commandArgv(cmdline);
    out.push({
      pid: Number(name),
      ppid: parsed.ppid,
      program: argv.length ? basename(argv[0]) : (parsed.comm || name),
      comm: parsed.comm,
    });
  }
  return out;
}

function wrappedTree(procs, rootPid) {
  const byPid = new Map(procs.map((proc) => [proc.pid, proc]));
  const children = new Map();
  for (const proc of procs) {
    const list = children.get(proc.ppid) || [];
    list.push(proc);
    children.set(proc.ppid, list);
  }
  const out = [];
  const seen = new Set();
  const stack = [rootPid];
  while (stack.length) {
    const pid = stack.pop();
    if (seen.has(pid)) continue;
    seen.add(pid);
    const proc = byPid.get(pid);
    if (proc) out.push(proc);
    for (const child of children.get(pid) || []) stack.push(child.pid);
  }
  return out;
}

function sampleWrappedTree(procRoot, rootPid, hostsText) {
  const procs = wrappedTree(readProcList(procRoot), rootPid);
  const byIp = parseHosts(hostsText || "");
  const sockets = loadSockets(procRoot);
  const connections = [];
  const seen = new Set();
  for (const proc of procs) {
    for (const inode of socketInodes(join(procRoot, String(proc.pid), "fd"))) {
      const socket = sockets.get(inode);
      if (!socket || socket.port === 0 || isLoopback(socket.ip) || socket.ip === "0.0.0.0" || socket.ip === "::") continue;
      const names = byIp.get(socket.ip) || [];
      const destination = names[0] || socket.ip;
      const key = `${proc.pid}\n${destination}\n${socket.port}`;
      if (seen.has(key)) continue;
      seen.add(key);
      connections.push({
        pid: proc.pid,
        ppid: proc.ppid,
        program: proc.program,
        destination,
        port: socket.port,
      });
    }
  }
  return { processes: procs, connections };
}

function createWrapSampler(options) {
  const procRoot = options.procRoot;
  const rootPid = options.rootPid;
  const hostsPath = options.hostsPath || "/etc/hosts";
  const intervalMs = options.intervalMs == null ? 20 : options.intervalMs;
  const onConnection = typeof options.onConnection === "function" ? options.onConnection : null;
  const processes = new Map();
  const connections = new Map();
  let timer = null;
  function sample() {
    if (!procRoot || !rootPid || !existsSync(procRoot)) return;
    let hostsText = "";
    try {
      hostsText = readFileSync(hostsPath, "utf8");
    } catch {
      hostsText = "";
    }
    const snap = sampleWrappedTree(procRoot, rootPid, hostsText);
    for (const proc of snap.processes) processes.set(proc.pid, proc);
    for (const conn of snap.connections) {
      const key = `${conn.pid}\n${conn.destination}\n${conn.port}`;
      if (connections.has(key)) continue;
      connections.set(key, conn);
      if (!onConnection) continue;
      try {
        onConnection(conn);
      } catch {
        // A live-note failure must not stop sampling. The run file still keeps the socket.
      }
    }
  }
  sample();
  if (intervalMs > 0) {
    timer = setInterval(sample, intervalMs);
    if (timer.unref) timer.unref();
  }
  return {
    stop() {
      if (timer) clearInterval(timer);
      timer = null;
      sample();
      return {
        processes: [...processes.values()],
        connections: [...connections.values()],
      };
    },
  };
}

module.exports = {
  commandLooksLikeAi,
  createWrapSampler,
  discoverUncovered,
  parseHosts,
  parseIpv4,
  parseStat,
  parseTcpTable,
  sampleWrappedTree,
};
