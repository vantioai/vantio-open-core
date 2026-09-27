# Governance posture

Audience: INTERNAL_RESTRICTED

## Provenance

- Package: @vantio/governance-assurance 0.1.0-internal
- Catalog: 0.1.0-internal
- Mapping: 0.1.0-internal
- Mapping commit: NOT_SELF_HASHED
- Source: vantioai/vantio-open-core @ a80fd4288df4983bf294aa219511ef60d86fa87c
- Reviewer: PENDING_INDEPENDENT_COUNCIL
- Council: PENDING_INDEPENDENT_COUNCIL

## Role

Vantio is the runtime authority, enforcement, revocation, recovery, and independently verifiable evidence layer for AI governance on customer-controlled Linux infrastructure. Vantio supports governance programs; Vantio does not independently make an AI system lawful, compliant, certified, regulator-approved, unbiased, appropriate for a regulated use, safe for every environment, or conformant with every framework.

## Claim ceiling

Governance Assurance 0.1.0-internal is a private mapping layer. NON-NORMATIVE. NOT_LEGAL_ADVICE. NO_COMPLIANCE_GUARANTEE. It does not certify a system, approve a procurement, classify legal risk, or convert a missing capability into a pass.

## State separation

Capability, configuration, runtime, and verification stay separate fields on every row.

## Counts

- Controls: 40
- Frameworks: 6
- Mappings: 144
- Evidence bindings: 22
- Customer responsibility assignments: 62
- Unsupported controls: 14
- External controls: 9

## Control rows

### GA-01 AI system inventory for supported observation paths

- Capability: AVAILABLE
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-02 Component and release-surface inventory

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-03 Coverage gap disclosure

- Capability: AVAILABLE
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-04 Legal classification and conformity roles

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_PROVIDES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-05 Ownership assignment

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_CONFIGURES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-06 Delegated authority

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_CONFIGURES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-07 Approvals and dual control

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_CONFIGURES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-08 Exception handling

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: NOT_IMPLEMENTED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-09 Customer policy authoring

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: NOT_IMPLEMENTED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-10 Host policy configuration

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-11 Host enrollment

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-12 Runtime observation of supported agent egress

- Capability: AVAILABLE
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-13 Runtime enforcement

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-14 Ingress control

- Capability: NOT_IMPLEMENTED
- Configuration: UNKNOWN
- Runtime: UNKNOWN
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: This row is not satisfied. The observe-only merge is not a pass.

### GA-15 Egress enforcement

- Capability: NOT_IMPLEMENTED
- Configuration: UNKNOWN
- Runtime: UNKNOWN
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: This row is not satisfied. The contract-only merge is not a pass.

### GA-16 Process attribution on supported paths

- Capability: AVAILABLE
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-17 In-process revocation step

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-18 Recovery after revocation or failure

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: NOT_IMPLEMENTED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-19 Evidence capture for supported observation

- Capability: AVAILABLE
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-20 Evidence custody for the closed Python release

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-21 Evidence freshness and staleness

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-22 Independent verification

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: NOT_IMPLEMENTED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-23 Customer-controlled infrastructure boundary

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_PROVIDES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-24 Credential and secret non-collection on supported paths

- Capability: AVAILABLE
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: NOT_SATISFIED (NO_COUNTING_EVIDENCE)
- Stale: false
- Ceiling: Partial. A secret placed in the URL path is stored because the path is kept. The CLI version file does not prove non-collection. This row is not certification, legal conformity, or external proof.

### GA-25 Content non-retention on supported paths

- Capability: AVAILABLE
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-26 Change and release characterization

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-27 Rollback and uninstall proof

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-28 Health and degradation signaling

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-29 Telemetry interoperability

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: PRODUCER_TESTED
- Support: CUSTOMER_CONFIGURES
- Satisfaction: NOT_SATISFIED (NO_COUNTING_EVIDENCE)
- Stale: false
- Ceiling: The adapter exists and defaults off. A configured, independently checked export is not in this tree.

### GA-30 Sequential and aggregate evaluation

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-31 Progressive enforcement staging in process

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: This row binds a bounded fact already in the tree. It is not certification, legal conformity, or external proof.

### GA-32 Host-attachment proof

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-33 Clean-host proof

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-34 Stranger-host proof

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

### GA-35 Model-provider obligations

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: THIRD_PARTY_REQUIRED
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-36 Human oversight

- Capability: DESIGNED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_PROVIDES
- Satisfaction: NOT_SATISFIED (NOT_A_PASS)
- Stale: false
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-37 Incident evidence and legal submission

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: NOT_TESTED
- Support: CUSTOMER_PROVIDES
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: The named customer or third-party role holds this duty. Vantio does not discharge it.

### GA-38 Procurement evidence packaging

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PARTIALLY_SUPPORTS
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: A private index for review. Not a submission and not an authorization to sell.

### GA-39 Claim ceiling and disclosure

