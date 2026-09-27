"use strict";

const fs = require("node:fs");
const path = require("node:path");

const { canonicalize, stableStringify } = require("./canonical.cjs");
const {
  AUDIENCE,
  CAPABILITY_STATES,
  CATALOG_VERSION,
  CLAIM_CEILING,
  CONFIGURATION_STATES,
  DISTRIBUTION,
  MAPPING_COMMIT,
  MAPPING_VERSION,
  PACKAGE_NAME,
  PACKAGE_VERSION,
  PRODUCER_CLASSIFICATION,
  PROHIBITED_INTERPRETATIONS,
  RETRIEVED_AT,
  REVIEWER,
  ROLE_STATEMENT,
  RUNTIME_STATES,
  SOURCE_BASE_COMMIT,
  SOURCE_REPOSITORY,
  SUPPORT_CLASSES,
  VERIFICATION_STATES,
} = require("./constants.cjs");
const { CONTROLS } = require("./data/controls.cjs");
const { loadEvidence } = require("./evidence.cjs");
const { FRAMEWORKS, MAPPINGS, selectMappings, unmappedControls } = require("./mappings.cjs");
const { buildMatrix, customerResponsibilityCount } = require("./responsibility.cjs");
const { isExternal, isUnsupported, satisfactionFor } = require("./satisfaction.cjs");

const PUBLIC_KEYS = Object.freeze([
  "document",
  "distribution",
  "role_statement",
  "claim_ceiling",
  "detail",
  "customer_confidential",
  "procurement_submitted",
  "proof_class_elevated",
]);

function provenance(generatedAt) {
  return {
    package_name: PACKAGE_NAME,
    package_version: PACKAGE_VERSION,
    catalog_version: CATALOG_VERSION,
    mapping_version: MAPPING_VERSION,
    mapping_commit: MAPPING_COMMIT,
    source_repository: SOURCE_REPOSITORY,
    source_base_commit: SOURCE_BASE_COMMIT,
    audience: AUDIENCE,
    distribution: "INTERNAL_RESTRICTED",
    reviewer: REVIEWER,
    retrieved_at: RETRIEVED_AT,
    generated_at: generatedAt || RETRIEVED_AT,
    generator: PACKAGE_NAME,
    producer_classification: PRODUCER_CLASSIFICATION,
    council_status: "PENDING_INDEPENDENT_COUNCIL",
    self_certified_council_pass: false,
  };
}

function postureRows(controls, bindings, context) {
  return controls.map((control) => ({
    control_id: control.control_id,
    title: control.title,
    product: control.product,
    lifecycle_order: control.lifecycle_order,
    implementation_state: control.implementation_state,
    configuration_state: control.configuration_state,
    runtime_state: control.runtime_state,
    verification_state: control.verification_state,
    primary_support: control.primary_support,
    proof_class: control.proof_class,
    evidence_freshness: control.evidence_freshness,
    claim_ceiling: control.claim_ceiling,
    satisfaction: satisfactionFor(control, bindings, context),
  }));
}

function publicDisclosure() {
  return {
    document: "GOVERNANCE_PUBLIC_DISCLOSURE",
    distribution: "PUBLIC",
    role_statement: ROLE_STATEMENT,
    claim_ceiling: CLAIM_CEILING,
    detail: "CONTROL_DETAIL_WITHHELD",
    customer_confidential: false,
    procurement_submitted: false,
    proof_class_elevated: false,
  };
}

