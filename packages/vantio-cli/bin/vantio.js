#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import { parseArgs }     from "node:util";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { homedir } from "node:os";
import { mkdirSync, readFileSync, writeFileSync, rmSync, readdirSync, statSync, existsSync, watch } from "node:fs";
import { randomUUID }    from "node:crypto";

const require = createRequire(import.meta.url);
const {
  SCHEMA_STATUS,
  VOCABULARY,
  PROVIDER_SDKS,
  humanStatus,
  displayCall,
  rollupCalls,
  telemetryPosture,
  withSchema,
} = require("./optics-cx.cjs");

const USAGE = `\
Vantio Optics | Free Observability for AI Agents

Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.

Usage:
  vantio run [flags] <prog>   Spawn <prog> under the Vantio execution context
  vantio demo                 In-process demo of one observed call (no network)
  vantio status               Local install and data status (no network by default)
  vantio discover [options]   Show AI-agent call history (--local; no key required)
  vantio prove [options]      Generate a proof artifact from a local run log (no key required)
  vantio search [query]       Search local run logs (host, path, action, free text)
  vantio tail [options]       Show the latest calls from a captured run
  vantio diff <a> <b>         Compare two local runs (hosts, counts, bytes)

Flags (run):
  --summary, -s   Print a run summary on exit.
  --json          Unstable JSON on stdout when the program exits.

--json output includes "schema_status": "unstable-pre-1.0" and may change without notice.

Examples:
  vantio run node agent.js
  vantio run python agent.py
  vantio run --summary tsx agent.ts
  vantio demo
  vantio status
  vantio discover --local
  vantio discover --since=7d
  vantio prove
  vantio prove --list
  vantio prove --format=md --out=report.md
  vantio search openai
  vantio tail -n 20
  vantio tail -n 0
  vantio tail --all
  vantio diff 0xabc 0xdef
`;

const DISCOVER_HELP = `\
vantio discover — local AI-agent call history

Reads run logs on this machine. Covers only processes started with
\`vantio run\` (Node) or \`vantio run python\` after
\`pip install vantio-agent-sdk\`. This machine only — not a fleet inventory.

Calls are grouped by target host. The action label recorded for a local
Optics run is OBSERVED.

Usage:
  vantio discover [options]

Options:
  --since=<period>    Look back 24h, 7d, or 30d  (default: 24h)
  --host=<hostname>   Filter to a specific target host
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  --local             Same local history (accepted; this command is always local)
  -h, --help          Show this help

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.

Examples:
  vantio discover
  vantio discover --local
  vantio discover --local --since=7d
  vantio discover --since=7d
  vantio discover --host=api.openai.com
`;

const PROVE_HELP = `\
vantio prove — local proof artifacts

Generates a local proof artifact (HTML or Markdown report) from a
vantio run log. Reports include: trace ID, PID, byte counts, host
breakdown, and summary counts. Prompts and completions are never stored.

Run logs are written automatically to ~/.vantio/runs/ when LLM calls are
intercepted by \`vantio run\`.

Usage:
  vantio prove [options]

Options:
  --list              List available local run logs
  --run=<trace-id>    Generate a report for a specific run (by trace ID or prefix)
  --from=<file>       Generate a report from an explicit log file path
  --format=html|md    Output format (default: html)
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  --out=<file>        Write output to a file (default: vantio-proof-<id>.html)
  -h, --help          Show this help

Examples:
  vantio prove                               → most recent run, HTML to file
  vantio prove --list                        → list available runs
  vantio prove --run=0x1a2b3c4d             → specific run by trace ID
  vantio prove --format=md                   → Markdown to stdout
  vantio prove --format=html --out=proof.html

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.
`;

const SEARCH_HELP = `\
vantio search — Search local Optics run logs

Find observed LLM calls across ~/.vantio/runs/ by free text, host, provider,
path, or action. Metadata only — prompts and completions are never stored.

Usage:
  vantio search [query] [options]

Options:
  --host=<hostname>   Filter to a target host (substring match)
  --provider=<name>   Filter by provider label (substring match)
  --action=<label>    Filter by stored action (e.g. OBSERVED)
  --run=<trace-id>    Limit to one run (trace ID or prefix)
  --since=24h|7d|30d  Only runs newer than this window (default: all)
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help          Show this help

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.

Examples:
  vantio search openai
  vantio search --host=api.anthropic.com
  vantio search chat --action=OBSERVED --since=7d
  vantio search --run=0x1a2b3c4d --json
`;

const TAIL_HELP = `\
vantio tail — Latest calls from a captured Optics run

Prints the most recent observed calls from a local run log. Metadata only —
prompts and completions are never stored.

Usage:
  vantio tail [options]

Options:
  --run=<trace-id>    Run to read (default: most recent local run)
  -n, --lines=<n>     Number of calls to show (default: 20). 0 shows zero calls.
  --all               Show every call in the run
  -f, --follow        Keep watching the run log for new calls
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help          Show this help

--json and --follow cannot be combined.
--all and --lines cannot be combined.

A run log is written when the wrapped agent exits, so --follow stays quiet
during a run that is still going and prints the calls once it finishes.

Examples:
  vantio tail
  vantio tail -n 50
  vantio tail --run=0x1a2b3c4d
  vantio tail -f

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.
`;

