#!/usr/bin/env node
import { spawn }                 from "node:child_process";
import { parseArgs }             from "node:util";
import { fileURLToPath }         from "node:url";
import { dirname, join }         from "node:path";

const USAGE = `\
Vantio AI — process supervisor

Usage:
  vantio run [--audit] <program> [...args]

Commands:
  run    Spawn <program> under the Vantio execution context.

Flags:
  --audit, -a   Enable audit mode. Injects VANTIO_AUDIT_MODE=1 into the
                child process environment.

Auto-interception:
  When VANTIO_API_KEY and VANTIO_INGEST_URL are set in your environment,
  vantio run automatically patches globalThis.fetch inside any Node.js
  process to capture outbound LLM API calls — zero code changes required.

  Supported: node, npx, tsx, ts-node
  Other runtimes (python, ruby, etc.) are spawned normally without injection.

Examples:
  vantio run node agent.js
  vantio run --audit node agent.js --model gpt-4o
  vantio run tsx agent.ts
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

// ── parse flags + positionals after 'run' ────────────────────────────────────

const { values, positionals } = parseArgs({
  args: rest,
  options: {
    audit: { type: "boolean", short: "a", default: false },
  },
  allowPositionals: true,
});

if (positionals.length === 0) {
  process.stderr.write(
    "vantio run: no program specified\n\nUsage: vantio run [--audit] <program> [...args]\n",
  );
  process.exit(1);
}

// ── resolve program and args ─────────────────────────────────────────────────

const [program, ...programArgs] = positionals;

// ── Node.js runtime detection for zero-line auto-interception ────────────────
// We inject the interceptor ONLY when the spawned process is a Node.js
// runtime. Python, Ruby, etc. are spawned normally — no panics, no errors.

const NODE_RUNTIMES = new Set(["node", "node.exe", "npx", "npx.cmd", "tsx", "ts-node"]);

function isNodeRuntime(prog) {
  const base = prog.split(/[\\/]/).pop().replace(/\.exe$/, "");
  return NODE_RUNTIMES.has(base);
}

let finalArgs = programArgs;

if (
  isNodeRuntime(program) &&
  process.env.VANTIO_API_KEY &&
  process.env.VANTIO_INGEST_URL
) {
  // Inject the CJS interceptor via --require before the user's script.
  // --require works with CommonJS modules in all Node.js 18+ environments.
  const interceptorPath = join(
    dirname(fileURLToPath(import.meta.url)),
    "interceptor.cjs",
  );
  finalArgs = ["--require", interceptorPath, ...programArgs];
}

// ── build child environment ───────────────────────────────────────────────────

const childEnv = Object.assign(
  Object.create(null),
  process.env,
  values.audit ? { VANTIO_AUDIT_MODE: "1" } : {},
);

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

// Propagate the child's exit code or termination signal to the parent so that
// upstream process managers (systemd, Docker, CI runners) observe the correct
// status without any wrapping ambiguity.
child.on("exit", (code, signal) => {
  if (signal !== null) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
