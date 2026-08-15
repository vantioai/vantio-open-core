#!/usr/bin/env node
import { spawn }         from "node:child_process";
import { parseArgs }     from "node:util";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { homedir, hostname as osHostname } from "node:os";
import { mkdirSync, readFileSync, writeFileSync, rmSync, chmodSync, readdirSync, statSync, existsSync, watch } from "node:fs";
import readline          from "node:readline";
import { randomUUID }    from "node:crypto";

const DEFAULT_BASE = "https://vantio.ai";

const USAGE = `\
Vantio AI — process supervisor

Usage:
  vantio login [key]          Save & validate your API key (no env vars after this)
  vantio logout               Remove the stored key
  vantio whoami               Show the stored key (masked) + connection status
  vantio run [flags] <prog>   Spawn <prog> under the Vantio execution context
  vantio discover [options]   Show Shadow AI attack surface (AI calls in your workspace)
  vantio prove [options]      Generate an auditor-ready proof artifact from a run log
  vantio search [query]       Search local run logs (host, path, action, free text)
  vantio tail [options]       Show the latest calls from a captured run
  vantio diff <a> <b>         Compare two local runs (hosts, counts, bytes)

Flags (run):
  --audit,   -a   Enable audit mode (VANTIO_AUDIT_MODE=1).
  --summary, -s   Print a run summary on exit.

After 'vantio login', plain 'vantio run node agent.js' just works — the key is
loaded from ~/.vantio/config.json and injected into the child process. An
explicit VANTIO_API_KEY in your environment always takes precedence.

Examples:
  vantio login vk_live_xxx
  vantio run node agent.js
  vantio run python agent.py
  vantio run --audit tsx agent.ts
  vantio discover --since=7d
  vantio discover --local
  vantio prove
  vantio prove --list
  vantio prove --format=md --out=audit.md
  vantio search openai
  vantio tail -n 20
  vantio diff 0xabc 0xdef
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

Free-tier local scan (--local):
  Reads run logs written to ~/.vantio/runs/ by \`vantio run\` on this machine.
  No API key required. Covers only processes started with \`vantio run\`.
  Pro adds dashboard sync and cross-machine history.
  Enterprise (Phantom Engine) adds detection of unenrolled processes.

Usage:
  vantio discover [options]

Options:
  --since=<period>    Look back 24h, 7d, or 30d  (default: 24h)
  --host=<hostname>   Filter to a specific target host
  --json              Output raw JSON instead of a formatted table
  --local             Show local run logs only — no API key required (Free tier)
  -h, --help          Show this help

Examples:
  vantio discover
  vantio discover --since=7d
  vantio discover --host=api.openai.com
  vantio discover --since=30d --json
  vantio discover --local
  vantio discover --local --since=7d
`;

const PROVE_HELP = `\
vantio prove — Auditor-Ready Proof Artifacts

Generates an auditor-ready proof artifact (HTML or Markdown report) from a
vantio run log. Reports include: trace ID, machine, PID, byte counts, host
breakdown, and summary counts. Reports contain NO prompts or completions.

Run logs are written automatically to ~/.vantio/runs/ when LLM calls are
intercepted by \`vantio run\`.

Usage:
  vantio prove [options]

Options:
  --list              List available local run logs
  --run=<trace-id>    Generate a report for a specific run (by trace ID or prefix)
  --from=<file>       Generate a report from an explicit log file path
  --format=html|md    Output format (default: html)
  --out=<file>        Write output to a file (default: vantio-proof-<id>.html)
  -h, --help          Show this help

Examples:
  vantio prove                               → most recent run, HTML to file
  vantio prove --list                        → list available runs
  vantio prove --run=0x1a2b3c4d             → specific run by trace ID
  vantio prove --format=md                   → Markdown to stdout
  vantio prove --format=html --out=proof.html
`;

const SEARCH_HELP = `\
vantio search — Search local Optics run logs

Find observed LLM calls across ~/.vantio/runs/ by free text, host, provider,
path, or action. Metadata only — never prompts or completions. Free, no key.

Usage:
  vantio search [query] [options]

Options:
  --host=<hostname>   Filter to a target host (substring match)
  --provider=<name>   Filter by provider label (substring match)
  --action=<label>    Filter by action (e.g. OBSERVED, BLOCKED)
  --run=<trace-id>    Limit to one run (trace ID or prefix)
  --since=24h|7d|30d  Only runs newer than this window (default: all)
  --json              Output raw JSON
  -h, --help          Show this help

Examples:
  vantio search openai
  vantio search --host=api.anthropic.com
  vantio search chat --action=OBSERVED --since=7d
  vantio search --run=0x1a2b3c4d --json
`;

const TAIL_HELP = `\
vantio tail — Latest calls from a captured Optics run

Prints the most recent observed calls from a local run log so you can inspect
egress without opening Mission Control. Free, no key.

Usage:
  vantio tail [options]

Options:
  --run=<trace-id>    Run to read (default: most recent local run)
  -n, --lines=<n>     Number of calls to show (default: 20)
  -f, --follow        Keep watching the run log for new calls
  --json              Output raw JSON
  -h, --help          Show this help

Examples:
  vantio tail
  vantio tail -n 50
  vantio tail --run=0x1a2b3c4d
  vantio tail -f
`;

