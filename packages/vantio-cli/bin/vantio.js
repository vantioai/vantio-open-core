#!/usr/bin/env node
import { spawn }         from "node:child_process";
import { parseArgs }     from "node:util";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { homedir }       from "node:os";
import { mkdirSync, readFileSync, writeFileSync, rmSync, chmodSync } from "node:fs";
import readline          from "node:readline";

const DEFAULT_BASE = "https://vantio.ai";

const USAGE = `\
Vantio AI — process supervisor

Usage:
  vantio login [key]          Save & validate your API key (no env vars after this)
  vantio logout               Remove the stored key
  vantio whoami               Show the stored key (masked) + connection status
  vantio run [flags] <prog>   Spawn <prog> under the Vantio execution context
  vantio discover [options]   Show Shadow AI attack surface (AI calls in your workspace)

Flags (run):
  --audit,   -a   Enable audit mode (VANTIO_AUDIT_MODE=1).
  --summary, -s   Print a run summary on exit.

After 'vantio login', plain 'vantio run node agent.js' just works — the key is
loaded from ~/.vantio/config.json and injected into the child process. An
explicit VANTIO_API_KEY in your environment always takes precedence.

Examples:
  vantio login vk_live_xxx
  vantio run node agent.js
  vantio run --audit tsx agent.ts
  vantio discover --since=7d
`;

const DISCOVER_HELP = `\
vantio discover — Shadow AI Attack Surface Discovery

Shows every AI agent call recorded in your Vantio workspace. Pro users see
SDK-monitored calls. Enterprise users (with the Phantom Engine) also see
unenrolled processes — your Shadow AI attack surface.

Calls are grouped by target host and annotated with governance status:
  ALLOWED   — call was permitted by policy
  REDACTED  — call was allowed but PII was scrubbed
  BLOCKED   — call was denied by policy
  OBSERVED  — call was seen with no Vantio trace_id (Shadow AI indicator)

Usage:
  vantio discover [options]

Options:
  --since=<period>    Look back 24h, 7d, or 30d  (default: 24h)
  --host=<hostname>   Filter to a specific target host
  --json              Output raw JSON instead of a formatted table
  -h, --help          Show this help

Examples:
  vantio discover
  vantio discover --since=7d
  vantio discover --host=api.openai.com
  vantio discover --since=30d --json
`;

// ── config store (~/.vantio/config.json) ─────────────────────────────────────

function configDir()  { return join(homedir(), ".vantio"); }
function configPath() { return join(configDir(), "config.json"); }

function readConfig() {
  try {
    return JSON.parse(readFileSync(configPath(), "utf8"));
  } catch {
    return null;
  }
}

function writeConfig(data) {
  mkdirSync(configDir(), { recursive: true, mode: 0o700 });
  writeFileSync(configPath(), JSON.stringify(data, null, 2) + "\n", { mode: 0o600 });
  // mode on writeFileSync is ignored if the file already existed — enforce it.
  try { chmodSync(configPath(), 0o600); } catch { /* non-POSIX filesystem */ }
}

function clearConfig() {
  try { rmSync(configPath()); return true; } catch { return false; }
}

function baseUrl() {
  return (process.env.VANTIO_INGEST_URL || DEFAULT_BASE).replace(/\/+$/, "");
}

function getVersion() {
  try {
    const pkgPath = join(dirname(fileURLToPath(import.meta.url)), "..", "package.json");
    return JSON.parse(readFileSync(pkgPath, "utf8")).version || "unknown";
  } catch {
    return "unknown";
  }
}

// Never print the full key. Show a recognizable prefix + suffix only.
function maskKey(key) {
  if (typeof key !== "string" || key.length === 0) return "(none)";
  if (key.length <= 10) return key.slice(0, 2) + "****";
  return `${key.slice(0, 6)}…${key.slice(-4)}`;
}

// Validate a key against GET /api/v1/config. Returns { ok, status, policyActive };
// throws on a network failure so the caller can refuse to save.
async function validateKey(base, key) {
  const res = await fetch(`${base}/api/v1/config`, {
    method: "GET",
    headers: { "x-vantio-identity": key },
    signal: AbortSignal.timeout(8000),
  });
  let policyActive = false;
  if (res.ok) {
    try {
      const data = await res.json();
      const p = data && data.policy;
      policyActive = !!(
        p && (p.enforce || p.redact_pii ||
          (Array.isArray(p.blocked_hosts) && p.blocked_hosts.length) ||
          (Array.isArray(p.allowed_hosts) && p.allowed_hosts.length) ||
          Number(p.spend_cap_usd) > 0 || Number(p.max_request_bytes) > 0)
      );
    } catch { /* body not JSON — still a valid 200 */ }
  }
  return { ok: res.ok, status: res.status, policyActive };
}

