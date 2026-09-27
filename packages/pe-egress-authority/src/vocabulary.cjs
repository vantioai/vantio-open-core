"use strict";

// Closed result vocabulary for the Phantom Engine egress program.
// These names are the authority's disposition. They are not Optics display
// tokens and they are not Phantom protection states.

const RESULT_LIST = Object.freeze([
  "ALLOWED",
  "DENIED",
  "REDACTED",
  "CONTAINED",
  "REVOKED",
  "UNSUPPORTED",
  "ENFORCEMENT_GAP",
  "EVIDENCE_UNAVAILABLE",
  "UNKNOWN",
]);

const RESULT_SET = new Set(RESULT_LIST);

const DIMENSIONS = Object.freeze([
  "destination",
  "protocol_port",
  "http_method_path",
  "direct_socket",
  "redirect",
  "retry",
  "dns",
  "tls",
  "descendant",
  "credential",
  "sensitive",
  "payload_size",
  "resource",
  "spend",
  "pattern",
  "bypass",
  "path_support",
]);

const VOCABULARY_ID = "PE_EGRESS_V1";
const AUDIENCE = "INTERNAL_RESTRICTED";

const PATTERN_KINDS = Object.freeze([
  "scanner",
  "proxy",
  "relay",
  "callback",
  "exfil",
]);

const BYPASS_KINDS = Object.freeze([
  "cleared_node_options",
  "raw_syscall",
  "unwrapped_binary",
  "alternate_runtime",
  "browser",
]);

const CHILD_TOOLS = Object.freeze(["curl", "wget", "httpie", "aria2c"]);

module.exports = {
  AUDIENCE,
  BYPASS_KINDS,
  CHILD_TOOLS,
  DIMENSIONS,
  PATTERN_KINDS,
  RESULT_LIST,
  RESULT_SET,
  VOCABULARY_ID,
};
