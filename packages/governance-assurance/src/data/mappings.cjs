"use strict";

const { MAPPING_COMMIT, MAPPING_VERSION, REVIEWER } = require("../constants.cjs");
const { CONTROLS } = require("./controls.cjs");
const { documentByVersion } = require("./frameworks.cjs");

const NIST_FUNCTION = Object.freeze({
  "GA-01": "MAP",
  "GA-02": "MAP",
  "GA-03": "MAP",
  "GA-04": "GOVERN",
  "GA-05": "GOVERN",
  "GA-06": "GOVERN",
  "GA-07": "GOVERN",
  "GA-08": "GOVERN",
  "GA-09": "GOVERN",
  "GA-10": "MANAGE",
  "GA-11": "MANAGE",
  "GA-12": "MEASURE",
  "GA-13": "MANAGE",
  "GA-14": "MANAGE",
  "GA-15": "MANAGE",
  "GA-16": "MAP",
  "GA-17": "MANAGE",
  "GA-18": "MANAGE",
  "GA-19": "MEASURE",
  "GA-20": "MEASURE",
  "GA-21": "MEASURE",
  "GA-22": "MEASURE",
  "GA-23": "GOVERN",
  "GA-24": "GOVERN",
  "GA-25": "GOVERN",
  "GA-26": "GOVERN",
  "GA-27": "MANAGE",
  "GA-28": "MEASURE",
  "GA-29": "MANAGE",
  "GA-30": "MANAGE",
  "GA-31": "MANAGE",
  "GA-32": "MEASURE",
  "GA-33": "MEASURE",
  "GA-34": "MEASURE",
  "GA-35": "MAP",
  "GA-36": "GOVERN",
  "GA-37": "MANAGE",
  "GA-38": "GOVERN",
  "GA-39": "GOVERN",
  "GA-40": "MANAGE",
});

const EU_ROWS = Object.freeze([
  ["GA-01", "Art. 11", "Technical documentation support is limited to metadata the product actually records. This is not the legal technical file."],
  ["GA-04", "Art. 6", "Risk classification stays with the customer and counsel. This row does not classify any system."],
  ["GA-04", "Art. 27", "Fundamental-rights assessment stays with the customer and counsel."],
  ["GA-04", "Art. 43", "Conformity assessment is excluded from Vantio. No notified-body role is claimed."],
  ["GA-04", "Art. 49", "Registration is a customer and counsel duty. Vantio does not register a system."],
  ["GA-12", "Art. 12", "Supported observation can contribute logs of destination, process, size, and timing. It is not a complete record-keeping system."],
  ["GA-13", "Art. 15", "Cybersecurity and robustness duties are not discharged. Runtime enforcement is unverified in this tree."],
  ["GA-19", "Art. 12", "Evidence capture is partial and path-limited. It is not automatic logging for every system."],
  ["GA-25", "Art. 10", "Data-governance and training-data duties stay with the customer and the model provider."],
  ["GA-35", "Art. 53", "General-purpose model provider duties are not Vantio duties. The article identifier is a boundary, not a claim of conformity."],
  ["GA-36", "Art. 14", "Human oversight stays with the customer. Planned approval classes are not live oversight."],
  ["GA-37", "Art. 73", "Legal incident submission stays with the customer. This package does not notify an authority."],
  ["GA-39", "Art. 13", "Transparency to users of a customer system is not established by this disclosure row."],
]);

const FEDERAL_ROWS = Object.freeze([
  ["GA-04", "M-25-21", "High-impact and agency governance determinations belong to the agency. This row does not make them."],
  ["GA-26", "M-25-22", "Release characterization is not post-award performance monitoring and not a contract deliverable."],
  ["GA-35", "M-26-04", "LLM procurement principles are agency and provider matters. No model is asserted to meet them."],
  ["GA-38", "M-25-22", "The private index can be read while preparing a vendor response. It is not a submission and not an award."],
  ["GA-39", "M-25-21", "The claim ceiling is a vendor disclosure. It is not an agency compliance plan."],
]);

const AGENT_ROWS = Object.freeze([
  ["GA-06", "NCCOE-AGENT-IDENTITY-CONCEPT", "2026-02-05", "The concept paper discusses agent identity and authorization. This tree has no live delegation object."],
  ["GA-13", "NIST-AI-800-5", "800-5", "The report summarizes comments on agent security. It is not a requirement this catalog treats as met."],
  ["GA-16", "NCCOE-AGENT-IDENTITY-CONCEPT", "2026-02-05", "Process metadata on a wrapped path is not agent identity infrastructure."],
  ["GA-30", "NIST-AGENT-INITIATIVE-PAGE", "page-undated", "Sequential evaluation is an internal candidate. It is not an industry standard adopted by the initiative."],
]);