// Masked-input prompt. Masks typed characters with '*' on a TTY; falls back to a
// plain prompt elsewhere (never throws).
function promptForKey() {
  const query = "Paste your Vantio API key: ";
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    const canMask = process.stdin.isTTY === true;
    if (canMask) {
      rl._writeToOutput = function (str) {
        if (str.includes(query) || str === "\n" || str === "\r\n") rl.output.write(str);
        else rl.output.write("*");
      };
    }
    rl.question(query, (answer) => {
      rl.close();
      if (canMask) process.stdout.write("\n");
      resolve(answer.trim());
    });
  });
}

// ── commands ──────────────────────────────────────────────────────────────────

async function loginCommand(args) {
  const base = baseUrl();
  let key = (args[0] || "").trim();
  if (!key) {
    if (!process.stdin.isTTY) {
      process.stderr.write("vantio login: no API key provided.\nUsage: vantio login <key>\n");
      process.exit(1);
    }
    key = await promptForKey();
  }
  if (!key) {
    process.stderr.write("vantio login: no API key entered.\n");
    process.exit(1);
  }

  process.stdout.write(`Validating key against ${base} …\n`);
  let result;
  try {
    result = await validateKey(base, key);
  } catch (err) {
    process.stderr.write(`vantio login: could not reach Vantio at ${base} (${err.message}). Key not saved.\n`);
    process.exit(1);
  }

  if (result.status === 401) {
    process.stderr.write(
      `vantio login: that API key was rejected (401). Key not saved.\n` +
      `  Get your key from your dashboard: ${base}/dashboard\n`
    );
    process.exit(1);
  }
  if (!result.ok) {
    process.stderr.write(`vantio login: unexpected response (HTTP ${result.status}). Key not saved.\n`);
    process.exit(1);
  }

  writeConfig({ apiKey: key, ingestUrl: base, savedAt: new Date().toISOString() });
  process.stdout.write(
    `\n✓ Connected to Vantio  (${maskKey(key)})${result.policyActive ? "  — policy active" : ""}\n` +
    `  Saved to ${configPath()} (chmod 600)\n\n` +
    `Next — run your agent with no env vars:\n  vantio run node agent.js\n`
  );
}

function logoutCommand() {
  const existed = readConfig() != null;
  clearConfig();
  process.stdout.write(existed ? "✓ Logged out — stored key removed.\n" : "No stored credentials to remove.\n");
}

async function whoamiCommand() {
  const cfg = readConfig();
  if (!cfg || !cfg.apiKey) {
    process.stdout.write("Not logged in. Run: vantio login <key>\n");
    return;
  }
  const base = (cfg.ingestUrl || baseUrl()).replace(/\/+$/, "");
  process.stdout.write(`Key:    ${maskKey(cfg.apiKey)}\nServer: ${base}\n`);
  try {
    const result = await validateKey(base, cfg.apiKey);
    if (result.status === 401) {
      process.stdout.write("Status: key rejected (401) — run `vantio login` again.\n");
    } else if (result.ok) {
      process.stdout.write(`Status: connected${result.policyActive ? " — policy active" : ""}\n`);
    } else {
      process.stdout.write(`Status: unexpected response (HTTP ${result.status}).\n`);
    }
  } catch {
    process.stdout.write("Status: could not reach Vantio (offline?). Key remains stored.\n");
  }
}