function buildReports(options = {}) {
  const controls = options.controls || CONTROLS;
  const bindings = options.bindings || loadEvidence(options.root);
  const mappings = options.mappings || MAPPINGS;
  const frameworks = options.frameworks || FRAMEWORKS;
  const context = options.context || {};
  const matrix = options.matrix || buildMatrix(controls);
  const rows = postureRows(controls, bindings, context);
  const unsupported = controls.filter(isUnsupported).map((control) => ({
    control_id: control.control_id,
    title: control.title,
    primary_support: control.primary_support,
    implementation_state: control.implementation_state,
    reason: "Unverified or not implemented. This entry is not a pass.",
  }));
  const external = controls.filter(isExternal).map((control) => ({
    control_id: control.control_id,
    title: control.title,
    primary_support: control.primary_support,
    reason: "A customer or third party holds the duty. Vantio does not discharge it.",
  }));
  const controlIds = controls.map((control) => control.control_id);
  const base = provenance(options.generatedAt);
  const posture = {
    document: "GOVERNANCE_POSTURE",
    schema: "vantio.governance-assurance.posture/v1",
    provenance: base,
    role_statement: ROLE_STATEMENT,
    claim_ceiling: CLAIM_CEILING,
    state_separation: {
      capability: CAPABILITY_STATES,
      configuration: CONFIGURATION_STATES,
      runtime: RUNTIME_STATES,
      verification: VERIFICATION_STATES,
    },
    support_classes: SUPPORT_CLASSES,
    counts: {
      controls: controls.length,
      frameworks: frameworks.length,
      mappings: mappings.length,
      evidence_bindings: bindings.length,
      customer_responsibility_assignments: customerResponsibilityCount(matrix),
      unsupported_controls: unsupported.length,
      external_controls: external.length,
    },
    controls: rows,
    wave2: bindings.map((binding) => ({
      binding_id: binding.binding_id,
      track_id: binding.track_id,
      wave2_state: binding.wave2_state,
      verification_result: binding.verification_result,
      proof_class: binding.proof_class,
      counts_toward_satisfaction: binding.counts_toward_satisfaction,
      count_control_ids: binding.count_control_ids,
      freshness: binding.freshness,
      independent_verifier: binding.independent_verifier,
    })),
    prohibited_interpretations: PROHIBITED_INTERPRETATIONS,
    refuses: [
      "overall compliance score",
      "compliance percentage",
      "legal conclusion",
      "certification conclusion",
      "regulator approval",
    ],
  };
  const evidenceIndex = {
    document: "CONTROL_EVIDENCE_INDEX",
    schema: "vantio.governance-assurance.evidence-index/v1",
    provenance: base,
    bindings: bindings.map((binding) => ({
      binding_id: binding.binding_id,
      track_id: binding.track_id,
      title: binding.title,
      control_ids: binding.control_ids,
      count_control_ids: binding.count_control_ids,
      artifact_records: binding.artifact_records,
      artifact_status: binding.artifact_status,
      producer: binding.producer,
      collection_source: binding.collection_source,
      product_version: binding.product_version,
      source_commit: binding.source_commit,
      environment: binding.environment,
      timestamp: binding.timestamp,
      freshness: binding.freshness,
      proof_class: binding.proof_class,
      independent_verifier: binding.independent_verifier,
      verification_result: binding.verification_result,
      limitations: binding.limitations,
      prohibited_interpretations: binding.prohibited_interpretations,
      wave2_state: binding.wave2_state,
      informs_posture: binding.informs_posture,
      counts_toward_satisfaction: binding.counts_toward_satisfaction,
    })),
  };
  const frameworkRegister = {
    document: "FRAMEWORK_VERSION_REGISTER",
    schema: "vantio.governance-assurance.framework-register/v1",
    provenance: base,
    frameworks: frameworks.map((framework) => ({
      framework_id: framework.framework_id,
      title: framework.title,
      documents: framework.documents.map((document) => ({
        ...document,
        active: document.superseded_status === "CURRENT",
      })),
      unmapped_control_ids: framework.documents
        .filter((document) => document.superseded_status === "CURRENT")
        .map((document) => ({
          version: document.version,
          control_ids: unmappedControls(framework.framework_id, document.version, controlIds, mappings),
        })),
    })),
  };
  const responsibility = {
    document: "CUSTOMER_RESPONSIBILITY_MATRIX",
    schema: "vantio.governance-assurance.responsibility-export/v1",
    provenance: base,
    ...matrix,
  };
  const unsupportedDoc = {
    document: "UNSUPPORTED_AND_EXTERNAL_CONTROLS",
    schema: "vantio.governance-assurance.unsupported/v1",
    provenance: base,
    unsupported,
    external,
    unsupported_control_count: unsupported.length,
    external_control_count: external.length,
  };
  const procurement = {
    document: "PROCUREMENT_EVIDENCE_INDEX",
    schema: "vantio.governance-assurance.procurement/v1",
    provenance: base,
    distribution: "INTERNAL_RESTRICTED",
    distribution_classes: DISTRIBUTION,
    submission_status: "NOT_SUBMITTED",
    proof_class_elevated: false,
    customer_confidential_on_public: false,
    refuses: ["ATO", "FedRAMP authorization", "agency acceptance", "procurement approval"],
    artifacts: [
      "GOVERNANCE_POSTURE.json",
      "GOVERNANCE_POSTURE.md",
      "CUSTOMER_RESPONSIBILITY_MATRIX.json",
      "CONTROL_EVIDENCE_INDEX.json",
      "FRAMEWORK_VERSION_REGISTER.json",
      "UNSUPPORTED_AND_EXTERNAL_CONTROLS.json",
      "PROCUREMENT_EVIDENCE_INDEX.json",
      "VERIFICATION_INSTRUCTIONS.md",
    ].map((name) => ({
      name,
      distribution: "INTERNAL_RESTRICTED",
      proof_class: "PRODUCER_TEST",
      proof_class_elevated: false,
    })),
    claim_ceiling: CLAIM_CEILING,
  };
  const reports = {
    "GOVERNANCE_POSTURE.json": posture,
    "CUSTOMER_RESPONSIBILITY_MATRIX.json": responsibility,
    "CONTROL_EVIDENCE_INDEX.json": evidenceIndex,
    "FRAMEWORK_VERSION_REGISTER.json": frameworkRegister,
    "UNSUPPORTED_AND_EXTERNAL_CONTROLS.json": unsupportedDoc,
    "PROCUREMENT_EVIDENCE_INDEX.json": procurement,
    "GOVERNANCE_POSTURE.md": renderPostureMarkdown(posture),
    "VERIFICATION_INSTRUCTIONS.md": renderVerification(),
    "PUBLIC_DISCLOSURE.json": publicDisclosure(),
  };
  assertReportsSafe(reports);
  return reports;
}