const DIFF_HELP = `\
vantio diff — Compare two local Optics runs

Shows what changed between two captured runs: hosts added or removed, call
counts, and byte totals. Metadata only. Free, no key.

Usage:
  vantio diff <run-a> <run-b> [options]

Arguments:
  <run-a> <run-b>     Trace IDs or prefixes of two local run logs

Options:
  --json              Output raw JSON
  -h, --help          Show this help

Examples:
  vantio diff 0xabc123 0xdef456
  vantio diff 0xabc 0xdef --json
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

// Validate a key against GET /api/v1/config. Returns { ok, status, policyActive, tier };
// throws on a network failure so the caller can refuse to save.
//
// `tier` distinguishes an authenticated-but-free key from a paid one. This
// matters because /api/v1/ingest and /api/v1/discover 403 for non-PRO/
// ENTERPRISE tenants (by design — dashboard sync is a paid feature), while
// /api/v1/config fails open with a permissive policy for everyone. Without
// checking tier explicitly, a free-tier user who logs in looks identical to a
// paid one until their events start silently 403ing.
function isPaidTier(tier) {
  return tier === "PRO" || tier === "ENTERPRISE";
}

async function validateKey(base, key) {
  const res = await fetch(`${base}/api/v1/config`, {
    method: "GET",
    headers: { "x-vantio-identity": key },
    signal: AbortSignal.timeout(8000),
  });
  let policyActive = false;
  let tier = null;
  if (res.ok) {
    try {
      const data = await res.json();
      const p = data && data.policy;
      tier = typeof data?.tier === "string" ? data.tier : null;
      policyActive = !!(
        p && (p.enforce || p.redact_pii ||
          (Array.isArray(p.blocked_hosts) && p.blocked_hosts.length) ||
          (Array.isArray(p.allowed_hosts) && p.allowed_hosts.length) ||
          Number(p.spend_cap_usd) > 0 || Number(p.max_request_bytes) > 0)
      );
    } catch { /* body not JSON — still a valid 200 */ }
  }
  return { ok: res.ok, status: res.status, policyActive, tier };
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
      `  Get your key at vantio.ai/dashboard\n`
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
  if (!isPaidTier(result.tier)) {
    process.stdout.write(
      "\nYou're on the Free plan — `vantio run` will keep observing calls locally in your\n" +
      "terminal, but dashboard sync, `vantio discover`, and policy enforcement require\n" +
      "Pro or Enterprise. Upgrade at vantio.ai/pricing.\n"
    );
  }
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
      const plan = result.tier ? ` — ${isPaidTier(result.tier) ? result.tier : "FREE"} plan` : "";
      process.stdout.write(`Status: connected${plan}${result.policyActive ? ", policy active" : ""}\n`);
      if (!isPaidTier(result.tier)) {
        process.stdout.write("  Dashboard sync and `vantio discover` require Pro or Enterprise — vantio.ai/pricing\n");
      }
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
  const isPythonRuntime = (prog) => {
    const base = prog.split(/[\\/]/).pop().replace(/\.exe$/, "").toLowerCase();
    return base === "python" || base === "python3" || base === "py" || /^python3\.\d+$/.test(base);
  };

  // Node runtimes get the interceptor via NODE_OPTIONS (honored by every node
  // invocation in the tree) rather than a CLI argument.
  // Python runtimes get sitecustomize.py on PYTHONPATH (needs vantio-agent-sdk).
  let extraNodeOptions = "";
  let extraPythonPath = "";
  if (isNodeRuntime(program)) {
    const interceptorPath = join(dirname(fileURLToPath(import.meta.url)), "interceptor.cjs");
    const requirePath = /\s/.test(interceptorPath) ? `"${interceptorPath}"` : interceptorPath;
    extraNodeOptions = `--require ${requirePath}`;
  } else if (isPythonRuntime(program)) {
    extraPythonPath = join(dirname(fileURLToPath(import.meta.url)), "python-wrap");
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
  const delim = process.platform === "win32" ? ";" : ":";
  const mergedPythonPath = extraPythonPath
    ? [extraPythonPath, process.env.PYTHONPATH].filter(Boolean).join(delim)
    : "";

  // One stable trace id for this `vantio run` — shared with interceptor ingest
  // and (on Enterprise) Phantom Engine --inject for Tier 1↔3 correlation.
  const runTraceId = process.env.VANTIO_TRACE_ID || `0x${randomUUID().replace(/-/g, "").slice(0, 16)}`;

  const childEnv = Object.assign(Object.create(null), process.env, {
    VANTIO_TRACE_ID: runTraceId,
    ...(values.audit     ? { VANTIO_AUDIT_MODE: "1" } : {}),
    ...(values.summary   ? { VANTIO_SUMMARY:    "1" } : {}),
    ...(extraNodeOptions ? { NODE_OPTIONS: mergedNodeOptions } : {}),
    ...(mergedPythonPath ? { PYTHONPATH: mergedPythonPath } : {}),
    ...(injectedKey      ? { VANTIO_API_KEY: injectedKey } : {}),
    ...(injectedBase     ? { VANTIO_INGEST_URL: injectedBase } : {}),
  });

  process.stderr.write(`[ ∅ VANTIO ] run trace_id=${runTraceId}\n`);

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

// ── shared formatting helpers ────────────────────────────────────────────────

// Pad a string to a fixed width, truncating with '…' if needed.
function col(str, width) {
  const s = String(str ?? "");
  if (s.length > width) return s.slice(0, width - 1) + "…";
  return s.padEnd(width);
}

// ── prove helpers ─────────────────────────────────────────────────────────────

function runsDir() { return join(configDir(), "runs"); }

function parseSincePeriod(since) {
  if (since === "7d")  return 7  * 24 * 60 * 60 * 1000;
  if (since === "30d") return 30 * 24 * 60 * 60 * 1000;
  return 24 * 60 * 60 * 1000; // "24h" default
}

// Escape HTML entities — used in the HTML proof report generator.
function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatBytes(n) {
  if (n < 1024) return n.toLocaleString() + " B";
  if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
  return (n / (1024 * 1024)).toFixed(2) + " MB";
}

function generateHtmlReport(log) {
  const calls      = Array.isArray(log.calls) ? log.calls : [];
  const summary    = log.summary || {};
  const totalCalls = summary.total_calls ?? calls.length;
  const totalBytes = summary.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0);
  const hosts      = Array.isArray(summary.hosts) ? summary.hosts
                     : [...new Set(calls.map((c) => c.hostname || "?"))];
  const redacted   = summary.redacted ?? 0;
  const blocked    = summary.blocked  ?? 0;
  const traceId    = escHtml(log.trace_id    || "—");
  const pid        = escHtml(log.pid         || "—");
  const machine    = escHtml(log.machine     || "—");
  const startedAt  = escHtml(log.started_at  || "—");
  const genAt      = escHtml(log.generated_at || new Date().toISOString());
  const durationMs = log.duration_ms != null ? `${Number(log.duration_ms).toLocaleString()} ms` : "—";
  const cliVer     = escHtml(log.cli_version || "—");

  const rows = calls.map((c, i) => {
    const act = (c.action || "OBSERVED").toUpperCase();
    const cls = act.startsWith("BLOCKED") ? "blocked" : act.toLowerCase();
    return `        <tr>
          <td class="num">${i + 1}</td>
          <td class="mono">${escHtml(c.hostname || "—")}</td>
          <td><span class="badge badge-${cls}">${escHtml(act)}</span></td>
          <td class="num">${c.bytes != null ? Number(c.bytes).toLocaleString() : "—"}</td>
          <td class="mono">${escHtml(c.ts || "—")}</td>
        </tr>`;
  }).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vantio Proof — ${traceId}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif; margin: 0; padding: 40px 20px; background: #f7f7f7; color: #111; }
    .page { max-width: 960px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,.09); padding: 44px 52px; }
    h1 { font-size: 1.3rem; font-weight: 700; margin: 0 0 4px; letter-spacing: -.3px; }
    .subtitle { color: #555; font-size: .875rem; margin: 0 0 28px; }
    .privacy-banner { background: #f0faf0; border: 1px solid #b3d9b3; border-radius: 6px; padding: 10px 16px; font-size: .875rem; margin-bottom: 32px; color: #1a5c1a; }
    h2 { font-size: .95rem; font-weight: 600; margin: 32px 0 12px; color: #333; border-top: 1px solid #eee; padding-top: 28px; }
    h2:first-of-type { border-top: none; padding-top: 0; }
    dl.meta { display: grid; grid-template-columns: max-content 1fr; gap: 5px 24px; margin: 0 0 8px; font-size: .875rem; }
    dl.meta dt { color: #666; font-weight: 500; }
    dl.meta dd { margin: 0; font-family: "SFMono-Regular", Consolas, monospace; }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 12px; margin-bottom: 8px; }
    .metric { background: #f5f5f5; border-radius: 6px; padding: 14px 16px; }
    .metric-value { font-size: 1.75rem; font-weight: 700; font-family: "SFMono-Regular", Consolas, monospace; line-height: 1.1; }
    .metric-label { color: #666; font-size: .72rem; margin-top: 4px; text-transform: uppercase; letter-spacing: .5px; }
    table { width: 100%; border-collapse: collapse; font-size: .835rem; }
    thead th { text-align: left; padding: 8px 10px; background: #f5f5f5; border-bottom: 2px solid #e0e0e0; font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .4px; color: #555; }
    tbody td { padding: 6px 10px; border-bottom: 1px solid #f0f0f0; }
    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover { background: #fafafa; }
    .num  { text-align: right; color: #888; }
    .mono { font-family: "SFMono-Regular", Consolas, monospace; font-size: .8rem; }
    .badge { display: inline-block; font-size: .7rem; font-weight: 600; padding: 2px 7px; border-radius: 3px; text-transform: uppercase; letter-spacing: .3px; font-family: "SFMono-Regular", Consolas, monospace; }
    .badge-observed { background: #f0f0f0; color: #555; }
    .badge-allowed  { background: #e6f7ee; color: #1a6b3a; }
    .badge-redacted { background: #fff8e0; color: #7a5500; }
    .badge-blocked  { background: #fde8e8; color: #9b1c1c; }
    .footer { margin-top: 40px; border-top: 1px solid #eee; padding-top: 16px; color: #aaa; font-size: .76rem; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
    .footer a { color: #aaa; }
    @media (max-width: 640px) { .page { padding: 24px 20px; } .metrics { grid-template-columns: repeat(2, 1fr); } }
  </style>
</head>
<body>
  <div class="page">
    <h1>[ ∅ VANTIO ] Run Proof Artifact</h1>
    <p class="subtitle">Auditor-ready AI governance evidence · @vantio/cli v${cliVer}</p>

    <div class="privacy-banner">
      ✓ <strong>No prompts or completions captured.</strong>
      This report contains only governance metadata: hostnames, byte counts, process IDs, trace IDs, and action labels.
    </div>

    <h2>Run identity</h2>
    <dl class="meta">
      <dt>Trace ID</dt>     <dd>${traceId}</dd>
      <dt>Run started</dt>  <dd>${startedAt}</dd>
      <dt>Generated</dt>    <dd>${genAt}</dd>
      <dt>Duration</dt>     <dd>${durationMs}</dd>
      <dt>Process ID</dt>   <dd>${pid}</dd>
      <dt>Machine</dt>      <dd>${machine}</dd>
      <dt>CLI version</dt>  <dd>@vantio/cli v${cliVer}</dd>
    </dl>

    <h2>Summary</h2>
    <div class="metrics">
      <div class="metric"><div class="metric-value">${totalCalls.toLocaleString()}</div><div class="metric-label">Total calls</div></div>
      <div class="metric"><div class="metric-value">${totalBytes > 0 ? formatBytes(totalBytes) : "—"}</div><div class="metric-label">Total bytes</div></div>
      <div class="metric"><div class="metric-value">${hosts.length}</div><div class="metric-label">Unique hosts</div></div>
      <div class="metric"><div class="metric-value">${redacted}</div><div class="metric-label">PII redacted</div></div>
      <div class="metric"><div class="metric-value">${blocked}</div><div class="metric-label">Blocked</div></div>
    </div>

    <h2>Call log (${totalCalls.toLocaleString()} call${totalCalls === 1 ? "" : "s"})</h2>
    ${calls.length === 0
      ? "<p style=\"color:#888;font-size:.875rem\">No calls recorded in this run log.</p>"
      : `<table>
      <thead><tr>
        <th class="num">#</th><th>Host</th><th>Action</th>
        <th class="num">Bytes</th><th>Timestamp</th>
      </tr></thead>
      <tbody>