const DIFF_HELP = `\
vantio diff — Compare two local Optics runs

Shows what changed between two captured runs: hosts added or removed, call
counts, and byte totals. Metadata only. Prompts and completions are never stored.

Usage:
  vantio diff <run-a> <run-b> [options]

Arguments:
  <run-a> <run-b>     Trace IDs or prefixes of two local run logs

Options:
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help          Show this help

Exit status: 0 completed, including an empty result. 1 bad arguments, or a file that exists but cannot be read or parsed.

Examples:
  vantio diff 0xabc123 0xdef456
  vantio diff 0xabc 0xdef --json
`;

const DEMO_HELP = `\
vantio demo — in-process Optics demo

Simulates one POST /v1/chat/completions that returns HTTP 200.
No network. No prompt or completion is created or stored.
Duration is fixed at 0 ms.

Usage:
  vantio demo [options]

Options:
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help          Show this help

Examples:
  vantio demo
  vantio demo --json
`;

const STATUS_HELP = `\
vantio status — local Optics status

Reports the installed CLI version, telemetry posture, local data size,
whether a run has been recorded, and which supported provider SDKs can
be resolved from the current directory. This command does not contact
the network unless --check-registry is set.

Usage:
  vantio status [options]

Options:
  --check-registry    Ask the npm registry for the latest @vantio/cli version
  --json              Unstable JSON (schema_status unstable-pre-1.0; may change without notice)
  -h, --help          Show this help

Examples:
  vantio status
  vantio status --json
  vantio status --check-registry
`;

// ── config store (~/.vantio/config.json) ───────────────────────────────────────────────────
function configDir()  { return join(homedir(), ".vantio"); }
function configPath() { return join(configDir(), "config.json"); }

// Compatibility: ~/.vantio/config.json is not read by run,
// discover, prove, search, tail, or diff. A previously saved apiKey is never
// injected, printed, or sent. `vantio logout` only deletes that local file.
function clearConfig() {
  try { rmSync(configPath()); return true; } catch { return false; }
}

function getVersion() {
  try {
    const pkgPath = join(dirname(fileURLToPath(import.meta.url)), "..", "package.json");
    return JSON.parse(readFileSync(pkgPath, "utf8")).version || "unknown";
  } catch {
    return "unknown";
  }
}

// ── commands ──────────────────────────────────────────────────────────────────────────────

function parseArgsSafe(command, config) {
  try {
    return parseArgs(config);
  } catch (err) {
    const detail = err && err.message ? String(err.message).split("\n")[0] : "invalid arguments";
    process.stderr.write(`vantio ${command}: ${detail}\n`);
    process.exit(1);
  }
}

function runCommand(rest) {
  // Split at the first non-flag argument (the program name) so flags meant for
  // the child (e.g. node -e) are never consumed by vantio's own parser.
  const splitAt  = rest.findIndex((a) => !a.startsWith("-"));
  const ourArgs  = splitAt === -1 ? rest : rest.slice(0, splitAt);
  const progArgs = splitAt === -1 ? []   : rest.slice(splitAt);

  const { values } = parseArgsSafe("run", {
    args: ourArgs,
    options: {
      audit:   { type: "boolean", short: "a", default: false },
      summary: { type: "boolean", short: "s", default: false },
      json:    { type: "boolean", default: false },
    },
    allowPositionals: false,
  });

  if (progArgs.length === 0) {
    process.stderr.write(
      "vantio run: no program specified\n\nUsage: vantio run [--summary] [--json] <program> [...args]\n",
    );
    process.exit(1);
  }

  const [program, ...programArgs] = progArgs;

  // ── Node.js runtime detection ──────────────────────────────────────────────────────────
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

  // Stored ~/.vantio/config.json is ignored. The CLI does not inject a
  // saved key or ingest URL. An explicit environment variable already present
  // on the parent is inherited with the rest of process.env.
  const mergedNodeOptions = [process.env.NODE_OPTIONS, extraNodeOptions].filter(Boolean).join(" ");
  const delim = process.platform === "win32" ? ";" : ":";
  const mergedPythonPath = extraPythonPath
    ? [extraPythonPath, process.env.PYTHONPATH].filter(Boolean).join(delim)
    : "";

  // One stable trace id for this `vantio run`.
  const runTraceId = process.env.VANTIO_TRACE_ID || `0x${randomUUID().replace(/-/g, "").slice(0, 16)}`;

  const childEnv = Object.assign(Object.create(null), process.env, {
    VANTIO_TRACE_ID: runTraceId,
    ...(values.audit     ? { VANTIO_AUDIT_MODE: "1" } : {}),
    ...(values.summary   ? { VANTIO_SUMMARY:    "1" } : {}),
    ...(values.json      ? { VANTIO_JSON:       "1" } : {}),
    ...(extraNodeOptions ? { NODE_OPTIONS: mergedNodeOptions } : {}),
    ...(mergedPythonPath ? { PYTHONPATH: mergedPythonPath } : {}),
  });

  function writeRunJson(exitCode, signal) {
    if (!values.json) return;
    process.stdout.write(JSON.stringify(withSchema({
      command: "run",
      trace_id: runTraceId,
      exit_code: exitCode,
      signal: signal || null,
      opticsStatus: signal ? "OPTICS_ERROR" : "SUCCESS",
      applicationStatus: "NOT_OBSERVED",
    })) + "\n");
  }

  process.stderr.write(`[ ∅ VANTIO ] run trace_id=${runTraceId}\n`);

  const child = spawn(program, programArgs, { stdio: "inherit", env: childEnv, shell: false });

  child.on("error", (err) => {
    process.stderr.write(`vantio: failed to start '${program}': ${err.message}\n`);
    writeRunJson(1, null);
    process.exit(1);
  });

  child.on("exit", (code, signal) => {
    if (signal !== null) {
      writeRunJson(null, signal);
      process.kill(process.pid, signal);
      return;
    }
    const exitCode = code ?? 1;
    writeRunJson(exitCode, null);
    process.exit(exitCode);
  });
}

