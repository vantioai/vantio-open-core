"use strict";

const PACKAGE_NAME = "@vantio/governance-assurance";
const PACKAGE_VERSION = "0.2.0-internal";
const CATALOG_VERSION = "0.2.0-internal";
const MAPPING_VERSION = "0.2.0-internal";
const SUPERSEDES_PACKAGE = "0.1.0-internal";
const AUDIENCE = "INTERNAL_RESTRICTED";
const SOURCE_REPOSITORY = "vantioai/vantio-open-core";
const SOURCE_BASE_COMMIT = "b0bcbdeb01ccb84a58a3aa6aacd0c05f94b22450";
const MAPPING_COMMIT = "NOT_SELF_HASHED";
const REVIEWER = "PENDING_INDEPENDENT_COUNCIL";
const REVIEW_DATE = "2026-09-28";
const RETRIEVED_AT = "2026-09-28T17:26:43Z";
const PRODUCER_CLASSIFICATION = "WS17_GOVERNANCE_ASSURANCE_0_2_0_INTERNAL_REBIND_READY_FOR_COUNCIL";
const PROGRAM_CLAIM_CEILING = "INTERNAL_CLEAN_HOST_PROOF";

const ROLE_STATEMENT =
  "Vantio is the runtime authority, enforcement, revocation, recovery, and independently verifiable evidence layer for AI governance on customer-controlled Linux infrastructure. Vantio supports governance programs; Vantio does not independently make an AI system lawful, compliant, certified, regulator-approved, unbiased, appropriate for a regulated use, safe for every environment, or conformant with every framework.";

const CLAIM_CEILING =
  "Governance Assurance 0.2.0-internal is a private mapping layer. NON-NORMATIVE. NOT_LEGAL_ADVICE. NO_COMPLIANCE_GUARANTEE. It does not certify a system, approve a procurement, classify legal risk, or convert a missing capability into a pass. It does not raise a proof class and it is not a customer candidate.";

const CAPABILITY_STATES = Object.freeze([
  "NOT_IMPLEMENTED",
  "DESIGNED",
  "IMPLEMENTED_INERT",
  "IMPLEMENTED_INTERNAL",
  "INTEGRATED",
  "AVAILABLE",
]);

const CONFIGURATION_STATES = Object.freeze([
  "NOT_CONFIGURED",
  "CONFIGURED",
  "MISCONFIGURED",
  "UNKNOWN",
  "NOT_APPLICABLE",
]);

const RUNTIME_STATES = Object.freeze([
  "NOT_RUNNING",
  "OBSERVING",
  "ENFORCING",
  "DEGRADED",
  "STALE",
  "DISCONNECTED",
  "UNKNOWN",
  "NOT_APPLICABLE",
]);

const VERIFICATION_STATES = Object.freeze([
  "NOT_TESTED",
  "PRODUCER_TESTED",
  "INDEPENDENTLY_TESTED",
  "CLEAN_HOST_INTERNAL_PROOF",
  "PROVED_EXTERNAL",
  "CUSTOMER_VALIDATED",
  "EXTERNALLY_ASSESSED",
]);

const SUPPORT_CLASSES = Object.freeze([
  "VANTIO_PROVIDES",
  "VANTIO_PARTIALLY_SUPPORTS",
  "CUSTOMER_CONFIGURES",
  "CUSTOMER_PROVIDES",
  "THIRD_PARTY_REQUIRED",
  "NOT_APPLICABLE",
  "NOT_IMPLEMENTED",
  "UNVERIFIED",
]);

const PROOF_CLASSES = Object.freeze([
  "NONE",
  "DESIGN_RECORD",
  "PRODUCER_TEST",
  "CONTRACT_EVALUATION",
  "RELEASE_CLOSE_PACKET",
  "CHARACTERIZATION",
  "BLOCKED_UNSET",
  "NOT_COMPLIANCE_ELIGIBLE",
  "SOURCE_ACCESS_REQUIRED",
]);

const FRESHNESS = Object.freeze([
  "CURRENT_FOR_CATALOG_REVIEW",
  "UNKNOWN",
  "STALE",
  "UNSET",
  "NOT_APPLICABLE",
]);

const PRODUCTS = Object.freeze([
  "OPTICS",
  "PHANTOM_ENGINE",
  "ENTERPRISE",
  "GOVERNANCE_ASSURANCE",
]);

const DOMAINS = Object.freeze([
  "OPERATIONAL",
  "LEGAL",
  "PRIVACY",
  "PROCUREMENT",
  "EVIDENCE",
  "DISCLOSURE",
]);

const ROLES = Object.freeze([
  "VANTIO",
  "CUSTOMER_AI_OWNER",
  "CUSTOMER_SECURITY",
  "CUSTOMER_COMPLIANCE",
  "CUSTOMER_LEGAL",
  "CUSTOMER_PRIVACY",
  "CUSTOMER_INFRASTRUCTURE_OPERATOR",
  "MODEL_PROVIDER",
  "THIRD_PARTY_INTEGRATOR",
  "INDEPENDENT_ASSESSOR",
]);

