"use strict";

const { spawnSync } = require("node:child_process");

function inheritTrace(parent) {
  const allow = parent.allow_cidr_v4.slice();
  if (!parent.trace_id) {
    return { trace_id: 0, allow_cidr_v4: allow, minted: false, widened: false };
  }
  return {
    trace_id: parent.trace_id,
    allow_cidr_v4: allow,
    minted: false,
    widened: false,
  };
}

function childWiden(parent, cidr) {
  const inherited = inheritTrace(parent);
  if (inherited.allow_cidr_v4.includes(cidr)) {
    return { ...inherited, disposition: "INHERIT_NO_WIDEN", added: false };
  }
  return {
    trace_id: inherited.trace_id,
    allow_cidr_v4: inherited.allow_cidr_v4.slice(),
    disposition: "REJECTED_NOT_AN_AUTHORITY_INPUT",
    mechanism_id: "no_child_delegation_object",
    added: false,
    widened: false,
  };
}

function proveLiveChild() {
  const script = [
    "process.stdout.write(JSON.stringify({",
    "pid:process.pid,",
    "ppid:process.ppid,",
    "trace:process.env.VANTIO_TRACE_ID==null?null:String(process.env.VANTIO_TRACE_ID),",
    "allow:process.env.VANTIO_ALLOW==null?null:String(process.env.VANTIO_ALLOW)",
    "}))",
  ].join("");
  const result = spawnSync(process.execPath, ["-e", script], {
    encoding: "utf8",
    env: { PATH: process.env.PATH || "/usr/bin" },
    timeout: 5000,
  });
  if (result.status !== 0) {
    throw new Error(`descendant process exited ${result.status}: ${result.stderr}`);
  }
  const parsed = JSON.parse(result.stdout);
  return {
    id: "descendants-live-child",
    surface: "descendants",
    disposition: parsed.ppid === process.pid && parsed.trace === null && parsed.allow === null
      ? "INHERIT_NO_WIDEN"
      : "NOT_COVERED",
    mechanism_id: "fork_trace_inherit",
    child_pid: parsed.pid,
    child_ppid: parsed.ppid,
    parent_pid: process.pid,
    child_trace_env: parsed.trace,
    child_allow_env: parsed.allow,
    kernel_executed: false,
    execution: "THIS_PROCESS",
    reason: "live_child_received_no_trace_and_no_allowlist",
  };
}

module.exports = {
  inheritTrace,
  childWiden,
  proveLiveChild,
};
