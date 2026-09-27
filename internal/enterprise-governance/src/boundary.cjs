"use strict";

// Internal record evaluator. Not a host agent, not an identity provider, not Phantom Engine.

const AUDIENCE = "INTERNAL_RESTRICTED";
const SCHEMA_STATUS = "unstable-pre-1.0";
const SCHEMA_VERSION = 0;
const MODULE_VERSION = "0.0.0-unstable-pre-1.0";
const PRODUCER_CLASSIFICATION = "ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const COUNCIL_VERDICT = null;
const PLAN_CLASSIFICATION_IN_TREE = "ENTERPRISE_GOVERNANCE_E1_E3_PLAN_READY_FOR_COUNCIL";
const PLAN_SITUATION = "ENTERPRISE_GOVERNANCE_E1_E3_PLAN_MERGED_NO_IMPLEMENTATION";
const STARTING_COMMIT = "89f95099d0dce463307eb75d78e7fcf2ef99feb2";
const PLAN_MERGE = "8eb353a94c08c1adaaa36d36e2536ee5619e9eb6";

const POSTURE = Object.freeze([
  "INTERNAL",
  "RECORD_EVALUATOR",
  "NOT_SHIPPED",
  "NO_HOST_CONTACT",
  "NO_CREDENTIALS",
  "NO_EXTERNAL_IDENTITY",
  "NO_ENFORCEMENT_ENGINE",
  "NO_STABLE_SCHEMA",
]);

const DOMAINS = Object.freeze(["workload", "security", "recovery"]);
const APPROVAL_CLASSES = Object.freeze(["INSPECT", "NARROW", "WIDEN", "ROOT", "RECOVERY"]);
const RECOVERY_MODES = Object.freeze(["last-known", "observe-only", "stay-quarantined"]);
const RESERVED_POWERS = Object.freeze([
  "freeze",
  "revoke_grant",
  "recover",
  "export",
  "hash",
  "rollback",
  "uninstall",
  "remove_witness",
]);

const REJECTED_ACTS = Object.freeze([
  "vantio_only_freeze",
  "vantio_only_revoke",
  "vantio_only_recover",
  "vendor_root_replacement",
  "unsigned_loosening",
  "console_attach",
  "billing_attach",
  "support_attach",
  "workload_self_approval",
  "same_person_dual_control",
  "wider_restore",
  "dry_run_activation",
  "second_enforcement_engine",
  "breakglass_off",
  "erase_evidence",
  "appoint_vantio",
  "mark_host_protected",
  "mark_host_enrolled",
  "mark_host_enforced",
]);

const DECISIONS = Object.freeze({
  "EG-D1": Object.freeze({ resolved: false, safe_default: "forbidden" }),
  "EG-D2": Object.freeze({ resolved: false, safe_default: "exactly_two" }),
  "EG-D3": Object.freeze({ resolved: false, safe_default: "optional_witness_not_quorum" }),
  "EG-D4": Object.freeze({ resolved: false, safe_default: "root_may_recover_vantio_cannot" }),
  "EG-D5": Object.freeze({ resolved: false, safe_default: "activation_on_customer_host_not_here" }),
  "EG-D6": Object.freeze({ resolved: false, safe_default: "customer_held_copy_not_a_store_product" }),
  "EG-D7": Object.freeze({ resolved: false, safe_default: "NOT_SET" }),
  "EG-D8": Object.freeze({ resolved: false, safe_default: "company_host_out_of_customer_model" }),
  "EG-D9": Object.freeze({ resolved: false, safe_default: "one_customer_root_identity" }),
  "EG-D10": Object.freeze({ resolved: false, safe_default: "security_delegate_may_narrow" }),
});

const REQUIREMENTS = Object.freeze({
  "EG-E1-1": "INTERNAL_RULE_ENFORCED",
  "EG-E1-2": "INTERNAL_RULE_ENFORCED_HOST_MECHANISM_ABSENT",
  "EG-E1-3": "INTERNAL_RULE_ENFORCED",
  "EG-E1-4": "INTERNAL_RULE_ENFORCED_HOST_MECHANISM_ABSENT",
  "EG-E1-5": "INTERNAL_RULE_ENFORCED",
  "EG-E1-6": "INTERNAL_RULE_ENFORCED",
  "EG-E2-1": "INTERNAL_RULE_ENFORCED",
  "EG-E2-2": "INTERNAL_RULE_ENFORCED",
  "EG-E2-3": "INTERNAL_RULE_ENFORCED",
  "EG-E2-4": "INTERNAL_RULE_ENFORCED",
  "EG-E2-5": "INTERNAL_RULE_ENFORCED",
  "EG-E2-6": "INTERNAL_RULE_ENFORCED",
  "EG-E2-7": "INTERNAL_RULE_ENFORCED",
  "EG-E2-8": "RECORD_LAYER_ONLY_HOST_UNSATISFIED",
  "EG-E3-1": "INTERNAL_RULE_ENFORCED",
  "EG-E3-2": "INTERNAL_RULE_ENFORCED",
  "EG-E3-3": "INTERNAL_RULE_ENFORCED",
  "EG-E3-4": "INTERNAL_RULE_ENFORCED",
  "EG-E3-5": "INTERNAL_RULE_ENFORCED",
  "EG-E3-6": "INTERNAL_RULE_ENFORCED",
  "EG-E3-7": "RECORD_LAYER_ONLY_HOST_UNSATISFIED",
  "EG-E3-8": "HOST_UNSATISFIED",
  "EG-SUB-1": "INTERNAL_RULE_ENFORCED",
  "EG-SUB-2": "INTERNAL_RULE_ENFORCED",
  "EG-SUB-3": "INTERNAL_RULE_ENFORCED_HOST_MECHANISM_ABSENT",
  "EG-SUB-4": "INTERNAL_RULE_ENFORCED",
  "EG-SUB-5": "INTERNAL_RULE_ENFORCED",
  "EG-SUB-6": "HOST_UNSATISFIED",
  "EG-SP-1": "NOT_RUN_HOST_UNSATISFIED",
  "EG-SP-2": "NOT_RUN_HOST_UNSATISFIED",
  "EG-SP-3": "NOT_RUN_HOST_UNSATISFIED",
  "EG-SP-4": "NOT_RUN_HOST_UNSATISFIED",
  "EG-SP-5": "NOT_RUN_HOST_UNSATISFIED",
});

const STORE_MARKER = "customer-held-enterprise-record";

module.exports = {
  APPROVAL_CLASSES,
  AUDIENCE,
  COUNCIL_STATUS,
  COUNCIL_VERDICT,
  DECISIONS,
  DOMAINS,
  MODULE_VERSION,
  PLAN_CLASSIFICATION_IN_TREE,
  PLAN_MERGE,
  PLAN_SITUATION,
  POSTURE,
  PRODUCER_CLASSIFICATION,
  RECOVERY_MODES,
  REJECTED_ACTS,
  REQUIREMENTS,
  RESERVED_POWERS,
  SCHEMA_STATUS,
  SCHEMA_VERSION,
  STARTING_COMMIT,
  STORE_MARKER,
};