function runCommand(rest) {
  // Split at the first non-flag argument (the program name) so flags meant for
  // the child (e.g. node -e) are never consumed by vantio's own parser.
  const splitAt  = rest.findIndex((a) => !a.startsWith("-"));
  const ourArgs  = splitAt === -1 ? rest : rest.slice(0, splitAt);
  const progArgs = splitAt === -1 ? []   : rest.slice(splitAt);

  const { values } = parseArgs({
    args: ourArgs,
    options: {
      audit:   { type: "boolean", short: "a", default: false },
      summary: { type: "boolean", short: "s", default: false },
    },
    allowPositionals: false,
  });

  if (progArgs.length === 0) {
    process.stderr.write(
      "vantio run: no program specified\n\nUsage: vantio run [--audit] [--summary] <program> [...args]\n",
    );
    process.exit(1);
  }

  const [program, ...programArgs] = progArgs;

  // ── Node.js runtime detection ──────────────────────────────────────────────
  const NODE_RUNTIMES = new Set(["node", "node.exe", "npx", "npx.cmd", "tsx", "ts-node"]);
  const isNodeRuntime = (prog) => {
    const base = prog.split(/[\\/]/).pop().replace(/\.exe$/, "");
    return NODE_RUNTIMES.has(base);
  };

  // Node runtimes get the interceptor via NODE_OPTIONS (honored by every node
  // invocation in the tree) rather than a CLI argument.
  let extraNodeOptions = "";
  if (isNodeRuntime(program)) {
    const interceptorPath = join(dirname(fileURLToPath(import.meta.url)), "interceptor.cjs");
    const requirePath = /\s/.test(interceptorPath) ? `"${interceptorPath}"` : interceptorPath;
    extraNodeOptions = `--require ${requirePath}`;
  } else {
    process.stderr.write('\n[ ∅ VANTIO ] Python runtime — use the Python SDK for interception: pip install vantio-agent-sdk\n\n');
  }

  // Auto-load the saved key/server if the environment doesn't already set them,
  // so `vantio run …` just works after `vantio login`. An explicit env var wins.
  let injectedKey  = null;
  let injectedBase = null;
  if (!process.env.VANTIO_API_KEY) {
    const cfg = readConfig();
    if (cfg && cfg.apiKey) {
      injectedKey = cfg.apiKey;
      if (!process.env.VANTIO_INGEST_URL && cfg.ingestUrl && cfg.ingestUrl !== DEFAULT_BASE) {
        injectedBase = cfg.ingestUrl;
      }
    }
  }

  const mergedNodeOptions = [process.env.NODE_OPTIONS, extraNodeOptions].filter(Boolean).join(" ");

  const childEnv = Object.assign(Object.create(null), process.env, {
    ...(values.audit     ? { VANTIO_AUDIT_MODE: "1" } : {}),
    ...(values.summary   ? { VANTIO_SUMMARY:    "1" } : {}),
    ...(extraNodeOptions ? { NODE_OPTIONS: mergedNodeOptions } : {}),
    ...(injectedKey      ? { VANTIO_API_KEY: injectedKey } : {}),
    ...(injectedBase     ? { VANTIO_INGEST_URL: injectedBase } : {}),
  });

  const child = spawn(program, programArgs, { stdio: "inherit", env: childEnv, shell: false });

  child.on("error", (err) => {
    process.stderr.write(`vantio: failed to start '${program}': ${err.message}\n`);
    process.exit(1);
  });

  child.on("exit", (code, signal) => {
    if (signal !== null) { process.kill(process.pid, signal); return; }
    process.exit(code ?? 1);
  });
}

// ── discover ─────────────────────────────────────────────────────────────────

// Pad a string to a fixed width, truncating with '…' if needed.
function col(str, width) {
  const s = String(str ?? "");
  if (s.length > width) return s.slice(0, width - 1) + "…";
  return s.padEnd(width);
}

// Render a human-readable discovery table from grouped event data.
// Expected shape: { period?, groups: [{ target_host, call_count,
//   action_breakdown: { ALLOWED?, REDACTED?, BLOCKED?, OBSERVED? },
//   first_seen?, last_seen?, shadow_ai? }] }
// Falls back gracefully when the shape differs.
function renderDiscoveryTable(data, since) {
  const groups = Array.isArray(data)
    ? data
    : Array.isArray(data?.groups)
      ? data.groups
      : null;

  if (!groups || groups.length === 0) {
    process.stdout.write(`No AI agent calls recorded in the last ${since}.\n`);
    return;
  }

  const STATUSES = ["ALLOWED", "REDACTED", "BLOCKED", "OBSERVED"];
  const W = { host: 32, calls: 7, allowed: 9, redacted: 9, blocked: 9, observed: 9, shadow: 8, last: 20 };

  const header =
    col("TARGET HOST", W.host) + "  " +
    col("CALLS", W.calls) + "  " +
    col("ALLOWED", W.allowed) + "  " +
    col("REDACTED", W.redacted) + "  " +
    col("BLOCKED", W.blocked) + "  " +
    col("OBSERVED", W.observed) + "  " +
    col("SHADOW?", W.shadow) + "  " +
    col("LAST SEEN", W.last);

  const divider = "-".repeat(header.length);

  process.stdout.write(`\nShadow AI Attack Surface — last ${since}\n`);
  process.stdout.write(`${divider}\n${header}\n${divider}\n`);

  let shadowCount = 0;
  for (const g of groups) {
    const breakdown = g.action_breakdown || g.actionBreakdown || {};
    const isShadow  = g.shadow_ai ?? (Number(breakdown.OBSERVED) > 0 && !g.trace_id);
    if (isShadow) shadowCount++;

    const lastSeen = g.last_seen || g.lastSeen
      ? new Date(g.last_seen || g.lastSeen).toISOString().replace("T", " ").slice(0, 19) + " UTC"
      : "—";

    const row =
      col(g.target_host || g.host || "unknown", W.host) + "  " +
      col(g.call_count ?? g.callCount ?? "—", W.calls) + "  " +
      col(breakdown.ALLOWED  ?? "—", W.allowed)  + "  " +
      col(breakdown.REDACTED ?? "—", W.redacted) + "  " +
      col(breakdown.BLOCKED  ?? "—", W.blocked)  + "  " +
      col(breakdown.OBSERVED ?? "—", W.observed) + "  " +
      col(isShadow ? "⚠ YES" : "no", W.shadow)  + "  " +
      col(lastSeen, W.last);

    process.stdout.write(`${row}\n`);
  }

  process.stdout.write(`${divider}\n`);
  process.stdout.write(`${groups.length} host(s) shown`);
  if (shadowCount > 0) {
    process.stdout.write(
      `  |  ⚠  ${shadowCount} Shadow AI indicator(s) detected — unenrolled processes calling LLM endpoints.\n` +
      `   Visit vantio.ai/dashboard to investigate and enroll them under governance.\n`
    );
  } else {
    process.stdout.write("  |  No Shadow AI indicators detected.\n");
  }
}