${rows}
      </tbody>
    </table>`}

    <div class="footer">
      <span>Generated by <a href="https://vantio.ai">Vantio AI</a> · <a href="https://vantio.ai/privacy">Privacy policy</a></span>
      <span>Report contains no prompts, completions, or content</span>
    </div>
  </div>
</body>
</html>`;
}

function generateMarkdownReport(log) {
  const calls      = Array.isArray(log.calls) ? log.calls : [];
  const summary    = log.summary || {};
  const totalCalls = summary.total_calls ?? calls.length;
  const totalBytes = summary.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0);
  const hosts      = Array.isArray(summary.hosts) ? summary.hosts
                     : [...new Set(calls.map((c) => c.hostname || "?"))];
  const redacted   = summary.redacted ?? 0;
  const blocked    = summary.blocked  ?? 0;

  const rows = calls.map((c, i) =>
    `| ${i + 1} | \`${c.hostname || "—"}\` | \`${(c.action || "OBSERVED").toUpperCase()}\` | ${c.bytes != null ? Number(c.bytes).toLocaleString() : "—"} | \`${c.ts || "—"}\` |`
  ).join("\n");

  return `# [ ∅ VANTIO ] Run Proof Artifact

> Auditor-ready AI governance evidence · @vantio/cli v${log.cli_version || "—"}

**Privacy notice:** This report contains only governance metadata — hostnames,
byte counts, process IDs, trace IDs, and action labels. No prompt content,
completions, API keys, or PII is present.

---

## Run identity

| Field | Value |
|-------|-------|
| Trace ID | \`${log.trace_id || "—"}\` |
| Run started | \`${log.started_at || "—"}\` |
| Generated | \`${log.generated_at || new Date().toISOString()}\` |
| Duration | \`${log.duration_ms != null ? `${Number(log.duration_ms).toLocaleString()} ms` : "—"}\` |
| Process ID | \`${log.pid || "—"}\` |
| Machine | \`${log.machine || "—"}\` |
| CLI version | \`@vantio/cli v${log.cli_version || "—"}\` |

---

## Summary

| Metric | Value |
|--------|-------|
| Total calls | **${totalCalls.toLocaleString()}** |
| Total bytes | ${totalBytes > 0 ? totalBytes.toLocaleString() : "—"} |
| Unique hosts | ${hosts.length} |
| PII redacted | ${redacted} |
| Blocked | ${blocked} |

Hosts: ${hosts.map((h) => `\`${h}\``).join(", ") || "—"}

