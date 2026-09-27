"use strict";

const { PLANES, sealChild } = require("../../pe-integrated-runtime/src/boundary.cjs");

const PRODUCER_CLASSIFICATION = "W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const AUDIENCE = "INTERNAL_RESTRICTED";
const STARTING_REF = "0cd36cf1d01c4db83a0a6999db0a322441f61c98";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const MODULE_VERSION = "0.0.0-unstable-pre-1.0";
const WAVE2_CLOSE = "ENTERPRISE_E1_E3_INTERNAL_MERGED_RECORD_LAYER_ONLY_NO_LIVE_CUSTOMER_AUTHORITY";
const PRODUCER_ID = "bc-adac3d0c-3395-5aeb-8a09-fad025b1aa95";
const PRODUCER_URL = "https://cursor.com/agents/bc-adac3d0c-3395-5aeb-8a09-fad025b1aa95";

const PREFERRED_EXECUTION = Object.freeze([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
]);

const REFUSED_REQUEST_KEYS = Object.freeze([
  "live_customer_authority",
  "customer_authority",
  "customer_deploy",
  "promote_record",
  "promote_to_customer",
  "host_attachment",
  "attach_host",
  "enroll",
  "enroll_host",
  "kernel_executed",
  "load_ebpf",
  "ebpf_loaded",
  "active_protection",
  "publish",
  "announce",
  "issue_credentials",
  "credentials_issued",
  "reopen_frozen",
  "frozen_cli_reopened",
  "reopen_cli",
  "reopen_python",
  "reopen_node",
  "mark_host_protected",
  "mark_host_enrolled",
  "mark_host_enforced",
  "proved_external",
  "clean_host_internal_proof",
  "enrolled",
  "protected",
  "enforced",
  "performed_here",
  "host_enrolled",
  "host_protected",
  "host_enforced",
  "applied_to_host",
  "mutate_loader",
]);

const CHILD_FALSE_KEYS = Object.freeze([
  "live_customer_authority",
  "host_contacted",
  "verified_on_host",
  "credential_created",
  "external_identity_created",
  "identity_authenticated",
  "satisfies_host_proof",
  "vantio_sufficient",
  "active_set_by_enterprise_writer",
  "host_enrolled",
  "host_protected",
  "host_enforced",
  "host_freeze_performed",
  "customer_authority_promoted",
  "published",
  "announced",
  "kernel_executed",
  "host_attachment",
  "active_protection",
  "ebpf_loaded",
  "applied_to_host",
  "customer_deployed",
  "credentials_issued",
  "frozen_version_reopened",
  "grant_minted",
]);

const POSTURE = Object.freeze({
  audience: AUDIENCE,
  producer_classification: PRODUCER_CLASSIFICATION,
  council_status: COUNCIL_STATUS,
  council_verdict: null,
  self_certified_council_pass: false,
  schema_status: SCHEMA_STATUS,
  schema_version: SCHEMA_VERSION,
  stable_schema: false,
  starting_ref: STARTING_REF,
  wave2_close: WAVE2_CLOSE,
  record_layer_only: true,
  live_customer_authority: false,
  customer_authority_promoted: false,
  published: false,
  announced: false,
  frozen_version_reopened: false,
  host_attachment: false,
  host_attachment_status: "HOST_ATTACHMENT_FALSE",
  ebpf_loaded: false,
  loader_mutated: false,
  kernel_executed: false,
  customer_deployed: false,
  stranger_host_executed: false,
  credentials_issued: false,
  clean_host_internal_proof: false,
  proved_external: false,
  frozen_cli_reopened: false,
  python_sdk_mutated: false,
  node_sdk_mutated: false,
  active_protection: false,
  decision_reported_as_enforcement: false,
  contract_reported_as_kernel_enforcement: false,
  unattached_mechanism_reported_as_active_protection: false,
  independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  preferred_execution: PREFERRED_EXECUTION,
});

const HONESTY_FIELDS = Object.freeze([
  "wave2_close",
  "record_layer_only",
  "live_customer_authority",
  "customer_authority_promoted",
  "published",
  "announced",
  "frozen_version_reopened",
  "host_attachment",
  "host_attachment_status",
  "ebpf_loaded",
  "loader_mutated",
  "kernel_executed",
  "customer_deployed",
  "stranger_host_executed",
  "credentials_issued",
  "clean_host_internal_proof",
  "proved_external",
  "frozen_cli_reopened",
  "python_sdk_mutated",
  "node_sdk_mutated",
  "active_protection",
  "decision_reported_as_enforcement",
  "contract_reported_as_kernel_enforcement",
  "unattached_mechanism_reported_as_active_protection",
  "independent_verification_status",
]);

const CITED_REQUIREMENTS = Object.freeze({
  "EG-E2-8": "RECORD_LAYER_ONLY_HOST_UNSATISFIED",
  "EG-E3-7": "RECORD_LAYER_ONLY_HOST_UNSATISFIED",
  "EG-E3-8": "HOST_UNSATISFIED",
  "EG-SUB-6": "HOST_UNSATISFIED",
});

function assertNever(value) {
  throw new Error("unhandled variant: " + String(value));
}

function keyHits(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  const found = [];
  for (const key of REFUSED_REQUEST_KEYS) {
    if (Object.prototype.hasOwnProperty.call(value, key) && value[key] !== false) found.push(key);
  }
  return found;
}

function promotionHits(request) {
  if (!request || typeof request !== "object") return [];
  const found = keyHits(request);
  if (request.input) found.push(...keyHits(request.input).map((key) => "input." + key));
  if (request.enterprise) found.push(...keyHits(request.enterprise).map((key) => "enterprise." + key));
  if (request.enterprise && request.enterprise.input) {
    found.push(...keyHits(request.enterprise.input).map((key) => "enterprise.input." + key));
  }
  if (request.pe) found.push(...keyHits(request.pe).map((key) => "pe." + key));
  if (request.pe && request.pe.input) found.push(...keyHits(request.pe.input).map((key) => "pe.input." + key));
  return found;
}

function sealEnterpriseChild(value) {
  if (!value || typeof value !== "object") return [];
  const problems = [];
  for (const key of CHILD_FALSE_KEYS) {
    if (value[key] === true) problems.push(key);
  }
  if (value.intent && typeof value.intent === "object") {
    if (value.intent.enrolled === true) problems.push("intent.enrolled");
    if (value.intent.protected === true) problems.push("intent.protected");
    if (value.intent.enforced === true) problems.push("intent.enforced");
    if (value.intent.performed_here === true) problems.push("intent.performed_here");
  }
  for (const problem of sealChild(value)) problems.push(problem);
  return problems;
}

module.exports = {
  AUDIENCE,
  CHILD_FALSE_KEYS,
  CITED_REQUIREMENTS,
  COUNCIL_STATUS,
  HONESTY_FIELDS,
  MODULE_VERSION,
  PLANES,
  POSTURE,
  PREFERRED_EXECUTION,
  PRODUCER_CLASSIFICATION,
  PRODUCER_ID,
  PRODUCER_URL,
  REFUSED_REQUEST_KEYS,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  STARTING_REF,
  WAVE2_CLOSE,
  assertNever,
  promotionHits,
  sealEnterpriseChild,
};
