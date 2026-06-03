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
  default:
    process.stderr.write(`vantio: unknown command '${command}'\n\n${USAGE}`);
    process.exit(1);
}