function renderPostureMarkdown(posture) {
  const lines = [
    "# Governance posture",
    "",
    `Audience: ${posture.provenance.audience}`,
    "",
    "## Provenance",
    "",
    `- Package: ${posture.provenance.package_name} ${posture.provenance.package_version}`,
    `- Catalog: ${posture.provenance.catalog_version}`,
    `- Mapping: ${posture.provenance.mapping_version}`,
    `- Mapping commit: ${posture.provenance.mapping_commit}`,
    `- Source: ${posture.provenance.source_repository} @ ${posture.provenance.source_base_commit}`,
    `- Reviewer: ${posture.provenance.reviewer}`,
    `- Council: ${posture.provenance.council_status}`,
    "",
    "## Role",
    "",
    ROLE_STATEMENT,
    "",
    "## Claim ceiling",
    "",
    posture.claim_ceiling,
    "",
    "## State separation",
    "",
    "Capability, configuration, runtime, and verification stay separate fields on every row.",
    "",
    "## Counts",
    "",
    `- Controls: ${posture.counts.controls}`,
    `- Frameworks: ${posture.counts.frameworks}`,
    `- Mappings: ${posture.counts.mappings}`,
    `- Evidence bindings: ${posture.counts.evidence_bindings}`,
    `- Customer responsibility assignments: ${posture.counts.customer_responsibility_assignments}`,
    `- Unsupported controls: ${posture.counts.unsupported_controls}`,
    `- External controls: ${posture.counts.external_controls}`,
    "",
    "## Control rows",
    "",
  ];
  for (const row of posture.controls) {
    lines.push(`### ${row.control_id} ${row.title}`);
    lines.push("");
    lines.push(`- Capability: ${row.implementation_state}`);
    lines.push(`- Configuration: ${row.configuration_state}`);
    lines.push(`- Runtime: ${row.runtime_state}`);
    lines.push(`- Verification: ${row.verification_state}`);
    lines.push(`- Support: ${row.primary_support}`);
    lines.push(`- Satisfaction: ${row.satisfaction.status} (${row.satisfaction.reason})`);
    lines.push(`- Stale: ${row.satisfaction.staleness.stale}`);
    lines.push(`- Ceiling: ${row.claim_ceiling}`);
    lines.push("");
  }
  lines.push("## Wave 2 bindings");
  lines.push("");
  for (const binding of posture.wave2) {
    lines.push(`- ${binding.track_id} ${binding.binding_id}: ${binding.wave2_state} / ${binding.verification_result}`);
  }
  lines.push("");
  lines.push("## Prohibited interpretations");
  lines.push("");
  for (const item of posture.prohibited_interpretations) lines.push(`- ${item}`);
  lines.push("");
  lines.push("This report has no compliance score and no legal conclusion.");
  lines.push("");
  return lines.join("\n");
}