// Hidden local compatibility. Not listed in help, README, or usage errors.
// Deletes ~/.vantio/config.json only. Does not read or print the file and
// does not contact the network.
function logoutCommand() {
  clearConfig();
  process.stdout.write(
    "Vantio Optics | Free Observability for AI Agents\n" +
    "Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.\n",
  );
}

// ── shared formatting helpers ─────────────────────────────────────────────────────────────────────────

// Pad a string to a fixed width, truncating with '…' if needed.
function col(str, width) {
  const s = String(str ?? "");
  if (s.length > width) return s.slice(0, width - 1) + "…";
  return s.padEnd(width);
}

// ── prove helpers ─────────────────────────────────────────────────────────────────────────────
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
  const rollup     = rollupCalls(calls);
  const traceId    = escHtml(log.trace_id    || "—");
  const pid        = escHtml(log.pid         || "—");
  const startedAt  = escHtml(log.started_at  || "—");
  const genAt      = escHtml(log.generated_at || new Date().toISOString());
  const durationMs = log.duration_ms != null ? `${Number(log.duration_ms).toLocaleString()} ms` : "—";
  const cliVer     = escHtml(log.cli_version || "—");

  const rows = calls.map((c, i) => {
    const view = displayCall(c);
    const http = view.httpStatus != null ? String(view.httpStatus) : "—";
    return `        <tr>
          <td class="num">${i + 1}</td>
          <td class="mono">${escHtml(view.hostname || "—")}</td>
          <td>${escHtml(view.opticsLabel)}</td>
          <td>${escHtml(view.applicationLabel)}</td>
          <td class="num">${escHtml(http)}</td>
          <td class="num">${view.bytes != null ? Number(view.bytes).toLocaleString() : "—"}</td>
          <td class="mono">${escHtml(view.ts || "—")}</td>
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
    .footer { margin-top: 40px; border-top: 1px solid #eee; padding-top: 16px; color: #aaa; font-size: .76rem; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
    .footer a { color: #aaa; }
    @media (max-width: 640px) { .page { padding: 24px 20px; } .metrics { grid-template-columns: repeat(2, 1fr); } }
  </style>
</head>
<body>
  <div class="page">
    <h1>Vantio Optics | Free Observability for AI Agents</h1>
    <p class="subtitle">Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.</p>

    <div class="privacy-banner">
      ✓ <strong>Prompts and completions are never stored.</strong>
      This report contains hostnames, byte counts, process IDs, trace IDs, Optics status, and Application outcome. CLI v${cliVer}.
    </div>

    <h2>Run identity</h2>
    <dl class="meta">
      <dt>Trace ID</dt>     <dd>${traceId}</dd>
      <dt>Run started</dt>  <dd>${startedAt}</dd>
      <dt>Generated</dt>    <dd>${genAt}</dd>
      <dt>Duration</dt>     <dd>${durationMs}</dd>
      <dt>Process ID</dt>   <dd>${pid}</dd>
      <dt>CLI version</dt>  <dd>@vantio/cli v${cliVer}</dd>
    </dl>

    <h2>Summary</h2>
    <div class="metrics">
      <div class="metric"><div class="metric-value">${totalCalls.toLocaleString()}</div><div class="metric-label">Total calls</div></div>
      <div class="metric"><div class="metric-value">${totalBytes > 0 ? formatBytes(totalBytes) : "—"}</div><div class="metric-label">Total bytes</div></div>
      <div class="metric"><div class="metric-value">${hosts.length}</div><div class="metric-label">Unique hosts</div></div>
      <div class="metric"><div class="metric-value">${escHtml(humanStatus(rollup.opticsStatus))}</div><div class="metric-label">Optics status</div></div>
      <div class="metric"><div class="metric-value">${escHtml(humanStatus(rollup.applicationStatus))}</div><div class="metric-label">Application outcome</div></div>
    </div>

    <h2>Call log (${totalCalls.toLocaleString()} call${totalCalls === 1 ? "" : "s"})</h2>
    ${calls.length === 0
      ? "<p style=\"color:#888;font-size:.875rem\">No calls recorded in this run log.</p>"
      : `<table>
      <thead><tr>
        <th class=\"num\">#</th><th>Host</th><th>Optics status</th>
        <th>Application outcome</th><th class=\"num\">HTTP</th><th class=\"num\">Bytes</th><th>Timestamp</th>
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

function proofJson(log) {
  const calls = Array.isArray(log.calls) ? log.calls : [];
  const rollup = rollupCalls(calls);
  return withSchema({
    command: "prove",
    trace_id: log.trace_id || null,
    pid: log.pid || null,
    started_at: log.started_at || null,
    generated_at: log.generated_at || null,
    duration_ms: log.duration_ms ?? null,
    cli_version: log.cli_version || null,
    opticsStatus: rollup.opticsStatus,
    applicationStatus: rollup.applicationStatus,
    summary: {
      total_calls: log.summary?.total_calls ?? calls.length,
      total_bytes: log.summary?.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0),
      opticsStatus: rollup.opticsStatus,
      applicationStatus: rollup.applicationStatus,
    },
    calls: calls.map((call, index) => Object.assign({ index: index + 1 }, publicCall(call))),
  });
}

function publicCall(call) {
  const view = displayCall(call);
  return {
    hostname: view.hostname,
    provider: view.provider,
    method: view.method,
    path: view.path,
    bytes: view.bytes,
    ts: view.ts,
    httpStatus: view.httpStatus,
    opticsStatus: view.opticsStatus,
    applicationStatus: view.applicationStatus,
  };
}

function generateMarkdownReport(log) {
  const calls      = Array.isArray(log.calls) ? log.calls : [];
  const summary    = log.summary || {};
  const totalCalls = summary.total_calls ?? calls.length;
  const totalBytes = summary.total_bytes ?? calls.reduce((a, c) => a + (c.bytes || 0), 0);
  const hosts      = Array.isArray(summary.hosts) ? summary.hosts
                     : [...new Set(calls.map((c) => c.hostname || "?"))];
  const rollup     = rollupCalls(calls);

  const rows = calls.map((c, i) => {
    const view = displayCall(c);
    const http = view.httpStatus != null ? view.httpStatus : "—";
    return `| ${i + 1} | \`${view.hostname || "—"}\` | ${view.opticsLabel} | ${view.applicationLabel} | ${http} | ${view.bytes != null ? Number(view.bytes).toLocaleString() : "—"} | \`${view.ts || "—"}\` |`;
  }).join("\n");

  return `# Vantio Optics | Free Observability for AI Agents

> Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.

**Privacy notice:** This report contains hostnames, byte counts, process IDs,
trace IDs, Optics status, and Application outcome. Prompts and completions are never stored.
CLI v${log.cli_version || "—"}.

---

## Run identity

| Field | Value |
|-------|-------|
| Trace ID | \`${log.trace_id || "—"}\` |
| Run started | \`${log.started_at || "—"}\` |
| Generated | \`${log.generated_at || new Date().toISOString()}\` |
| Duration | \`${log.duration_ms != null ? `${Number(log.duration_ms).toLocaleString()} ms` : "—"}\` |
| Process ID | \`${log.pid || "—"}\` |
| CLI version | \`@vantio/cli v${log.cli_version || "—"}\` |

---

## Summary

| Metric | Value |
|--------|-------|
| Total calls | **${totalCalls.toLocaleString()}** |
| Total bytes | ${totalBytes > 0 ? totalBytes.toLocaleString() : "—"} |
| Unique hosts | ${hosts.length} |
| Optics status | ${humanStatus(rollup.opticsStatus)} |
| Application outcome | ${humanStatus(rollup.applicationStatus)} |

Hosts: ${hosts.map((h) => `\`${h}\``).join(", ") || "—"}