const RACI = Object.freeze([
  "RESPONSIBLE",
  "ACCOUNTABLE",
  "CONSULTED",
  "INFORMED",
  "NOT_APPLICABLE",
]);

const DISTRIBUTION = Object.freeze([
  "PUBLIC",
  "INVESTOR_UNDER_NDA",
  "CUSTOMER_CONFIDENTIAL",
  "INTERNAL_RESTRICTED",
  "ASSESSOR_CONFIDENTIAL",
]);

const REJECTED_SOLE_PROOFS = Object.freeze([
  "DASHBOARD_GREEN",
  "HTTP_200",
  "PROCESS_EXISTS",
  "PRODUCER_WRITTEN_PASS",
  "EXIT_0",
  "GENERATED_REPORT_ALONE",
  "STALE_EVIDENCE",
  "SIMULATION_AS_REAL",
  "PHANTOM_BOX_AS_STRANGER_HOST",
]);

const STALENESS_TRIGGERS = Object.freeze([
  "PRODUCT_VERSION_CHANGED",
  "CATALOG_VERSION_CHANGED",
  "FRAMEWORK_VERSION_CHANGED",
  "AUTHORITY_POLICY_CHANGED",
  "EVIDENCE_EXPIRED",
  "VERIFICATION_FAILED",
  "COVERAGE_CHANGED",
  "CAPABILITY_REMOVED_OR_DEGRADED",
  "EXCEPTION_EXPIRED",
  "ROLLBACK_OR_UNINSTALL_INCOMPLETE",
  "EXTERNAL_DEPENDENCY_UNAVAILABLE",
]);

const PROMOTION_BLOCKED_VERIFICATION = Object.freeze([
  "INDEPENDENTLY_TESTED",
  "CLEAN_HOST_INTERNAL_PROOF",
  "PROVED_EXTERNAL",
  "CUSTOMER_VALIDATED",
  "EXTERNALLY_ASSESSED",
]);

const LIMITS = Object.freeze({
  maxDepth: 8,
  maxNodes: 500,
  maxControls: 256,
  maxMappings: 2000,
  maxString: 4000,
});

const PROHIBITED_INTERPRETATIONS = Object.freeze([
  "Do not treat this packet as a compliance percentage or an overall score.",
  "Do not treat a missing, planned, or in-revision capability as a pass.",
  "Do not promote producer tests, internal packages, or a demo into external proof.",
  "Do not treat a dashboard, an HTTP 200, process existence, exit 0, or a generated report as sole proof.",
  "Do not treat the producer as the independent verifier.",
  "Do not assign legal classification, conformity, registration, or incident submission to Vantio by default.",
  "Do not read a framework crosswalk as certification, regulator approval, or a statement that Vantio fulfills the framework.",
  "Do not treat the Python 3.1.0 release-close as runtime observation or as observation evidence capture.",
  "Do not treat a package version file as proof that credentials are not collected.",
  "Do not treat PARTIAL_INTERNAL_CLEAN_HOST_PROOF as full efficacy, as 0.3.0, or as a customer candidate.",
  "Do not treat SOURCE_CLOSED_MERGED on RBK-004 as a live Class A residual-only re-proof.",
  "Do not treat STAGE_B_DESTROY_PASS as a billing close, as C8 readiness, or as Council F acceptance.",
  "Do not treat NOT_CAPTURED recordings as captured demonstrations.",
  "Do not treat an integration record that names open gates as a clean result with those gates removed.",
]);

module.exports = {
  AUDIENCE,
  CAPABILITY_STATES,
  CATALOG_VERSION,
  CLAIM_CEILING,
  CONFIGURATION_STATES,
  DISTRIBUTION,
  DOMAINS,
  FRESHNESS,
  LIMITS,
  MAPPING_COMMIT,
  MAPPING_VERSION,
  PACKAGE_NAME,
  PACKAGE_VERSION,
  PRODUCTS,
  PRODUCER_CLASSIFICATION,
  PROGRAM_CLAIM_CEILING,
  PROHIBITED_INTERPRETATIONS,
  PROMOTION_BLOCKED_VERIFICATION,
  PROOF_CLASSES,
  RACI,
  REJECTED_SOLE_PROOFS,
  REVIEW_DATE,
  REVIEWER,
  RETRIEVED_AT,
  ROLE_STATEMENT,
  ROLES,
  RUNTIME_STATES,
  SOURCE_BASE_COMMIT,
  SOURCE_REPOSITORY,
  SUPERSEDES_PACKAGE,
  STALENESS_TRIGGERS,
  SUPPORT_CLASSES,
  VERIFICATION_STATES,
};
