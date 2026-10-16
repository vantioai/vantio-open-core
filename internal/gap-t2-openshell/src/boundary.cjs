"use strict";

// INTERNAL_RESTRICTED. Lab-only snapshot join. Not shipped. Not Phantom Engine.

const AUDIENCE = "INTERNAL_RESTRICTED";
const LABEL = "LAB_ONLY";
const LIVE_STACK = "ROADMAP";
const RUN_SCHEMA = "vantio.internal.openshell_reconciliation.run.v1";
const RESULT_SCHEMA = "vantio.internal.openshell_reconciliation.result.v1";
const EVIDENCE_SCHEMA = "vantio.internal.openshell_reconciliation.evidence.v1";

const MAX_RECORDS = 4096;
const MAX_LINE_BYTES = 65536;
const MAX_STRING = 65536;
const MAX_DEPTH = 16;
const MAX_KEYS = 64;
const MAX_BINDINGS = 64;
const MAX_ID = 128;
const MAX_PATH = 4096;
const MAX_HOST = 253;
const MIN_UNIX_MS = 1700000000000;
const MAX_UNIX_MS = 4102444800000;
const MAX_WINDOW_MS = 60000;

const INDICATORS = Object.freeze([
  "BYPASS_INDICATOR",
  "RECONCILED_OK",
  "UNATTRIBUTED",
  "OUT_OF_SCOPE",
]);

const REASON_CODES = Object.freeze([
  "AMBIGUOUS_BINDING",
  "CORRUPT_LINE",
  "LIMIT_EXCEEDED",
  "SECRET_FIELD",
  "CONVERSATION_FIELD",
  "SCHEMA",
  "KERNEL_RECORD",
  "OPENSHELL_RECORD",
  "GATE_RECORD",
]);

const FINDING_REASONS = Object.freeze([
  "no_matching_openshell_or_gate_record",
  "matched_openshell",
  "matched_gate",
  "matched_both",
  "missing_action_class",
  "missing_subject",
  "kernel_time_not_unix",
  "out_of_scope_host",
  "out_of_scope_cgroup",
]);

const SECRET_KEYS = Object.freeze([
  "authorization",
  "api_key",
  "apikey",
  "token",
  "secret",
  "password",
  "credential",
  "credentials",
  "bearer",
  "access_key",
  "private_key",
  "client_secret",
]);

const CONVERSATION_KEYS = Object.freeze([
  "prompt",
  "prompts",
  "completion",
  "completions",
  "messages",
  "tool_arguments",
  "input_text",
  "output_text",
]);

const POSTURE = Object.freeze([
  "INTERNAL_RESTRICTED",
  "LAB_ONLY",
  "ROADMAP_LIVE_STACK",
  "OBSERVE_ONLY",
  "NOT_SHIPPED",
  "NO_NETWORK",
  "NO_EBPF",
]);

function assertListed(value, allowed, label) {
  for (const entry of allowed) {
    if (entry === value) {
      return value;
    }
  }
  throw new Error(`unhandled ${label}`);
}

module.exports = {
  AUDIENCE,
  CONVERSATION_KEYS,
  EVIDENCE_SCHEMA,
  FINDING_REASONS,
  INDICATORS,
  LABEL,
  LIVE_STACK,
  MAX_BINDINGS,
  MAX_DEPTH,
  MAX_HOST,
  MAX_ID,
  MAX_KEYS,
  MAX_LINE_BYTES,
  MAX_PATH,
  MAX_RECORDS,
  MAX_STRING,
  MAX_UNIX_MS,
  MAX_WINDOW_MS,
  MIN_UNIX_MS,
  POSTURE,
  REASON_CODES,
  RESULT_SCHEMA,
  RUN_SCHEMA,
  SECRET_KEYS,
  assertListed,
};
