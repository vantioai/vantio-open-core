"use strict";

const PRODUCER_CLASSIFICATION = "PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL";

const POSTURE = Object.freeze({
  audience: "INTERNAL_RESTRICTED",
  banner: "PRIVATE | INERT | NOT SHIPPED | NO HOST ATTACHMENT | NO AUTO-ENFORCE | NO STABLE SCHEMA",
  package_id: "PE-PROGRESSIVE-ENFORCEMENT",
  schema_status: "unstable-pre-1.0",
  schema_version: 0,
  stable_schema: false,
  producer_classification: PRODUCER_CLASSIFICATION,
  council_status: "PENDING_INDEPENDENT_COUNCIL",
  council_verdict: null,
  self_certified_council_pass: false,
  host_attachment: "NOT_PERFORMED",
  live_enforcement: false,
  auto_enforce_from_observation: false,
  customer_deploy: false,
  stranger_host_execution: false,
});

const STAGES = Object.freeze([
  "DISCOVER",
  "OBSERVE",
  "PROPOSE",
  "SIMULATE",
  "CANARY",
  "ENFORCE",
  "REVIEW",
  "REVOKE_OR_ROLLBACK",
  "RETIRE",
  "VERIFY_REMOVAL",
]);

const ROLLOUT_STEPS = Object.freeze(["NONE", "COHORT", "LIMITED", "BROADER"]);

const EFFECTS = Object.freeze(["DECLARED_HOST_MATCH", "DECLARED_BYTE_CAP"]);

const DECISION_CLASSES = Object.freeze([
  "OBSERVATION",
  "PROPOSAL",
  "SHADOW",
  "CANARY",
  "PROMOTED_MATCH",
  "FROZEN",
  "EXCEPTION",
  "ROLLED_BACK",
  "RETIRED",
  "REMOVED",
  "REFUSED",
]);

const EVIDENCE_KINDS = Object.freeze([
  "DISCOVER",
  "OBSERVATION",
  "PROPOSAL",
  "SIMULATION",
  "CANARY",
  "IMPACT",
  "PROMOTION",
  "ROLLOUT",
  "REVIEW",
  "FREEZE",
  "THAW",
  "EXCEPTION",
  "EXCEPTION_EXPIRY",
  "ROLLBACK",
  "RETIREMENT",
  "REMOVAL",
]);

const REJECTED_ACTORS = new Set([
  "auto",
  "automatic",
  "system",
  "observation",
  "ingest",
  "anonymous",
  "policy",
]);

const ID_PATTERN = /^[a-z0-9][a-z0-9._:-]{0,63}$/;
const HOST_PATTERN = /^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?)*$/;
const MAX_OBSERVATIONS = 1024;
const MAX_CORPUS = 500;
const MAX_COHORT = 20;
const MAX_LIMITED = 50;
const MAX_BROADER = 200;
const MAX_JSON_DEPTH = 8;

const DROPPED_KEYS = new Set([
  "prompt",
  "prompts",
  "completion",
  "completions",
  "messages",
  "message",
  "content",
  "body",
  "payload",
  "api_key",
  "apikey",
  "authorization",
  "password",
  "secret",
  "token",
  "credential",
  "credentials",
  "cookie",
  "raw",
  "text",
]);

const CONTROL_KEYS = new Set([
  "enforce",
  "auto",
  "automatic",
  "auto_promote",
  "promote",
  "stage",
  "rollout",
  "policy",
]);

module.exports = {
  CONTROL_KEYS,
  DECISION_CLASSES,
  DROPPED_KEYS,
  EFFECTS,
  EVIDENCE_KINDS,
  HOST_PATTERN,
  ID_PATTERN,
  MAX_BROADER,
  MAX_COHORT,
  MAX_CORPUS,
  MAX_JSON_DEPTH,
  MAX_LIMITED,
  MAX_OBSERVATIONS,
  POSTURE,
  PRODUCER_CLASSIFICATION,
  REJECTED_ACTORS,
  ROLLOUT_STEPS,
  STAGES,
};
