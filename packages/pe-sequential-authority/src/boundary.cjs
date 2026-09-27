"use strict";

const POSTURE = Object.freeze([
  "INTERNAL_CANDIDATE",
  "EVALUATE_ONLY",
  "NOT_HOST_ENFORCEMENT",
  "NOT_SHIPPED",
  "NO_KERNEL",
  "NO_ENROLL",
  "NO_CREDENTIAL_MATERIAL",
  "NO_STABLE_SCHEMA",
]);

const AUDIENCE = "INTERNAL_RESTRICTED";
const CLASSIFICATION = "PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const PACKAGE_NAME = "@vantio/pe-sequential-authority";
const PACKAGE_VERSION = "0.0.0-unstable-pre-1.0";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const ENFORCEMENT = "EVALUATE_ONLY";
const STARTING_REF = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";

const INVARIANTS = Object.freeze([
  "SPLIT_CANNOT_BYPASS_AGGREGATE",
  "CONSENSUS_IS_NOT_AUTHORIZATION",
  "PROCESS_COUNT_IS_NOT_PRINCIPAL",
  "CHILD_CANNOT_EXCEED_INHERITANCE",
  "DELEGATION_CANNOT_CREATE_RESERVED_RIGHTS",
  "REVOCATION_REACHES_DESCENDANTS",
  "STALE_DESCENDANT_DOES_NOT_SURVIVE_PARENT_REVOCATION",
  "NO_REPLAY_ACROSS_ACTIONS",
  "SEQUENCE_DOES_NOT_COMPOSE_UNAUTHORIZED_AUTHORITY",
]);

const LIMIT_AXES = Object.freeze([
  "action",
  "sequence",
  "run",
  "workload",
  "lineage",
  "credential",
  "destination",
  "tenant",
  "node",
  "fleet",
  "time_window",
  "resource_budget",
]);

const RESERVED_RIGHTS = Object.freeze([
  "freeze",
  "revoke_root",
  "recover",
  "export",
  "hash_evidence",
  "rollback",
  "uninstall",
  "leave",
  "witness_removal",
  "root_set_change",
]);

const RESERVED_DOMAINS = Object.freeze(["security", "recovery"]);
const DOMAIN_NAMES = Object.freeze(["workload", "security", "recovery"]);
const CAUSES = Object.freeze(["grant", "process_spawn", "consensus"]);
const AUTHORITY_SOURCES = Object.freeze(["envelope", "consensus", "process_count"]);
const STATES = Object.freeze(["ACTIVE", "REVOKED", "EXPIRED"]);

const COMPOSITIONS = Object.freeze([
  Object.freeze({
    id: "observe_then_label_enforced",
    priorAction: "observe",
    stepAction: "label_enforced",
    derived: "enforce",
  }),
  Object.freeze({
    id: "propose_then_record_approval",
    priorAction: "propose",
    stepAction: "record_approval",
    derived: "activate",
  }),
  Object.freeze({
    id: "exercise_then_name_delegate",
    priorAction: "exercise",
    stepAction: "name_delegate",
    derived: "delegate",
  }),
]);

const RULES = Object.freeze(["INPUT_REJECTED", "LIMIT", "REDELEGATION_FORBIDDEN"]);
const MAX_COLLECTION = 10000;

function assertNever(value) {
  throw new Error("unhandled variant: " + String(value));
}

module.exports = {
  AUDIENCE,
  AUTHORITY_SOURCES,
  CAUSES,
  CLASSIFICATION,
  COMPOSITIONS,
  COUNCIL_STATUS,
  DOMAIN_NAMES,
  ENFORCEMENT,
  INVARIANTS,
  LIMIT_AXES,
  MAX_COLLECTION,
  PACKAGE_NAME,
  PACKAGE_VERSION,
  POSTURE,
  RESERVED_DOMAINS,
  RESERVED_RIGHTS,
  RULES,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  STARTING_REF,
  STATES,
  assertNever,
};