---

## Call log (${totalCalls} call${totalCalls === 1 ? "" : "s"})

| # | Host | Action | Bytes | Timestamp |
|---|------|--------|-------|-----------|
${rows || "| — | — | — | — | — |"}

---

*Generated by [Vantio AI](https://vantio.ai) · @vantio/cli v${log.cli_version || "—"}*
*Report contains no prompts, completions, or content · [Privacy policy](https://vantio.ai/privacy)*
`;
}

function listRuns(dir) {
  let entries = [];
  try {
    entries = readdirSync(dir)
      .filter((f) => f.endsWith(".json"))
      .map((f) => {
        try {
          const log = JSON.parse(readFileSync(join(dir, f), "utf8"));
          if (log?.vantio_run_log !== "1") return null;
          return { f, log };
        } catch { return null; }
      })
      .filter(Boolean)
      .sort((a, b) => {
        const ta = a.log.generated_at ? new Date(a.log.generated_at).getTime() : 0;
        const tb = b.log.generated_at ? new Date(b.log.generated_at).getTime() : 0;
        return tb - ta;
      });
  } catch { /* dir doesn't exist */ }

  if (entries.length === 0) {
    process.stdout.write(
      "No run logs found. Run an agent first:\n" +
      "  vantio run node agent.js\n\n" +
      "Run logs are written to ~/.vantio/runs/ when LLM calls are intercepted.\n"
    );
    return;
  }

  process.stdout.write(`\nLocal run logs (stored in ${dir}):\n\n`);
  const W = { trace: 38, calls: 7, bytes: 14, date: 24 };
  const hdr = col("TRACE ID", W.trace) + "  " + col("CALLS", W.calls) + "  " + col("TOTAL BYTES", W.bytes) + "  " + col("DATE", W.date);
  const div = "-".repeat(hdr.length);
  process.stdout.write(`${div}\n${hdr}\n${div}\n`);
  for (const { log } of entries) {
    const calls = log.summary?.total_calls ?? (Array.isArray(log.calls) ? log.calls.length : "—");
    const bytes = log.summary?.total_bytes;
    const date  = log.generated_at
      ? new Date(log.generated_at).toISOString().replace("T", " ").slice(0, 19) + " UTC"
      : "—";
    process.stdout.write(
      col(log.trace_id || "—", W.trace) + "  " +
      col(calls, W.calls) + "  " +
      col(bytes != null && bytes > 0 ? bytes.toLocaleString() : "—", W.bytes) + "  " +
      col(date, W.date) + "\n"
    );
  }
  process.stdout.write(`${div}\n${entries.length} run log(s)\n\n`);
  process.stdout.write(
    "Generate a proof artifact:\n" +
    "  vantio prove                   → most recent run (HTML)\n" +
    "  vantio prove --run=<trace-id>  → specific run\n" +
    "  vantio prove --format=md       → Markdown to stdout\n"
  );
}

function findRunByPrefix(dir, prefix, cmd = "prove") {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch {
    process.stderr.write(`vantio ${cmd}: no run logs found in ~/.vantio/runs/\n`);
    process.exit(1);
  }
  const norm = prefix.replace(/[^a-zA-Z0-9_-]/g, "_");
  const matches = files.filter((f) => f.includes(norm));
  if (matches.length === 0) {
    process.stderr.write(
      `vantio ${cmd}: no run found with trace ID containing '${prefix}'\n` +
      "  Run `vantio prove --list` to see available runs.\n"
    );
    process.exit(1);
  }
  if (matches.length > 1) {
    process.stderr.write(`vantio ${cmd}: '${prefix}' matches ${matches.length} runs. Use a longer prefix:\n`);
    for (const f of matches) process.stderr.write(`  ${f.replace(/\.json$/, "")}\n`);
    process.exit(1);
  }
  return join(dir, matches[0]);
}

function findMostRecentRun(dir) {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch { return null; }
  if (files.length === 0) return null;
  let newest = null, newestTime = 0;
  for (const f of files) {
    const p = join(dir, f);
    try { const s = statSync(p); if (s.mtimeMs > newestTime) { newestTime = s.mtimeMs; newest = p; } }
    catch { /* skip */ }
  }
  return newest;
}

async function proveCommand(args) {
  const { values } = parseArgs({
    args,
    options: {
      list:   { type: "boolean", default: false },
      run:    { type: "string" },
      from:   { type: "string" },
      format: { type: "string",  default: "html" },
      out:    { type: "string" },
      help:   { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) { process.stdout.write(PROVE_HELP); return; }

  const dir = runsDir();

  if (values.list) { listRuns(dir); return; }

  let logPath;
  if (values.from) {
    logPath = values.from.replace(/^~/, homedir());
    if (!existsSync(logPath)) {
      process.stderr.write(`vantio prove: file not found: ${logPath}\n`);
      process.exit(1);
    }
  } else if (values.run) {
    logPath = findRunByPrefix(dir, values.run);
  } else {
    logPath = findMostRecentRun(dir);
    if (!logPath) {
      process.stdout.write(
        "No local run logs found. Run an agent first:\n" +
        "  vantio run node agent.js\n\n" +
        "Then generate a proof artifact:\n" +
        "  vantio prove\n"
      );
      return;
    }
    process.stderr.write(`[ ∅ VANTIO ] Using most recent run log: ${logPath}\n`);
  }

  let log;
  try { log = JSON.parse(readFileSync(logPath, "utf8")); }
  catch (err) {
    process.stderr.write(`vantio prove: could not read log: ${err.message}\n`);
    process.exit(1);
  }

  const format = (values.format || "html").toLowerCase();
  if (format !== "html" && format !== "md") {
    process.stderr.write(`vantio prove: invalid format '${format}'. Use html or md.\n`);
    process.exit(1);
  }

  const report = format === "html" ? generateHtmlReport(log) : generateMarkdownReport(log);

  if (values.out) {
    writeFileSync(values.out, report, "utf8");
    process.stdout.write(`✓ Proof artifact written to: ${values.out}\n`);
  } else if (format === "html") {
    const safeid = (log.trace_id || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40);
    const outPath = `vantio-proof-${safeid}.html`;
    writeFileSync(outPath, report, "utf8");
    process.stdout.write(`✓ Proof artifact written to: ${outPath}\n`);
  } else {
    process.stdout.write(report);
  }
}

// ── discover --local (Free-tier local scan) ───────────────────────────────────

// Known LLM provider credential env vars — presence suggests active AI usage.
const LLM_KEY_ENVS = [
  "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
  "COHERE_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY", "MISTRAL_API_KEY",
  "PERPLEXITY_API_KEY", "AZURE_OPENAI_KEY", "AZURE_OPENAI_API_KEY",
  "OPENROUTER_API_KEY", "BEDROCK_ACCESS_KEY",
];

async function discoverLocalCommand(since) {
  const dir    = runsDir();
  const cutoff = Date.now() - parseSincePeriod(since);

  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch { /* dir missing */ }

  // Aggregate call data by host from local run logs
  const hostMap = new Map();
  let scannedRuns = 0;
  for (const f of files) {
    const p = join(dir, f);
    try {
      const s = statSync(p);
      if (s.mtimeMs < cutoff) continue;
      const log = JSON.parse(readFileSync(p, "utf8"));
      if (log?.vantio_run_log !== "1" || !Array.isArray(log.calls)) continue;
      scannedRuns++;
      const ts = log.generated_at ? new Date(log.generated_at).getTime() : 0;
      for (const call of log.calls) {
        const h = call.hostname || "unknown";
        const rec = hostMap.get(h) || { host: h, total: 0, bytes: 0, last_seen: null };
        rec.total++;
        rec.bytes += call.bytes || 0;
        if (!rec.last_seen || ts > rec.last_seen) rec.last_seen = ts;
        hostMap.set(h, rec);
      }
    } catch { /* skip corrupt files */ }
  }

  // Scan current environment for LLM credentials
  const foundKeys = LLM_KEY_ENVS.filter((k) => process.env[k]);

  process.stdout.write(`\nVantio Observe — local run history (last ${since})\n`);
  process.stdout.write(`  Scanned ${scannedRuns} run log(s) from ${dir}\n`);

  if (foundKeys.length > 0) {
    process.stdout.write(`\nLLM credential(s) found in current environment:\n`);
    for (const k of foundKeys) {
      const val = process.env[k] || "";
      const masked = val.length > 8 ? val.slice(0, 4) + "…" + val.slice(-4) : "****";
      process.stdout.write(`  ${k}=${masked}\n`);
    }
    process.stdout.write(`  → These suggest active AI usage. Run \`vantio run\` to bring calls under governance.\n`);
  }

  if (hostMap.size === 0) {
    process.stdout.write(`\nNo local run logs found for the last ${since}.\n`);
    process.stdout.write(`  Run an agent:  vantio run node agent.js\n`);
    process.stdout.write(`  Then re-run:   vantio discover --local\n`);
  } else {
    const W = { host: 32, calls: 7, bytes: 14, last: 24 };
    const hdr = col("TARGET HOST", W.host) + "  " + col("CALLS", W.calls) + "  " + col("TOTAL BYTES", W.bytes) + "  " + col("LAST RUN", W.last);
    const div = "-".repeat(hdr.length);
    const hosts = [...hostMap.values()].sort((a, b) => (b.last_seen || 0) - (a.last_seen || 0));

    process.stdout.write(`\n${div}\n${hdr}\n${div}\n`);
    for (const h of hosts) {
      const lastRun = h.last_seen
        ? new Date(h.last_seen).toISOString().replace("T", " ").slice(0, 19) + " UTC"
        : "—";
      process.stdout.write(
        col(h.host, W.host) + "  " +
        col(h.total, W.calls) + "  " +
        col(h.bytes > 0 ? h.bytes.toLocaleString() : "—", W.bytes) + "  " +
        col(lastRun, W.last) + "\n"
      );
    }
    process.stdout.write(`${div}\n`);
    const totalCalls = hosts.reduce((a, h) => a + h.total, 0);
    process.stdout.write(`${hosts.length} host(s)  |  ${totalCalls} total call(s) observed locally\n`);
  }

  process.stdout.write(
    `\n  Free (this output)  — local run history, this machine, only processes started with \`vantio run\`\n` +
    `  Pro                 — remote dashboard sync, cross-machine discovery, governance enforcement\n` +
    `  Enterprise          — kernel-level shadow AI detection (catches unenrolled processes via eBPF)\n` +
    `  Upgrade at vantio.ai/pricing\n\n`
  );
}