---

## Call log (${totalCalls} call${totalCalls === 1 ? "" : "s"})

| # | Host | Optics status | Application outcome | HTTP | Bytes | Timestamp |
|---|------|---------------|---------------------|------|-------|-----------|
${rows || "| — | — | — | — | — | — | — |"}

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
          const loaded = readJsonFile(join(dir, f));
          if (loaded.unreadable || loaded.corrupt) failUnreadable("prove", join(dir, f), loaded.error);
          const log = loaded.json;
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

  process.stdout.write(`\nLocal run logs (~/.vantio/runs):\n\n`);
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
    return { path: null, empty: true };
  }
  const norm = prefix.replace(/[^a-zA-Z0-9_-]/g, "_");
  const matches = files.filter((f) => f.includes(norm));
  if (matches.length === 0) return { path: null, empty: true };
  if (matches.length > 1) {
    process.stderr.write(`vantio ${cmd}: '${prefix}' matches ${matches.length} runs. Use a longer prefix:\n`);
    for (const f of matches) process.stderr.write(`  ${f.replace(/\.json$/, "")}\n`);
    process.exit(1);
  }
  return { path: join(dir, matches[0]), empty: false };
}

function readJsonFile(path) {
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch (err) {
    return { unreadable: true, error: err };
  }
  try {
    return { json: JSON.parse(text) };
  } catch (err) {
    return { corrupt: true, error: err };
  }
}

function failUnreadable(cmd, path, err) {
  const detail = err && err.message ? String(err.message).split("\n")[0] : "could not read the file";
  process.stderr.write(`vantio ${cmd}: could not read ${path}: ${detail}\n`);
  process.exit(1);
}

function findMostRecentRun(dir) {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch { return null; }
  if (files.length === 0) return null;
  let newest = null, newestTime = 0;
  for (const f of files) {
    const p = join(dir, f);
    try {
      // Prefer the JSON's generated_at timestamp for stable ordering (mtime can
      // be the same when fixtures are written in quick succession in tests).
      let t = 0;
      try {
        const log = JSON.parse(readFileSync(p, "utf8"));
        if (log?.generated_at) t = new Date(log.generated_at).getTime();
        else if (log?.started_at) t = new Date(log.started_at).getTime();
      } catch { /* fall through to mtime */ }
      if (!t) t = statSync(p).mtimeMs;
      if (t > newestTime) { newestTime = t; newest = p; }
    } catch { /* skip */ }
  }
  return newest;
}

