#!/usr/bin/env node
import { spawn } from "node:child_process";
import { parseArgs } from "node:util";

const USAGE = `\
Vantio AI — process supervisor

Usage:
  vantio run [--audit] <program> [...args]

Commands:
  run    Spawn <program> under the Vantio execution context.

Flags:
  --audit, -a   Enable audit mode. Injects VANTIO_AUDIT_MODE=1 into the
                child process environment.

Examples:
  vantio run node agent.js
  vantio run --audit node agent.js --model gpt-4o
`;

// ── argument intake ──────────────────────────────────────────────────────────

const [command, ...rest] = process.argv.slice(2);

if (!command || command === "--help" || command === "-h") {
  process.stdout.write(USAGE);
  process.exit(0);
}

if (command !== "run") {
  process.stderr.write(
    `vantio: unknown command '${command}'\n\n${USAGE}`,
  );
  process.exit(1);
}

// ── parse flags + positionals after 'run' ────────────────────────────────────

const { values, positionals } = parseArgs({
  args: rest,
  options: {
    audit: { type: "boolean", short: "a", default: false },
  },
  allowPositionals: true,
  // strict: true (default) — unknown flags will throw with a clear message
});

if (positionals.length === 0) {
  process.stderr.write(
    "vantio run: no program specified\n\nUsage: vantio run [--audit] <program> [...args]\n",
  );
  process.exit(1);
}

// ── build child environment ───────────────────────────────────────────────────

const [program, ...programArgs] = positionals;

const childEnv = Object.assign(
  Object.create(null),
  process.env,
  values.audit ? { VANTIO_AUDIT_MODE: "1" } : {},
);

// ── spawn ─────────────────────────────────────────────────────────────────────

const child = spawn(program, programArgs, {
  stdio: "inherit",
  env: childEnv,
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
    // Re-raise the signal on the parent so the OS records the correct cause.
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
