"use strict";

// PRIVATE future CLI line. Not @vantio/cli 0.3.24. Not published. Not a stable schema.

const AUDIENCE = "INTERNAL_RESTRICTED";
const FUTURE_CLI_VERSION = "0.4.0-pkg02-unit-d";
const FROZEN_CLI_VERSION = "0.3.24";
const PRODUCER = "node_interceptor";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const UNICODE_PROFILE_ID = "PKG01-UCD-16.0.0";
const UNICODE_PROFILE_VERSION = "16.0.0";
const LEGACY_SCHEMA_VERSION = 2;

const WRITER_OPTICS = new Set([
  "OBSERVED",
  "UNAVAILABLE",
  "NOT_OBSERVED",
  "OPTICS_ERROR",
]);

const PROHIBITED_KEYS = new Set([
  "anonymousId",
  "body",
  "completion",
  "completions",
  "cost",
  "data_note",
  "est_spend_usd",
  "free_mode",
  "freshness",
  "hostname",
  "machine",
  "message",
  "messages",
  "plane",
  "prompt",
  "prompts",
  "residual",
  "token_count",
  "usage",
  "widget_hint",
  "workflow",
]);

const ENFORCEMENT_ACTIONS = new Set([
  "ALLOWED",
  "BLOCKED",
  "BLOCKED_HOST",
  "BLOCKED_SIZE",
  "BLOCKED_SPEND",
  "DRY_RUN_BLOCKED_HOST",
  "DRY_RUN_BLOCKED_SIZE",
  "DRY_RUN_BLOCKED_SPEND",
  "REDACTED",
]);

module.exports = {
  AUDIENCE,
  ENFORCEMENT_ACTIONS,
  FUTURE_CLI_VERSION,
  FROZEN_CLI_VERSION,
  LEGACY_SCHEMA_VERSION,
  PROHIBITED_KEYS,
  PRODUCER,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  UNICODE_PROFILE_ID,
  UNICODE_PROFILE_VERSION,
  WRITER_OPTICS,
};
