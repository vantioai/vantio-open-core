#!/usr/bin/env node
import { spawn }         from "node:child_process";
import { parseArgs }     from "node:util";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const USAGE = `\
Vantio AI — process supervisor

Usage:
  vantio run [flags] <program> [...args]

Commands:
  run    Spawn <program> under the Vantio execution context.

Flags:
  --audit,   -a   Enable audit mode (VANTIO_AUDIT_MODE=1).
  --summary, -s   Print a run summary on exit.

Auto-interception (Node.js only):
  Set VANTIO_API_KEY + VANTIO_INGEST_URL to enable cloud routing.
  Without a key, intercepted calls are printed to stderr (free tier).
  Python, Ruby, and other runtimes are spawned normally.

Examples:
  vantio run node agent.js
  vantio run --audit node agent.js
  vantio run --summary tsx agent.ts
`;

// ── argument intake ──────────────────────────────────────────────────────────

const [command, ...rest] = process.argv.slice(2);

if (!command || command === "--help" || command === "-h") {
  process.stdout.write(USAGE);
  process.exit(0);
}

if (command !== "run") {
  process.stderr.write(`vantio: unknown command '${command}'\n\n${USAGE}`);
  process.exit(1);
}

// ── parse flags + positionals ────────────────────────────────────────────────
// Split at the first non-flag argument (the program name) so that flags
// intended for the child process (e.g. node -e, python -c) are never
// consumed by vantio's own argument parser.

const splitAt = rest.findIndex((a) => !a.startsWith("-"));
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

// ── resolve program and args ─────────────────────────────────────────────────

const [program, ...programArgs] = progArgs;

// ── Node.js runtime detection ────────────────────────────────────────────────

const NODE_RUNTIMES = new Set(["node", "node.exe", "npx", "npx.cmd", "tsx", "ts-node"]);

function isNodeRuntime(prog) {
  const base = prog.split(/[\\/]/).pop().replace(/\.exe$/, "");
  return NODE_RUNTIMES.has(base);
}

let finalArgs = programArgs;

if (isNodeRuntime(program)) {
  const interceptorPath = join(
    dirname(fileURLToPath(import.meta.url)),
    "interceptor.cjs",
  );
  finalArgs = ["--require", interceptorPath, ...programArgs];
}

// ── build child environment ───────────────────────────────────────────────────

const childEnv = Object.assign(Object.create(null), process.env, {
  ...(values.audit   ? { VANTIO_AUDIT_MODE: "1" } : {}),
  ...(values.summary ? { VANTIO_SUMMARY:    "1" } : {}),
});

// ── spawn ─────────────────────────────────────────────────────────────────────

const child = spawn(program, finalArgs, {
  stdio: "inherit",
  env:   childEnv,
  shell: false,
});

child.on("error", (err) => {
  process.stderr.write(`vantio: failed to start '${program}': ${err.message}\n`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal !== null) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