function row(spec) {
  return {
    mapping_id: spec.mappingId,
    control_id: spec.controlId,
    framework_id: spec.frameworkId,
    document_id: spec.document.document_id,
    document_title: spec.document.title,
    document_version: spec.document.version,
    jurisdiction: spec.document.jurisdiction,
    authority: spec.document.authority,
    publication_date: spec.document.publication_date,
    effective_date: spec.document.effective_date,
    source_url: spec.document.source_url,
    retrieved_at: spec.document.retrieved_at,
    mapping_version: MAPPING_VERSION,
    mapping_commit: MAPPING_COMMIT,
    reviewer: REVIEWER,
    superseded_status: spec.document.superseded_status,
    superseded_by: spec.document.superseded_by,
    next_review_trigger: spec.document.next_review_trigger,
    reference: spec.reference,
    relationship_note: spec.note,
    vantio_fulfills_function: false,
    legal_classification: "NOT_A_LEGAL_CLASSIFICATION",
    clause_text: null,
    source_access: spec.document.source_access,
    related_mapping_ids: spec.related || [],
    active: spec.document.superseded_status === "CURRENT",
  };
}

function buildMappings() {
  const mappings = [];
  const nistDoc = documentByVersion("NIST-AI-RMF", "1.0");
  const playbook = documentByVersion("NIST-AI-RMF-PLAYBOOK", "first-complete-version");
  const iso = documentByVersion("ISO-IEC-42001", "2023");
  const eu = documentByVersion("EU-AI-ACT", "2024/1689");
  for (const control of CONTROLS) {
    const fn = NIST_FUNCTION[control.control_id];
    const nistId = `MAP-NIST-${control.control_id}`;
    mappings.push(row({
      mappingId: nistId,
      controlId: control.control_id,
      frameworkId: "NIST-AI-RMF",
      document: nistDoc,
      reference: fn,
      note: `${fn} is the function identifier only. Vantio does not fulfill ${fn}. Subcategory text is not copied. Support on this row follows ${control.primary_support}.`,
    }));
    mappings.push(row({
      mappingId: `MAP-PLAY-${control.control_id}`,
      controlId: control.control_id,
      frameworkId: "NIST-AI-RMF-PLAYBOOK",
      document: playbook,
      reference: fn,
      note: `Playbook suggestions for ${fn} are not copied and are not adopted as completed actions.`,
      related: [nistId],
    }));
    mappings.push(row({
      mappingId: `MAP-ISO-${control.control_id}`,
      controlId: control.control_id,
      frameworkId: "ISO-IEC-42001",
      document: iso,
      reference: "SOURCE_ACCESS_REQUIRED",
      note: "No clause number is assigned. Vantio does not establish the customer's management system and does not claim certification readiness.",
    }));
  }
  for (const [controlId, reference, note] of EU_ROWS) {
    mappings.push(row({
      mappingId: `MAP-EU-${controlId}-${reference.replace(/[^A-Z0-9]+/gi, "")}`,
      controlId,
      frameworkId: "EU-AI-ACT",
      document: eu,
      reference,
      note,
    }));
  }
  for (const [controlId, version, note] of FEDERAL_ROWS) {
    mappings.push(row({
      mappingId: `MAP-FED-${controlId}-${version}`,
      controlId,
      frameworkId: "US-FEDERAL-AI-ACQUISITION",
      document: documentByVersion("US-FEDERAL-AI-ACQUISITION", version),
      reference: version,
      note,
    }));
  }
  for (const [controlId, documentId, version, note] of AGENT_ROWS) {
    mappings.push(row({
      mappingId: `MAP-AGENT-${controlId}-${documentId}`,
      controlId,
      frameworkId: "NIST-AI-AGENT-STANDARDS",
      document: documentByVersion("NIST-AI-AGENT-STANDARDS", version),
      reference: documentId,
      note,
    }));
  }
  mappings.push(row({
    mappingId: "MAP-SUPER-M-24-10",
    controlId: null,
    frameworkId: "US-FEDERAL-AI-ACQUISITION",
    document: documentByVersion("US-FEDERAL-AI-ACQUISITION", "M-24-10"),
    reference: "M-24-10",
    note: "Superseded by M-25-21. Visible so a reader does not apply the replaced memorandum as current.",
  }));
  mappings.push(row({
    mappingId: "MAP-SUPER-M-24-18",
    controlId: null,
    frameworkId: "US-FEDERAL-AI-ACQUISITION",
    document: documentByVersion("US-FEDERAL-AI-ACQUISITION", "M-24-18"),
    reference: "M-24-18",
    note: "Superseded by M-25-22. Visible so a reader does not apply the replaced memorandum as current.",
  }));
  return mappings;
}

const MAPPINGS = buildMappings();

module.exports = {
  MAPPINGS,
  NIST_FUNCTION,
};
