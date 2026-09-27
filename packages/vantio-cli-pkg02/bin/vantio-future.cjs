#!/usr/bin/env node
"use strict";

const { spawn } = require("node:child_process");
const { randomUUID } = require("node:crypto");
const path = require("node:path");

const boundary = require("../src/boundary.cjs");

const INTERCEPTOR = path.join(__dirname, "../../vantio-cli/bin/interceptor.cjs");
const PRELOAD = path.join(__dirname, "../src/preload.cjs");

function quote(value) {
  return /\s/.test(value) ? `"${value}"` : value;
}

function isNodeProgram(program) {
  const base = path.basename(program).replace(/\.exe$/, "").toLowerCase();
  return base === "node" || base === "npx" || base === "tsx" || base === "ts-node";
}

const argv = process.argv.slice(2);
if (argv[0] !== "run" || argv.length < 3 || !isNodeProgram(argv[1])) {
  process.stderr.write("vantio-pkg02 run <node program> [...args]\n");
  process.exit(1);
}

const program = argv[1];
const programArgs = argv.slice(2);
const trace = process.env.VANTIO_TRACE_ID || `0x${randomUUID().replace(/-/g, "").slice(0, 16)}`;
const writer = process.env.VANTIO_PKG02_WRITER === "0" ? "0" : "1";
const requireOpt = `--require ${quote(PRELOAD)} --require ${quote(INTERCEPTOR)}`;
const nodeOptions = [process.env.NODE_OPTIONS, requireOpt].filter(Boolean).join(" ");
const childEnv = Object.assign({}, process.env, {
  NODE_OPTIONS: nodeOptions,
  VANTIO_PKG02_WRITER: writer,
  VANTIO_TRACE_ID: trace,
});

process.stderr.write(
  `[ vantio-pkg02 ] version=${boundary.FUTURE_CLI_VERSION} writer=${writer} trace_id=${trace}\n`,
);

const child = spawn(program, programArgs, {
  env: childEnv,
  shell: false,
  stdio: "inherit",
});

child.on("error", () => {
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code == null ? 1 : code);
});