// ── discover ─────────────────────────────────────────────────────────────────

// Render a human-readable discovery table from the /api/v1/discover response.
// Actual shape (see apps' /api/v1/discover route — the source of truth this
// must match field-for-field):
//   { since, generated_at, summary: { total_calls, governed_calls,
//     shadow_ai_calls, blocked_calls, redacted_calls },
//     hosts: [{ host, total, allowed, redacted, blocked, observed,
//       first_seen, last_seen }] }
function renderDiscoveryTable(data, since) {
  const hosts = Array.isArray(data?.hosts) ? data.hosts : null;

  if (!hosts || hosts.length === 0) {
    process.stdout.write(`No AI agent calls recorded in the last ${since}.\n`);
    return;
  }

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

  for (const h of hosts) {
    // A host is a Shadow AI indicator when it has any OBSERVED calls — traffic
    // seen by the network interceptor with no SDK-side policy trace attached.
    const isShadow = Number(h.observed) > 0;

    const lastSeen = h.last_seen
      ? new Date(h.last_seen).toISOString().replace("T", " ").slice(0, 19) + " UTC"
      : "—";

    const row =
      col(h.host ?? "unknown", W.host) + "  " +
      col(h.total ?? "—", W.calls) + "  " +
      col(h.allowed  ?? "—", W.allowed)  + "  " +
      col(h.redacted ?? "—", W.redacted) + "  " +
      col(h.blocked  ?? "—", W.blocked)  + "  " +
      col(h.observed ?? "—", W.observed) + "  " +
      col(isShadow ? "⚠ YES" : "no", W.shadow)  + "  " +
      col(lastSeen, W.last);

    process.stdout.write(`${row}\n`);
  }

  process.stdout.write(`${divider}\n`);
  process.stdout.write(`${hosts.length} host(s) shown`);

  const shadowCount = Number(data?.summary?.shadow_ai_calls) || 0;
  if (shadowCount > 0) {
    process.stdout.write(
      `  |  ⚠  ${shadowCount} Shadow AI call(s) detected — unenrolled processes calling LLM endpoints.\n` +
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
      local: { type: "boolean", default: false },
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

  // --local: read local run logs only — no API key required.
  if (values.local) {
    await discoverLocalCommand(values.since);
    return;
  }

  const cfg    = readConfig();
  const apiKey = process.env.VANTIO_API_KEY || cfg?.apiKey;
  if (!apiKey) {
    process.stdout.write("Run `vantio login` first to connect your workspace.\n");
    process.stdout.write("  Tip: `vantio discover --local` shows local run history without a key.\n");
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

  if (res.status === 403) {
    process.stdout.write(
      '[ ∅ VANTIO ] Discovery requires a Pro or Enterprise plan.\n' +
      '  Upgrade at vantio.ai/pricing\n' +
      '  Tip: `vantio discover --local` shows local run history on your Free plan.\n'
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

// ── inspect helpers (search / tail / diff) ────────────────────────────────────

function loadRunLog(path, cmd) {
  try {
    const log = JSON.parse(readFileSync(path, "utf8"));
    if (log?.vantio_run_log !== "1") {
      process.stderr.write(`vantio ${cmd}: not a Vantio run log: ${path}\n`);
      process.exit(1);
    }
    return log;
  } catch (err) {
    process.stderr.write(`vantio ${cmd}: could not read log: ${err.message}\n`);
    process.exit(1);
  }
}

function tryLoadRunLog(path) {
  try {
    const log = JSON.parse(readFileSync(path, "utf8"));
    if (log?.vantio_run_log !== "1") return null;
    return log;
  } catch {
    return null;
  }
}

function resolveRunPath(dir, runPrefix, cmd) {
  if (runPrefix) return findRunByPrefix(dir, runPrefix, cmd);
  const newest = findMostRecentRun(dir);
  if (!newest) {
    process.stdout.write(
      "No local run logs found. Wrap an agent first:\n" +
      "  vantio run node agent.js\n\n" +
      "Then inspect with:\n" +
      "  vantio search <query>\n" +
      "  vantio tail\n" +
      "  vantio diff <run-a> <run-b>\n"
    );
    process.exit(0);
  }
  return newest;
}

function listValidRunEntries(dir, sinceMs = null) {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch { return []; }
  const cutoff = sinceMs != null ? Date.now() - sinceMs : null;
  const out = [];
  for (const f of files) {
    const p = join(dir, f);
    try {
      const log = JSON.parse(readFileSync(p, "utf8"));
      if (log?.vantio_run_log !== "1") continue;
      if (cutoff != null) {
        const t = log.generated_at ? new Date(log.generated_at).getTime()
          : (log.started_at ? new Date(log.started_at).getTime() : 0);
        if (!t || t < cutoff) continue;
      }
      out.push({ path: p, log });
    } catch { /* skip bad files */ }
  }
  return out.sort((a, b) => {
    const ta = a.log.generated_at ? new Date(a.log.generated_at).getTime() : 0;
    const tb = b.log.generated_at ? new Date(b.log.generated_at).getTime() : 0;
    return tb - ta;
  });
}

function callSearchBlob(call, traceId) {
  return [
    traceId || "",
    call.hostname || "",
    call.provider || "",
    call.method || "",
    call.path || "",
    call.action || "",
    call.error || "",
    call.error_class || "",
  ].join(" ").toLowerCase();
}

// Column widths shared by the header and every row so a call with a missing
// timestamp or a long action label (DRY_RUN_BLOCKED_SPEND) still lines up.
const CALL_COLS = { ts: 24, host: 28, action: 22, route: 36, bytes: 10 };

function formatCallLine(call, traceId) {
  const host = call.hostname || "—";
  const action = (call.action || "OBSERVED").toUpperCase();
  const method = call.method || "";
  const path = call.path || "";
  const route = [method, path].filter(Boolean).join(" ") || "—";
  const bytes = call.bytes != null ? Number(call.bytes).toLocaleString() : "—";
  const ts = call.ts || "—";
  // Trace ID is printed in full: it is what you paste into `vantio prove --run=`
  // or `vantio diff`, so truncating it would make the row unusable.
  const tid = traceId ? String(traceId) : "—";
  return `${col(ts, CALL_COLS.ts)}  ${col(host, CALL_COLS.host)}  ${col(action, CALL_COLS.action)}  ` +
    `${col(route, CALL_COLS.route)}  ${col(bytes, CALL_COLS.bytes)}  ${tid}`;
}

function printCallHeader() {
  const hdr =
    col("TIMESTAMP", CALL_COLS.ts) + "  " +
    col("HOST", CALL_COLS.host) + "  " +
    col("ACTION", CALL_COLS.action) + "  " +
    col("METHOD / PATH", CALL_COLS.route) + "  " +
    col("BYTES", CALL_COLS.bytes) + "  TRACE ID";
  process.stdout.write(`${hdr}\n${"-".repeat(hdr.length)}\n`);
}

async function searchCommand(args) {
  const { values, positionals } = parseArgs({
    args,
    options: {
      host:     { type: "string" },
      provider: { type: "string" },
      action:   { type: "string" },
      run:      { type: "string" },
      since:    { type: "string" },
      json:     { type: "boolean", default: false },
      help:     { type: "boolean", short: "h", default: false },
    },
    allowPositionals: true,
  });

  if (values.help) { process.stdout.write(SEARCH_HELP); return; }

  const query = (positionals[0] || "").trim().toLowerCase();
  if (!query && !values.host && !values.provider && !values.action && !values.run) {
    process.stderr.write("vantio search: provide a query or a filter (--host, --provider, --action, --run)\n\n");
    process.stdout.write(SEARCH_HELP);
    process.exit(1);
  }

  if (values.since && !["24h", "7d", "30d"].includes(values.since)) {
    process.stderr.write("vantio search: invalid --since value. Use 24h, 7d, or 30d.\n");
    process.exit(1);
  }

  const dir = runsDir();
  let entries;
  if (values.run) {
    const path = findRunByPrefix(dir, values.run, "search");
    entries = [{ path, log: loadRunLog(path, "search") }];
  } else {
    const sinceMs = values.since ? parseSincePeriod(values.since) : null;
    entries = listValidRunEntries(dir, sinceMs);
  }

  if (entries.length === 0) {
    process.stdout.write(
      "No local run logs found. Wrap an agent first:\n" +
      "  vantio run node agent.js\n"
    );
    return;
  }

  const hostF = (values.host || "").toLowerCase();
  const providerF = (values.provider || "").toLowerCase();
  const actionF = (values.action || "").toLowerCase();
  const hits = [];

  for (const { log } of entries) {
    const calls = Array.isArray(log.calls) ? log.calls : [];
    for (let i = 0; i < calls.length; i++) {
      const call = calls[i];
      if (hostF && !(call.hostname || "").toLowerCase().includes(hostF)) continue;
      if (providerF && !(call.provider || "").toLowerCase().includes(providerF)) continue;
      if (actionF && !(call.action || "").toLowerCase().includes(actionF)) continue;
      if (query && !callSearchBlob(call, log.trace_id).includes(query)) continue;
      hits.push({
        trace_id: log.trace_id || null,
        index: i + 1,
        hostname: call.hostname || null,
        provider: call.provider || null,
        method: call.method || null,
        path: call.path || null,
        action: call.action || "OBSERVED",
        bytes: call.bytes ?? null,
        ts: call.ts || null,
        status: call.status ?? null,
      });
    }
  }

  if (values.json) {
    process.stdout.write(JSON.stringify({ query: query || null, matches: hits.length, calls: hits }, null, 2) + "\n");
    return;
  }

  if (hits.length === 0) {
    process.stdout.write("No matching calls in local run logs.\n");
    return;
  }

  process.stdout.write(`\nSearch results — ${hits.length} call(s)\n\n`);
  printCallHeader();
  for (const h of hits) {
    process.stdout.write(formatCallLine(h, h.trace_id) + "\n");
  }
  process.stdout.write(`\n${hits.length} match(es). Export a full report with \`vantio prove --run=<trace-id>\`.\n`);
}

function readCallsFromLog(log) {
  return Array.isArray(log.calls) ? log.calls : [];
}

function printTailCalls(log, lines, asJson) {
  const calls = readCallsFromLog(log);
  const slice = lines > 0 ? calls.slice(-lines) : calls;
  if (asJson) {
    process.stdout.write(JSON.stringify({
      trace_id: log.trace_id || null,
      total_calls: calls.length,
      shown: slice.length,
      calls: slice,
    }, null, 2) + "\n");
    return slice.length;
  }
  process.stdout.write(
    `\nTail — trace ${log.trace_id || "—"} · showing ${slice.length} of ${calls.length} call(s)\n\n`
  );
  if (slice.length === 0) {
    process.stdout.write("No calls recorded in this run log.\n");
    return 0;
  }
  printCallHeader();
  for (const c of slice) process.stdout.write(formatCallLine(c, log.trace_id) + "\n");
  process.stdout.write("\n");
  return slice.length;
}

async function tailCommand(args) {
  const { values } = parseArgs({
    args,
    options: {
      run:     { type: "string" },
      lines:   { type: "string", short: "n", default: "20" },
      follow:  { type: "boolean", short: "f", default: false },
      json:    { type: "boolean", default: false },
      help:    { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) { process.stdout.write(TAIL_HELP); return; }

  const n = Number.parseInt(values.lines, 10);
  if (!Number.isFinite(n) || n < 0) {
    process.stderr.write("vantio tail: --lines must be a non-negative integer\n");
    process.exit(1);
  }

  const dir = runsDir();
  const logPath = resolveRunPath(dir, values.run, "tail");
  let log = loadRunLog(logPath, "tail");
  if (!values.run) {
    process.stderr.write(`[ ∅ VANTIO ] Tailing most recent run: ${log.trace_id || logPath}\n`);
  }

  printTailCalls(log, n, values.json);

  if (!values.follow) return;

  if (values.json) {
    process.stderr.write("vantio tail: --follow writes human lines; omit --json to follow.\n");
  }

  process.stderr.write("[ ∅ VANTIO ] Following run log (Ctrl+C to stop)…\n");
  let lastCount = readCallsFromLog(log).length;

  const refresh = () => {
    const next = tryLoadRunLog(logPath);
    if (!next) return;
    const calls = readCallsFromLog(next);
    if (calls.length > lastCount) {
      const fresh = calls.slice(lastCount);
      for (const c of fresh) process.stdout.write(formatCallLine(c, next.trace_id) + "\n");
      lastCount = calls.length;
    }
    log = next;
  };

  try {
    const watcher = watch(logPath, { persistent: true }, () => refresh());
    await new Promise((resolve) => {
      const stop = () => { try { watcher.close(); } catch { /* */ } resolve(); };
      process.on("SIGINT", stop);
      process.on("SIGTERM", stop);
    });
  } catch (err) {
    process.stderr.write(`vantio tail: cannot follow: ${err.message}\n`);
    process.exit(1);
  }
}

function hostRollup(log) {
  const by = log.summary?.by_host && typeof log.summary.by_host === "object"
    ? log.summary.by_host
    : null;
  if (by) {
    const out = {};
    for (const [host, info] of Object.entries(by)) {
      out[host] = {
        calls: Number(info?.calls) || 0,
        bytes: Number(info?.bytes) || 0,
      };
    }
    return out;
  }
  const out = {};
  for (const call of readCallsFromLog(log)) {
    const h = call.hostname || "unknown";
    out[h] = out[h] || { calls: 0, bytes: 0 };
    out[h].calls += 1;
    out[h].bytes += call.bytes || 0;
  }
  return out;
}

function runTotals(log) {
  const calls = readCallsFromLog(log);
  return {
    trace_id: log.trace_id || null,
    started_at: log.started_at || null,
    generated_at: log.generated_at || null,
    total_calls: log.summary?.total_calls ?? calls.length,
    total_bytes: log.summary?.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0),
    hosts: hostRollup(log),
  };
}

async function diffCommand(args) {
  const { values, positionals } = parseArgs({
    args,
    options: {
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: true,
  });

  if (values.help) { process.stdout.write(DIFF_HELP); return; }

  if (positionals.length < 2) {
    process.stderr.write("vantio diff: need two run IDs — vantio diff <run-a> <run-b>\n\n");
    process.stdout.write(DIFF_HELP);
    process.exit(1);
  }

  const dir = runsDir();
  const pathA = findRunByPrefix(dir, positionals[0], "diff");
  const pathB = findRunByPrefix(dir, positionals[1], "diff");
  const a = runTotals(loadRunLog(pathA, "diff"));
  const b = runTotals(loadRunLog(pathB, "diff"));

  const hostsA = new Set(Object.keys(a.hosts));
  const hostsB = new Set(Object.keys(b.hosts));
  const added = [...hostsB].filter((h) => !hostsA.has(h)).sort();
  const removed = [...hostsA].filter((h) => !hostsB.has(h)).sort();
  const shared = [...hostsA].filter((h) => hostsB.has(h)).sort();
  const changed = shared
    .map((h) => ({
      host: h,
      calls_a: a.hosts[h].calls,
      calls_b: b.hosts[h].calls,
      bytes_a: a.hosts[h].bytes,
      bytes_b: b.hosts[h].bytes,
      delta_calls: b.hosts[h].calls - a.hosts[h].calls,
      delta_bytes: b.hosts[h].bytes - a.hosts[h].bytes,
    }))
    .filter((row) => row.delta_calls !== 0 || row.delta_bytes !== 0);

  const result = {
    a: { trace_id: a.trace_id, total_calls: a.total_calls, total_bytes: a.total_bytes, started_at: a.started_at },
    b: { trace_id: b.trace_id, total_calls: b.total_calls, total_bytes: b.total_bytes, started_at: b.started_at },
    delta_calls: b.total_calls - a.total_calls,
    delta_bytes: b.total_bytes - a.total_bytes,
    hosts_added: added,
    hosts_removed: removed,
    hosts_changed: changed,
  };

  if (values.json) {
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    return;
  }

  process.stdout.write("\nRun diff (Optics · observe only)\n\n");
  process.stdout.write(`  A  ${a.trace_id || "—"}  ·  ${a.total_calls} call(s)  ·  ${(a.total_bytes || 0).toLocaleString()} bytes\n`);
  process.stdout.write(`  B  ${b.trace_id || "—"}  ·  ${b.total_calls} call(s)  ·  ${(b.total_bytes || 0).toLocaleString()} bytes\n`);
  process.stdout.write(`  Δ  calls ${result.delta_calls >= 0 ? "+" : ""}${result.delta_calls}  ·  bytes ${result.delta_bytes >= 0 ? "+" : ""}${result.delta_bytes.toLocaleString()}\n\n`);

  if (added.length) {
    process.stdout.write(`Hosts only in B (${added.length}):\n`);
    for (const h of added) process.stdout.write(`  + ${h}  (${b.hosts[h].calls} call(s))\n`);
    process.stdout.write("\n");
  }
  if (removed.length) {
    process.stdout.write(`Hosts only in A (${removed.length}):\n`);
    for (const h of removed) process.stdout.write(`  - ${h}  (${a.hosts[h].calls} call(s))\n`);
    process.stdout.write("\n");
  }
  if (changed.length) {
    process.stdout.write(`Hosts changed (${changed.length}):\n`);
    for (const row of changed) {
      process.stdout.write(
        `  ~ ${row.host}  calls ${row.calls_a}→${row.calls_b} (${row.delta_calls >= 0 ? "+" : ""}${row.delta_calls})` +
        `  bytes ${row.bytes_a.toLocaleString()}→${row.bytes_b.toLocaleString()}\n`
      );
    }
    process.stdout.write("\n");
  }
  if (!added.length && !removed.length && !changed.length) {
    process.stdout.write("No host-level differences between these two runs.\n\n");
  }
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
  case "prove":
    await proveCommand(rest);
    break;
  case "search":
    await searchCommand(rest);
    break;
  case "tail":
    await tailCommand(rest);
    break;
  case "diff":
    await diffCommand(rest);
    break;
  default:
    process.stderr.write(`vantio: unknown command '${command}'\n\n${USAGE}`);
    process.exit(1);
}