- Capability: IMPLEMENTED_INTERNAL
- Configuration: NOT_APPLICABLE
- Runtime: NOT_APPLICABLE
- Verification: PRODUCER_TESTED
- Support: VANTIO_PROVIDES
- Satisfaction: BOUND_WITH_LIMITS (EVIDENCE_BOUND_NOT_A_COMPLIANCE_PASS)
- Stale: false
- Ceiling: Vantio provides this disclosure. The disclosure does not make any system conformant.

### GA-40 Decommissioning

- Capability: NOT_IMPLEMENTED
- Configuration: NOT_CONFIGURED
- Runtime: NOT_RUNNING
- Verification: NOT_TESTED
- Support: UNVERIFIED
- Satisfaction: NOT_SATISFIED (STALE)
- Stale: true
- Ceiling: This row is not satisfied. Absence, a plan, or an in-revision track is not a pass.

## Wave 2 bindings

- T1 EB-T1: RELEASE_CLOSED_REGISTRY_VERIFIED / REGISTRY_HASHES_MATCH_AUTHORIZED_PINS_CLIENT_NOT_REEXECUTED
- T3 EB-T3: NOT_IMPLEMENTED_UNVERIFIED_BLOCKED_NODE / O7_NOT_AUTHORIZED_DECISION_9_UNRESOLVED_BLOCKED_NODE
- T4 EB-T4: IMPLEMENTED_INTERNAL / IMPLEMENTED_INTERNAL_GREEN_FALSE_NO_PE_INTEGRATION
- T5 EB-T5: MERGED_OBSERVE_ONLY_LOADER_UNTOUCHED / MERGED_OBSERVE_ONLY_NOT_COUNTED
- T6 EB-T6: MERGED_CONTRACT_ONLY_HOST_NETWORK_NOT_EXECUTED / MERGED_CONTRACT_ONLY_NOT_COUNTED
- T7 EB-T7: CONTRACT_ONLY / CONTRACT_ONLY_KERNEL_NOT_EXECUTED
- T8 EB-T8: MERGED_EVALUATE_ONLY_HOST_ATTACHMENT_FALSE / EVALUATE_ONLY_HOST_ATTACHMENT_FALSE
- T9 EB-T9: MERGED_IN_PROCESS_HOST_ATTACHMENT_NOT_PERFORMED / IN_PROCESS_HOST_ATTACHMENT_NOT_PERFORMED
- T10 EB-T10: BLOCKED_INFRA / BLOCKED_INFRA_EVIDENCE_UNSET
- T11 EB-T11: DEMO_NOT_COMPLIANCE_PROOF / NOT_COMPLIANCE_PROOF
- T12 EB-T12: IMPLEMENTED_INTERNAL_DEFAULT_DISABLED / DEFAULT_DISABLED_NOT_OPERATIONAL
- T13 EB-T13: PLAN_ONLY_NO_LIVE_CUSTOMER_AUTHORITY / NO_LIVE_CUSTOMER_AUTHORITY
- T14 EB-T14: CHARACTERIZED_NO_FORMAL_CERTIFICATION / CHARACTERIZED_FORMAL_CLAIMS_NOT_CLAIMED
- T16 EB-T16: READINESS_ONLY_EXECUTION_NOT_AUTHORIZED / EXECUTION_NOT_AUTHORIZED
- BENCHMARK EB-BENCH: DESIGN_TARGET / NO_EVIDENCE_BACKED_CLAIM
- UNIT-D EB-UNIT-D: MERGED_FUTURE_CLI_NOT_SHIPPED / UNIT_D_PROVED_NOT_SHIPPED
- UNIT-E EB-UNIT-E: MERGED_NO_LIVE_INTEGRATION / MERGED_NO_LIVE_INTEGRATION_NOT_A_SHIPPED_WRITER
- CLI EB-CLI-0324: FROZEN_PUBLISHED / FROZEN_CLI_0_3_24_UNCHANGED
- OPTICS-PRIVACY EB-OPTICS-PRIVACY: DOCUMENTED_EXCEPTION_NOT_REEXECUTED / URL_PATH_SECRET_RETAINED_NOT_REEXECUTED
- WS17 EB-ROLE: PRIVATE_MAPPING_LAYER / DISCLOSURE_ONLY
- WS17 EB-STALENESS: IMPLEMENTED_INTERNAL / STALENESS_FUNCTION_PRESENT
- WS17 EB-PROCUREMENT: PRIVATE_NOT_SUBMITTED / INDEX_GENERATED_NOT_SUBMITTED

## Prohibited interpretations

- Do not treat this packet as a compliance percentage or an overall score.
- Do not treat a missing, planned, or in-revision capability as a pass.
- Do not promote producer tests, internal packages, or a demo into external proof.
- Do not treat a dashboard, an HTTP 200, process existence, exit 0, or a generated report as sole proof.
- Do not treat the producer as the independent verifier.
- Do not assign legal classification, conformity, registration, or incident submission to Vantio by default.
- Do not read a framework crosswalk as certification, regulator approval, or a statement that Vantio fulfills the framework.
- Do not treat the Python 3.1.0 release-close as runtime observation or as observation evidence capture.
- Do not treat a package version file as proof that credentials are not collected.

This report has no compliance score and no legal conclusion.