function renderVerification() {
  return [
    "# Verification instructions",
    "",
    "Audience: INTERNAL_RESTRICTED",
    "",
    "From the repository root:",
    "",
    "```",
    "node --test tests/governance-assurance/*.test.cjs",
    "```",
    "",
    "The package is private and is not a pnpm workspace member. Do not publish it.",
    "",
    "A passing test run is a producer check of this catalog. It is not independent verification, not a clean-host proof, and not a stranger-host proof.",
    "",
    "Reviewer for the mappings is PENDING_INDEPENDENT_COUNCIL. This force does not sit that council.",
    "",
    "Regenerate the reports with the package `buildReports` function. The default clock is the catalog review instant, not a live wall clock.",
    "",
    "Version rebind:",
    "",
    "- 0.2.0 after Wave 2 merges that change a bound track.",
    "- 0.3.0 after clean-host evidence exists.",
    "- 0.4.0 after stranger-host execution is authorized and completed.",
    "- 1.0.0-customer-candidate only after external assessment, disclosure review, and a separate release council.",
    "",
  ].join("\n");
}

function renderFramework(frameworkId) {
  const framework = FRAMEWORKS.find((item) => item.framework_id === frameworkId);
  if (!framework) return renderView(frameworkId, "missing");
  return framework.documents.map((document) => renderView(frameworkId, document.version)).join("\n");
}

function renderView(frameworkId, version) {
  const selected = selectMappings(frameworkId, version);
  const lines = [
    `# ${frameworkId} ${version}`,
    "",
    "Audience: INTERNAL_RESTRICTED",
    "",
    "Vantio does not fulfill this framework. Rows are crosswalks.",
    "",
  ];
  if (!selected.ok) {
    lines.push(`Selection failed closed: ${selected.reason}.`);
    lines.push("");
    return lines.join("\n");
  }
  lines.push(`Status: ${selected.reason}. Active: ${selected.active}.`);
  if (selected.superseded_by) lines.push(`Superseded by: ${selected.superseded_by}.`);
  lines.push("");
  for (const mapping of selected.mappings) {
    lines.push(`- ${mapping.mapping_id} ${mapping.control_id || "register"} ${mapping.reference}: ${mapping.relationship_note}`);
  }
  lines.push("");
  return lines.join("\n");
}

function writeReports(directory, options = {}) {
  const reports = buildReports(options);
  fs.mkdirSync(directory, { recursive: true });
  for (const [name, value] of Object.entries(reports)) {
    const text = typeof value === "string" ? value : stableStringify(value);
    fs.writeFileSync(path.join(directory, name), text);
  }
  return reports;
}

function claimProblems(value, pathName = "$") {
  const problems = [];
  if (typeof value === "string") {
    if (value === ROLE_STATEMENT || value === CLAIM_CEILING) return problems;
    if (/\d+(?:\.\d+)?\s*%/.test(value)) problems.push(`${pathName} contains a percent`);
    if (value === "PASS" || value === "COMPLIANT" || value === "MOSTLY_COMPLIANT" || value === "CERTIFIED") {
      problems.push(`${pathName} affirmative claim`);
    }
    return problems;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => problems.push(...claimProblems(item, `${pathName}[${index}]`)));
    return problems;
  }
  if (value && typeof value === "object") {
    for (const key of Object.keys(value)) {
      if (key === "prohibited_interpretations" || key === "refuses" || key === "banned") continue;
      if (key === "overall_compliance_score" || key === "compliance_percent" || key === "legal_conclusion") {
        problems.push(`${pathName}.${key} forbidden field`);
      }
      problems.push(...claimProblems(value[key], `${pathName}.${key}`));
    }
  }
  return problems;
}

function assertReportsSafe(reports) {
  const problems = [];
  for (const [name, value] of Object.entries(reports)) {
    if (name === "PUBLIC_DISCLOSURE.json") {
      const keys = Object.keys(value);
      for (const key of keys) {
        if (!PUBLIC_KEYS.includes(key)) problems.push(`public key ${key}`);
      }
    }
    problems.push(...claimProblems(value, name));
  }
  if (problems.length > 0) throw new Error(problems.join("; "));
  return reports;
}

module.exports = {
  PUBLIC_KEYS,
  assertReportsSafe,
  buildReports,
  canonicalize,
  claimProblems,
  publicDisclosure,
  renderFramework,
  renderView,
  writeReports,
};
