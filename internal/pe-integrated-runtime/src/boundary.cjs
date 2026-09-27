"use strict";

const PRODUCER_CLASSIFICATION = "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const AUDIENCE = "INTERNAL_RESTRICTED";
const STARTING_REF = "0620f10ee52d3abcea18c1c988df02f687f51b36";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;

const PLANES = Object.freeze([
  "OBSERVATION",
  "DECISION",
  "APPLICATION_ENFORCEMENT",
  "HOST_ENFORCEMENT",
  "CONTAINMENT",
  "REVOCATION",
  "EVIDENCE",
  "INDEPENDENT_VERIFICATION",
]);

const PLANE_SET = new Set(PLANES);

const PREFERRED_EXECUTION = Object.freeze([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
]);

const ALLOWED_EXECUTION = new Set([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
  "NOT_PERFORMED",
]);

const ALLOWED_HOST_ATTACHMENT = new Set(["NOT_PERFORMED", "HOST_ATTACHMENT_FALSE"]);

const HONESTY_TRUE_KEYS = Object.freeze([
  "kernel_executed",
  "host_attachment",
  "active_protection",
  "live_enforcement",
  "ebpf_loaded",
  "this_force_executed_host",
  "this_force_executed_network",
  "live_loader_mutated",
  "applied_to_host",
  "enforcement_attached",
  "customer_deployed",
  "proved",
  "green",
  "live_phantom_enforcement_changed",
  "clean_host_internal_proof",
  "proved_external",
  "loader_mutated",
  "authority_widened",
  "universal_linux",
  "ingress_protected_claim",
  "kernel_activated",
  "maps_changed",
  "cgroup_freeze_applied",
  "doctrine_present",
  "optimistic_allow",
  "reachability_is_authority",
  "credential_is_integrity",
  "auto_promoted",
  "stranger_host_executed",
  "credentials_issued",
  "announced",
  "applied",
]);

const REFUSED_REQUEST_KEYS = Object.freeze([
  "host_attachment",
  "kernel_executed",
  "ebpf_loaded",
  "load_ebpf",
  "attach_host",
  "active_protection",
  "customer_deploy",
  "enroll_host",
  "mutate_loader",
  "announce",
  "issue_credentials",
  "proved_external",
  "clean_host_internal_proof",
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
  host_attachment: false,
  host_attachment_status: "HOST_ATTACHMENT_FALSE",
  ebpf_loaded: false,
  loader_mutated: false,
  kernel_executed: false,
  customer_deployed: false,
  stranger_host_executed: false,
  credentials_issued: false,
  announced: false,
  clean_host_internal_proof: false,
  proved_external: false,
  frozen_cli_reopened: false,
  python_sdk_mutated: false,
  node_sdk_mutated: false,
  active_protection: false,
  decision_reported_as_enforcement: false,
  contract_reported_as_kernel_enforcement: false,
  unattached_mechanism_reported_as_active_protection: false,
  healthy_enforcing_reported_as_host_enforcement: false,
  blocked_host_reported_as_host_enforcement: false,
  enforce_stage_reported_as_host_enforcement: false,
  promoted_match_reported_as_host_enforcement: false,
  missing_evidence_collapsed_to_success: false,
  unknown_evidence_collapsed_to_success: false,
  unavailable_evidence_collapsed_to_success: false,
  optimistic_success: false,
  eligible_plane: "NONE",
  named_eligible_plane: false,
  infra_requirement: "W3-INFRA-REQ-1",
  execution_ceiling: "HOST_ATTACHMENT_FALSE",
  product_health_failure_truth: "W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL",
  independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  preferred_execution: PREFERRED_EXECUTION,
});

const HONESTY_FIELDS = Object.freeze([
  "host_attachment",
  "host_attachment_status",
  "ebpf_loaded",
  "loader_mutated",
  "kernel_executed",
  "customer_deployed",
  "stranger_host_executed",
  "credentials_issued",
  "announced",
  "clean_host_internal_proof",
  "proved_external",
  "frozen_cli_reopened",
  "python_sdk_mutated",
  "node_sdk_mutated",
  "active_protection",
  "decision_reported_as_enforcement",
  "contract_reported_as_kernel_enforcement",
  "unattached_mechanism_reported_as_active_protection",
  "healthy_enforcing_reported_as_host_enforcement",
  "blocked_host_reported_as_host_enforcement",
  "enforce_stage_reported_as_host_enforcement",
  "promoted_match_reported_as_host_enforcement",
  "missing_evidence_collapsed_to_success",
  "unknown_evidence_collapsed_to_success",
  "unavailable_evidence_collapsed_to_success",
  "optimistic_success",
  "eligible_plane",
  "named_eligible_plane",
  "infra_requirement",
  "execution_ceiling",
  "product_health_failure_truth",
  "independent_verification_status",
]);

function assertNever(value) {
  throw new Error("unhandled variant: " + String(value));
}

function sealChild(value) {
  if (!value || typeof value !== "object") return [];
  const problems = [];
  for (const key of HONESTY_TRUE_KEYS) {
    if (value[key] === true) problems.push(key);
  }
  if (typeof value.host_attachment === "string" && !ALLOWED_HOST_ATTACHMENT.has(value.host_attachment)) {
    problems.push("host_attachment");
  }
  if (Object.prototype.hasOwnProperty.call(value, "execution") && value.execution != null && !ALLOWED_EXECUTION.has(value.execution)) {
    problems.push("execution");
  }
  if (Object.prototype.hasOwnProperty.call(value, "enforcement") && value.enforcement !== "EVALUATE_ONLY") {
    problems.push("enforcement");
  }
  if (Object.prototype.hasOwnProperty.call(value, "packet_effect") && value.packet_effect !== "NOT_APPLIED") {
    problems.push("packet_effect");
  }
  if (value.idp_revoke === "EXECUTED" || value.identity_revoke === "EXECUTED") problems.push("revoke_executed");
  if (value.executor && value.executor !== "NOT_WIRED_IN_LIVE_LOADER" && value.executor !== "NOT_PRESENT") {
    problems.push("executor");
  }
  return problems;
}

function requestAttachment(request) {
  const hit = [];
  for (const key of REFUSED_REQUEST_KEYS) {
    if (Object.prototype.hasOwnProperty.call(request, key) && request[key] !== false) hit.push(key);
  }
  return hit;
}

module.exports = {
  ALLOWED_EXECUTION,
  AUDIENCE,
  COUNCIL_STATUS,
  HONESTY_FIELDS,
  HONESTY_TRUE_KEYS,
  PLANES,
  PLANE_SET,
  POSTURE,
  PREFERRED_EXECUTION,
  PRODUCER_CLASSIFICATION,
  REFUSED_REQUEST_KEYS,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  STARTING_REF,
  assertNever,
  requestAttachment,
  sealChild,
};