async function proveCommand(args) {
  const { values } = parseArgsSafe("prove", {
    args,
    options: {
      list:   { type: "boolean", default: false },
      run:    { type: "string" },
      from:   { type: "string" },
      format: { type: "string",  default: "html" },
      json:   { type: "boolean", default: false },
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
    const found = findRunByPrefix(dir, values.run, "prove");
    if (!found.path) {
      process.stdout.write(`No run log matched '${values.run}'.\nNext: vantio prove --list\n`);
      return;
    }
    logPath = found.path;
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
    process.stderr.write(`[ ∅ VANTIO ] Using most recent run log: ~/.vantio/runs/${logPath.split(/[\\/]/).pop()}\n`);
  }

  const loaded = readJsonFile(logPath);
  if (loaded.unreadable || loaded.corrupt) failUnreadable("prove", logPath, loaded.error);
  const log = loaded.json;
  if (!log || typeof log !== "object" || Array.isArray(log)) {
    process.stderr.write(`vantio prove: could not read log: not a JSON object\n`);
    process.exit(1);
  }

  const formatGiven = args.some((a) => a === "--format" || a.startsWith("--format="));
  if (values.json && formatGiven) {
    process.stderr.write("vantio prove: use either --json or --format, not both\n");
    process.exit(1);
  }

  const format = (values.format || "html").toLowerCase();
  if (!values.json && format !== "html" && format !== "md") {
    process.stderr.write(`vantio prove: invalid format '${format}'. Use html or md.\n`);
    process.exit(1);
  }

  const report = values.json
    ? JSON.stringify(proofJson(log), null, 2) + "\n"
    : (format === "html" ? generateHtmlReport(log) : generateMarkdownReport(log));

  function writeProof(outPath) {
    try {
      writeFileSync(outPath, report, "utf8");
    } catch (err) {
      const detail = err && err.message ? String(err.message).split("\n")[0] : "could not write the proof";
      process.stderr.write(`vantio prove: could not write ${outPath}: ${detail}\n`);
      process.exit(1);
    }
    process.stdout.write(`✓ Proof artifact written to: ${outPath}\n`);
  }

  if (values.out) {
    writeProof(values.out);
  } else if (!values.json && format === "html") {
    const safeid = (log.trace_id || "unknown").replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 40);
    writeProof(`vantio-proof-${safeid}.html`);
  } else {
    process.stdout.write(report);
  }
}

// ── discover (local run history) ─────────────────────────────────────────────
// discover reads ~/.vantio/runs only. It does not contact the
// network and it does not read stored account config or environment secrets.

function discoverLocalCommand(since, hostFilter, asJson) {
  const cutoff = Date.now() - parseSincePeriod(since);

  let files = [];
  try { files = readdirSync(runsDir()).filter((f) => f.endsWith(".json")); } catch { /* dir missing */ }

  const hostMap = new Map();
  let scannedRuns = 0;
  const hostNeedle = hostFilter ? String(hostFilter).toLowerCase() : "";
  for (const f of files) {
    const filePath = join(runsDir(), f);
    try {
      const s = statSync(filePath);
      if (s.mtimeMs < cutoff) continue;
      const loaded = readJsonFile(filePath);
      if (loaded.unreadable || loaded.corrupt) failUnreadable("discover", filePath, loaded.error);
      const log = loaded.json;
      if (log?.vantio_run_log !== "1" || !Array.isArray(log.calls)) continue;
      scannedRuns++;
      const ts = log.generated_at ? new Date(log.generated_at).getTime() : 0;
      for (const call of log.calls) {
        const h = call.hostname || "unknown";
        if (hostNeedle && !h.toLowerCase().includes(hostNeedle)) continue;
        const rec = hostMap.get(h) || { host: h, total: 0, bytes: 0, last_seen: null };
        rec.total++;
        rec.bytes += call.bytes || 0;
        if (!rec.last_seen || ts > rec.last_seen) rec.last_seen = ts;
        hostMap.set(h, rec);
      }
    } catch { /* skip corrupt files */ }
  }

  const hosts = [...hostMap.values()].sort((a, b) => (b.last_seen || 0) - (a.last_seen || 0));
  if (asJson) {
    process.stdout.write(JSON.stringify(withSchema({
      command: "discover",
      since,
      scanned_runs: scannedRuns,
      opticsStatus: hosts.length ? "SUCCESS" : "NOT_OBSERVED",
      applicationStatus: hosts.length ? "SUCCESS" : "NOT_OBSERVED",
      hosts: hosts.map((h) => ({
        host: h.host,
        total: h.total,
        bytes: h.bytes,
        last_seen: h.last_seen ? new Date(h.last_seen).toISOString() : null,
      })),
    }), null, 2) + "\n");
    return;
  }

  process.stdout.write(`\nVantio Optics — local run history (last ${since})\n`);
  process.stdout.write(`  Scanned ${scannedRuns} run log(s) from ~/.vantio/runs\n`);

  if (hosts.length === 0) {
    if (scannedRuns === 0) {
      process.stdout.write(`\nNo run logs found for the last ${since}.\n`);
      process.stdout.write(`  Run an agent:  vantio run node agent.js\n`);
      process.stdout.write(`  Then re-run:   vantio discover\n`);
    } else {
      process.stdout.write(`\nNo LLM calls recorded in the last ${since} (${scannedRuns} run log(s) scanned, zero calls).\n`);
      process.stdout.write(`  Check that your agent is actually making LLM API calls.\n`);
    }
    process.stdout.write("Next: vantio run node agent.js\n");
    return;
  }

  const W = { host: 32, calls: 7, bytes: 14, last: 24 };
  const hdr = col("TARGET HOST", W.host) + "  " + col("CALLS", W.calls) + "  " + col("TOTAL BYTES", W.bytes) + "  " + col("LAST RUN", W.last);
  const div = "-".repeat(hdr.length);
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
  process.stdout.write("Next: vantio search <query>\n\n");
}

async function discoverCommand(args) {
  const { values } = parseArgsSafe("discover", {
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

  discoverLocalCommand(values.since, values.host, values.json);
}

// ── inspect helpers (search / tail / diff) ───────────────────────────────────────────────────

function loadRunLog(path, cmd) {
  const loaded = readJsonFile(path);
  if (loaded.unreadable || loaded.corrupt) failUnreadable(cmd, path, loaded.error);
  const log = loaded.json;
  if (log?.vantio_run_log !== "1") {
    process.stderr.write(`vantio ${cmd}: not a Vantio run log: ${path}\n`);
    process.exit(1);
  }
  return log;
}

function tryLoadRunLog(path) {
  const loaded = readJsonFile(path);
  if (loaded.unreadable || loaded.corrupt || loaded.json?.vantio_run_log !== "1") return null;
  return loaded.json;
}

function resolveRunPath(dir, runPrefix, cmd) {
  if (runPrefix) return findRunByPrefix(dir, runPrefix, cmd);
  const newest = findMostRecentRun(dir);
  if (!newest) return { path: null, empty: true };
  return { path: newest, empty: false };
}

function listValidRunEntries(dir, sinceMs = null) {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); } catch { return []; }
  const cutoff = sinceMs != null ? Date.now() - sinceMs : null;
  const out = [];
  for (const f of files) {
    const p = join(dir, f);
    try {
      const loaded = readJsonFile(p);
      if (loaded.unreadable || loaded.corrupt) failUnreadable("search", p, loaded.error);
      const log = loaded.json;
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

// Column widths shared by the header and every row. Trace ID is never truncated.
const CALL_COLS = { ts: 24, host: 28, optics: 16, outcome: 18, route: 36, bytes: 10 };

function formatCallLine(call, traceId) {
  const view = displayCall(call);
  const host = view.hostname || "—";
  const method = view.method || "";
  const path = view.path || "";
  const route = [method, path].filter(Boolean).join(" ") || "—";
  const bytes = view.bytes != null ? Number(view.bytes).toLocaleString() : "—";
  const ts = view.ts || "—";
  const tid = traceId ? String(traceId) : "—";
  return `${col(ts, CALL_COLS.ts)}  ${col(host, CALL_COLS.host)}  ${col(view.opticsLabel, CALL_COLS.optics)}  ` +
    `${col(view.applicationLabel, CALL_COLS.outcome)}  ${col(route, CALL_COLS.route)}  ${col(bytes, CALL_COLS.bytes)}  ${tid}`;
}

function printCallHeader() {
  const hdr =
    col("TIMESTAMP", CALL_COLS.ts) + "  " +
    col("HOST", CALL_COLS.host) + "  " +
    col("OPTICS STATUS", CALL_COLS.optics) + "  " +
    col("APP OUTCOME", CALL_COLS.outcome) + "  " +
    col("METHOD / PATH", CALL_COLS.route) + "  " +
    col("BYTES", CALL_COLS.bytes) + "  TRACE ID";
  process.stdout.write(`${hdr}\n${"-".repeat(hdr.length)}\n`);
}

async function searchCommand(args) {
  const { values, positionals } = parseArgsSafe("search", {
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
    const found = findRunByPrefix(dir, values.run, "search");
    if (!found.path) {
      process.stdout.write(`No run log matched '${values.run}'.\nNext: vantio prove --list\n`);
      return;
    }
    entries = [{ path: found.path, log: loadRunLog(found.path, "search") }];
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
      hits.push(Object.assign({
        trace_id: log.trace_id || null,
        index: i + 1,
      }, publicCall(call)));
    }
  }

  if (values.json) {
    process.stdout.write(JSON.stringify(withSchema({
      command: "search",
      query: query || null,
      matches: hits.length,
      opticsStatus: hits.length ? "SUCCESS" : "NOT_OBSERVED",
      applicationStatus: rollupCalls(hits.map((hit) => ({ status: hit.httpStatus }))).applicationStatus,
      calls: hits,
    }), null, 2) + "\n");
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
  process.stdout.write(`\n${hits.length} match(es).\nNext: vantio prove --run=<trace-id>\n`);
}

function readCallsFromLog(log) {
  return Array.isArray(log.calls) ? log.calls : [];
}

function printTailCalls(log, lines, asJson, showAll) {
  const calls = readCallsFromLog(log);
  const slice = showAll ? calls : (lines === 0 ? [] : calls.slice(-lines));
  if (asJson) {
    const shown = slice.map((call) => publicCall(call));
    process.stdout.write(JSON.stringify(withSchema({
      command: "tail",
      trace_id: log.trace_id || null,
      total_calls: calls.length,
      shown: shown.length,
      opticsStatus: rollupCalls(slice).opticsStatus,
      applicationStatus: rollupCalls(slice).applicationStatus,
      calls: shown,
    }), null, 2) + "\n");
    return shown.length;
  }
  process.stdout.write(
    `\nTail — trace ${log.trace_id || "—"} · showing ${slice.length} of ${calls.length} call(s)\n\n`
  );
  if (slice.length === 0) {
    if (calls.length === 0) process.stdout.write("No calls recorded in this run log.\n");
    process.stdout.write(`Next: vantio prove --run=${log.trace_id || ""}\n`);
    return 0;
  }
  printCallHeader();
  for (const c of slice) process.stdout.write(formatCallLine(c, log.trace_id) + "\n");
  process.stdout.write(`\nNext: vantio prove --run=${log.trace_id || ""}\n`);
  return slice.length;
}

async function tailCommand(args) {
  const { values } = parseArgsSafe("tail", {
    args,
    options: {
      run:     { type: "string" },
      lines:   { type: "string", short: "n", default: "20" },
      all:     { type: "boolean", default: false },
      follow:  { type: "boolean", short: "f", default: false },
      json:    { type: "boolean", default: false },
      help:    { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });

  if (values.help) { process.stdout.write(TAIL_HELP); return; }

  if (values.json && values.follow) {
    process.stderr.write("vantio tail: --json and --follow cannot be used together\n");
    process.exit(1);
  }

  const linesGiven = args.some((arg) => arg === "-n" || arg === "--lines" || arg.startsWith("--lines=") || /^-n\d/.test(arg));
  if (values.all && linesGiven) {
    process.stderr.write("vantio tail: use either --all or --lines, not both\n");
    process.exit(1);
  }

  const n = Number.parseInt(values.lines, 10);
  if (!values.all && (!Number.isFinite(n) || n < 0)) {
    process.stderr.write("vantio tail: --lines must be a non-negative integer\n");
    process.exit(1);
  }

  const dir = runsDir();
  const found = resolveRunPath(dir, values.run, "tail");
  if (!found.path) {
    const which = values.run ? `'${values.run}'` : "the local run directory";
    process.stdout.write(`No run log matched ${which}.\nNext: vantio run node agent.js\n`);
    return;
  }
  const logPath = found.path;
  let log = loadRunLog(logPath, "tail");
  if (!values.run) {
    process.stderr.write(`[ ∅ VANTIO ] Tailing most recent run: ${log.trace_id || "local run"}\n`);
  }

  printTailCalls(log, n, values.json, values.all);

  if (!values.follow) return;

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
  const { values, positionals } = parseArgsSafe("diff", {
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
  const foundA = findRunByPrefix(dir, positionals[0], "diff");
  const foundB = findRunByPrefix(dir, positionals[1], "diff");
  if (!foundA.path || !foundB.path) {
    const missing = [foundA.path ? null : positionals[0], foundB.path ? null : positionals[1]].filter(Boolean);
    process.stdout.write(`No run log matched ${missing.map((id) => `'${id}'`).join(" and ")}.\nNext: vantio prove --list\n`);
    return;
  }
  const a = runTotals(loadRunLog(foundA.path, "diff"));
  const b = runTotals(loadRunLog(foundB.path, "diff"));

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
    process.stdout.write(JSON.stringify(withSchema(Object.assign({ command: "diff" }, result)), null, 2) + "\n");
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
  process.stdout.write("Next: vantio prove --run=<trace-id>\n");
}

const DEMO_DURATION_MS = 0;

function demoCommand(args) {
  const { values } = parseArgsSafe("demo", {
    args,
    options: {
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (values.help) { process.stdout.write(DEMO_HELP); return; }

  const traceId = `0x${randomUUID().replace(/-/g, "").slice(0, 16)}`;
  const stamp = new Date().toISOString();
  const call = {
    hostname: "optics-demo.invalid",
    provider: "openai",
    method: "POST",
    path: "/v1/chat/completions",
    status: 200,
    bytes: 0,
    ts: stamp,
    action: "OBSERVED",
  };
  const log = {
    vantio_run_log: "1",
    schema_version: 2,
    plane: "optics",
    trace_id: traceId,
    started_at: stamp,
    generated_at: stamp,
    duration_ms: DEMO_DURATION_MS,
    cli_version: getVersion(),
    calls: [call],
    summary: {
      total_calls: 1,
      total_bytes: 0,
      hosts: [call.hostname],
    },
  };
  const dir = runsDir();
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const safeid = traceId.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 80);
  writeFileSync(join(dir, `${safeid}.json`), JSON.stringify(log, null, 2) + "\n", { mode: 0o600 });

  const view = displayCall(call);
  if (values.json) {
    process.stdout.write(JSON.stringify(withSchema({
      command: "demo",
      network: "none",
      trace_id: traceId,
      method: "POST",
      path: "/v1/chat/completions",
      httpStatus: 200,
      duration_ms: DEMO_DURATION_MS,
      opticsStatus: view.opticsStatus,
      applicationStatus: view.applicationStatus,
      content: null,
    }), null, 2) + "\n");
    return;
  }
  process.stdout.write(
    "Vantio Optics | Free Observability for AI Agents\n" +
    "Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.\n\n" +
    "Demo — in-process stub. No network.\n\n" +
    "  method: POST /v1/chat/completions\n" +
    "  http_status: 200\n" +
    `  Optics status: ${view.opticsLabel}\n` +
    `  Application outcome: ${view.applicationLabel}\n` +
    `  duration_ms: ${DEMO_DURATION_MS}\n` +
    `  trace_id: ${traceId}\n\n` +
    `Next: vantio prove --run=${traceId}\n`
  );
}

function directoryBytes(root) {
  let total = 0;
  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch (err) {
    if (err && err.code === "ENOENT") return { bytes: 0, missing: true };
    return { bytes: 0, unreadable: true };
  }
  for (const ent of entries) {
    if (ent.isSymbolicLink()) continue;
    const path = join(root, ent.name);
    if (ent.isDirectory()) {
      const sub = directoryBytes(path);
      if (sub.unreadable) return { bytes: total, unreadable: true };
      total += sub.bytes;
    } else if (ent.isFile()) {
      try { total += statSync(path).size; }
      catch { return { bytes: total, unreadable: true }; }
    }
  }
  return { bytes: total, missing: false };
}

function sdkRows() {
  let req = null;
  try { req = createRequire(join(process.cwd(), "package.json")); } catch { req = null; }
  return PROVIDER_SDKS.map((sdk) => {
    let importable = false;
    if (req) {
      try { req.resolve(sdk.spec); importable = true; }
      catch { importable = false; }
    }
    return {
      name: sdk.name,
      spec: sdk.spec,
      opticsStatus: importable ? "SUCCESS" : "UNSUPPORTED",
    };
  });
}

function firstRunScan(dir) {
  let files = [];
  try { files = readdirSync(dir).filter((f) => f.endsWith(".json")); }
  catch (err) {
    if (err && err.code === "ENOENT") {
      return { first_run_since_install: true, first_run_at: null, corrupt: false, runs: 0 };
    }
    return { first_run_since_install: true, first_run_at: null, corrupt: true, runs: 0 };
  }
  let earliest = null;
  let valid = 0;
  let corrupt = false;
  for (const file of files) {
    const loaded = readJsonFile(join(dir, file));
    if (loaded.unreadable || loaded.corrupt) { corrupt = true; continue; }
    const log = loaded.json;
    if (log?.vantio_run_log !== "1") continue;
    valid += 1;
    const stamp = log.started_at || log.generated_at || null;
    if (stamp && (!earliest || String(stamp) < earliest)) earliest = String(stamp);
  }
  return {
    first_run_since_install: valid === 0,
    first_run_at: earliest,
    corrupt,
    runs: valid,
  };
}

function lookupRegistryVersion() {
  const res = spawnSync("npm", ["view", "@vantio/cli", "version"], {
    encoding: "utf8",
    timeout: 8000,
    env: Object.assign({}, process.env, { npm_config_update_notifier: "false" }),
  });
  const version = res && res.stdout ? String(res.stdout).trim() : "";
  if (!res || res.status !== 0 || !version || /[\r\n]/.test(version)) {
    return { checked: true, version: null, opticsStatus: "UNAVAILABLE" };
  }
  return { checked: true, version, opticsStatus: "SUCCESS" };
}

function statusCommand(args) {
  const { values } = parseArgsSafe("status", {
    args,
    options: {
      "check-registry": { type: "boolean", default: false },
      json: { type: "boolean", default: false },
      help: { type: "boolean", short: "h", default: false },
    },
    allowPositionals: false,
  });
  if (values.help) { process.stdout.write(STATUS_HELP); return; }

  const version = getVersion();
  const dataDir = configDir();
  const size = directoryBytes(dataDir);
  const runs = firstRunScan(runsDir());
  const registry = values["check-registry"]
    ? lookupRegistryVersion()
    : { checked: false, version: null, opticsStatus: "NOT_OBSERVED" };
  const dataStatus = size.unreadable ? "OPTICS_ERROR" : (size.missing ? "NOT_OBSERVED" : "SUCCESS");
  const report = withSchema({
    command: "status",
    vocabulary: VOCABULARY,
    install: {
      version,
      opticsStatus: version && version !== "unknown" ? "SUCCESS" : "OPTICS_ERROR",
    },
    registry,
    telemetry: { posture: telemetryPosture(process.env), opticsStatus: "SUCCESS" },
    data: { bytes: size.bytes || 0, opticsStatus: dataStatus },
    first_run_since_install: runs.first_run_since_install,
    first_run_at: runs.first_run_at,
    runs: {
      count: runs.runs,
      opticsStatus: runs.corrupt ? "OPTICS_ERROR" : (runs.first_run_since_install ? "NOT_OBSERVED" : "SUCCESS"),
    },
    sdks: sdkRows(),
  });

  if (values.json) {
    process.stdout.write(JSON.stringify(report, null, 2) + "\n");
    return;
  }

  const registryLine = registry.checked
    ? (registry.version || humanStatus("UNAVAILABLE"))
    : "not checked";
  const sdkLines = report.sdks.map((sdk) => `  ${sdk.name}  ${humanStatus(sdk.opticsStatus)}`).join("\n");
  process.stdout.write(
    "Vantio Optics | Free Observability for AI Agents\n" +
    "Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.\n\n" +
    `Install version:             ${version}\n` +
    `Registry latest:             ${registryLine}\n` +
    `Telemetry:                   ${report.telemetry.posture}\n` +
    `Local data:                  ${report.data.bytes} bytes\n` +
    `First run since install:     ${report.first_run_since_install ? "yes" : "no"}\n` +
    `First run at:                ${report.first_run_at || "none"}\n` +
    `Run logs:                    ${humanStatus(report.runs.opticsStatus)}\n` +
    "Provider SDKs:\n" +
    `${sdkLines}\n\n` +
    "Next: vantio demo\n"
  );
}

// ── dispatch ────────────────────────────────────────────────────────────────────────────

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
  case "demo":
    demoCommand(rest);
    break;
  case "status":
    await statusCommand(rest);
    break;
  case "logout":
    logoutCommand();
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