async function discoverCommand(args) {
  const { values } = parseArgs({
    args,
    options: {
      since: { type: "string",  default: "24h" },
      host:  { type: "string" },
      json:  { type: "boolean", default: false },
      help:  { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) {
    process.stdout.write(DISCOVER_HELP);
    return;
  }

  const validPeriods = new Set(["24h", "7d", "30d"]);
  if (!validPeriods.has(values.since)) {
    process.stderr.write(`vantio discover: invalid --since value '${values.since}'. Use 24h, 7d, or 30d.\n`);
    process.exit(1);
  }

  const cfg    = readConfig();
  const apiKey = process.env.VANTIO_API_KEY || cfg?.apiKey;
  if (!apiKey) {
    process.stdout.write("Run `vantio login` first to connect your workspace.\n");
    process.exit(1);
  }

  const base   = (cfg?.ingestUrl || baseUrl()).replace(/\/+$/, "");
  const params = new URLSearchParams({ since: values.since });
  if (values.host) params.set("host", values.host);

  let res;
  try {
    res = await fetch(`${base}/api/v1/discover?${params}`, {
      method:  "GET",
      headers: { "x-vantio-identity": apiKey },
      signal:  AbortSignal.timeout(10000),
    });
  } catch (err) {
    process.stdout.write(
      `Discovery: could not reach the Vantio API (${err.message}).\n` +
      `  Check your connection or run \`vantio whoami\` to verify credentials.\n`
    );
    process.exit(1);
  }

  if (res.status === 401) {
    process.stdout.write(
      "[ ∅ VANTIO ] Invalid or expired API key. Run `vantio login` to reconnect.\n"
    );
    process.exit(1);
  }

  if (res.status === 404) {
    process.stdout.write(
      "Discovery is available for Pro and Enterprise accounts. " +
      "Upgrade at vantio.ai/pricing to unlock full access.\n"
    );
    return;
  }

  if (!res.ok) {
    process.stdout.write(`Discovery: unexpected response (HTTP ${res.status}).\n`);
    process.exit(1);
  }

  let data;
  try {
    data = await res.json();
  } catch {
    process.stdout.write("Discovery: response was not valid JSON.\n");
    process.exit(1);
  }

  if (values.json) {
    process.stdout.write(JSON.stringify(data, null, 2) + "\n");
    return;
  }

  renderDiscoveryTable(data, values.since);
}

// ── dispatch ────────────────────────────────────────────────────────────────

const [command, ...rest] = process.argv.slice(2);

if (!command || command === "--help" || command === "-h" || command === "help") {
  process.stdout.write(USAGE);
  process.exit(0);
}
if (command === "--version" || command === "-v") {
  process.stdout.write(`${getVersion()}\n`);
  process.exit(0);
}

switch (command) {
  case "run":
    runCommand(rest);
    break;
  case "login":
    await loginCommand(rest);
    break;
  case "logout":
    logoutCommand();
    break;
  case "whoami":
    await whoamiCommand();
    break;
  case "discover":
    await discoverCommand(rest);
    break;
  default:
    process.stderr.write(`vantio: unknown command '${command}'\n\n${USAGE}`);
    process.exit(1);
}
