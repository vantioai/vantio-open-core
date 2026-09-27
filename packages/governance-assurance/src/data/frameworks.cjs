"use strict";

const { RETRIEVED_AT } = require("../constants.cjs");

const NEXT_REVIEW = "Rebind at package 0.2.0 after Wave 2 merges, or sooner when the cited authority republishes.";

function document(spec) {
  return {
    document_id: spec.id,
    title: spec.title,
    version: spec.version,
    publication_date: spec.published,
    effective_date: spec.effective,
    source_url: spec.url,
    retrieved_at: RETRIEVED_AT,
    jurisdiction: spec.jurisdiction,
    authority: spec.authority,
    superseded_status: spec.superseded,
    superseded_by: spec.supersededBy || null,
    source_access: spec.access,
    body_copied: false,
    next_review_trigger: NEXT_REVIEW,
    notes: spec.notes,
  };
}

const FRAMEWORKS = [
  {
    framework_id: "NIST-AI-RMF",
    title: "NIST AI Risk Management Framework",
    documents: [
      document({
        id: "NIST-AI-100-1",
        title: "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
        version: "1.0",
        published: "2023-01-26",
        effective: "UNKNOWN",
        url: "https://www.nist.gov/itl/ai-risk-management-framework",
        jurisdiction: "US",
        authority: "NIST",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "NIST states the framework was released on January 26, 2023 and is intended for voluntary use. No legal effective date is recorded here. Function identifiers are used. Subcategory narrative is not copied. The same NIST page states that AI RMF 1.0 is being revised.",
      }),
    ],
  },
  {
    framework_id: "NIST-AI-RMF-PLAYBOOK",
    title: "NIST AI RMF Playbook",
    documents: [
      document({
        id: "NIST-AI-RMF-PLAYBOOK-FIRST",
        title: "NIST AI RMF Playbook",
        version: "first-complete-version",
        published: "2023-03-30",
        effective: "UNKNOWN",
        url: "https://www.nist.gov/itl/ai-risk-management-framework/nist-ai-rmf-playbook",
        jurisdiction: "US",
        authority: "NIST",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "The NIST playbook page states that the first complete version was announced on March 30, 2023, that it is based on AI RMF 1.0, and that it is for voluntary use. Suggested actions are not copied. The page says the playbook will be updated after AI RMF 1.0 is revised.",
      }),
    ],
  },
  {
    framework_id: "NIST-AI-AGENT-STANDARDS",
    title: "NIST AI Agent Standards Initiative outputs",
    documents: [
      document({
        id: "NIST-AGENT-INITIATIVE-PAGE",
        title: "AI Agent Standards Initiative",
        version: "page-undated",
        published: "UNKNOWN",
        effective: "UNKNOWN",
        url: "https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative",
        jurisdiction: "US",
        authority: "NIST",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "The NIST initiative page describes voluntary guidelines, protocols, and research. It does not, on the page retrieved for this register, state a single publication date or an effective date. No output text is copied.",
      }),
      document({
        id: "NIST-AI-800-5",
        title: "Summary Analysis of Responses to the Request for Information Regarding Security Considerations for AI Agents",
        version: "800-5",
        published: "2026-05-18",
        effective: "UNKNOWN",
        url: "https://www.nist.gov/publications/summary-analysis-responses-request-information-regarding-security-considerations-ai",
        jurisdiction: "US",
        authority: "NIST",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "NIST lists this report as published May 18, 2026, report number 800-5. It summarizes RFI responses. It is not a control baseline this catalog adopts, and its text is not copied.",
      }),
      document({
        id: "NCCOE-AGENT-IDENTITY-CONCEPT",
        title: "Accelerating the Adoption of Software and Artificial Intelligence Agent Identity and Authorization",
        version: "2026-02-05",
        published: "2026-02-05",
        effective: "UNKNOWN",
        url: "https://csrc.nist.gov/pubs/other/2026/02/05/accelerating-the-adoption-of-software-and-ai-agent/ipd",
        jurisdiction: "US",
        authority: "NIST NCCoE",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "CSRC lists the concept paper as published February 5, 2026, with a public comment period that closed April 2, 2026. It is a concept paper for a potential project, not a finished practice guide. Text is not copied.",
      }),
    ],
  },
  {
    framework_id: "EU-AI-ACT",
    title: "EU AI Act technical crosswalk",
    documents: [
      document({
        id: "REG-EU-2024-1689",
        title: "Regulation (EU) 2024/1689",
        version: "2024/1689",
        published: "2024-07-12",
        effective: "UNKNOWN",
        url: "http://data.europa.eu/eli/reg/2024/1689/oj",
        jurisdiction: "EU",
        authority: "European Parliament and Council",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "ELI identifies Regulation (EU) 2024/1689, published in the Official Journal on 12 July 2024. The regulation states more than one application date. This register does not collapse those dates into one effective date and does not copy the articles. The crosswalk is technical and is not a legal classification.",
      }),
    ],
  },
  {
    framework_id: "ISO-IEC-42001",
    title: "ISO/IEC 42001",
    documents: [
      document({
        id: "ISO-IEC-42001-2023",
        title: "ISO/IEC 42001:2023",
        version: "2023",
        published: "UNKNOWN",
        effective: "UNKNOWN",
        url: "https://www.iso.org/standard/81230.html",
        jurisdiction: "INTERNATIONAL",
        authority: "ISO/IEC",
        superseded: "CURRENT",
        access: "SOURCE_ACCESS_REQUIRED",
        notes: "The public catalog identifier is ISO/IEC 42001:2023. Clause text was not retrieved. No clause number and no clause sentence is asserted. A management-system certificate is not claimed.",
      }),
    ],
  },
  {
    framework_id: "US-FEDERAL-AI-ACQUISITION",
    title: "U.S. federal AI acquisition and governance guidance",
    documents: [
      document({
        id: "OMB-M-25-21",
        title: "Accelerating Federal Use of AI through Innovation, Governance, and Public Trust",
        version: "M-25-21",
        published: "2025-04-03",
        effective: "UNKNOWN",
        url: "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf",
        jurisdiction: "US",
        authority: "OMB",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "The memorandum is dated April 3, 2025. It states that it rescinds and replaces OMB Memorandum M-24-10. A single effective date is not recorded in this register. Agency duties are not copied and are not claimed as met.",
      }),
      document({
        id: "OMB-M-25-22",
        title: "Driving Efficient Acquisition of Artificial Intelligence in Government",
        version: "M-25-22",
        published: "2025-04-03",
        effective: "UNKNOWN",
        url: "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf",
        jurisdiction: "US",
        authority: "OMB",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "The memorandum is dated April 3, 2025. It states that it rescinds and replaces OMB Memorandum M-24-18. It also states that it applies to contracts awarded from solicitations issued on or after 180 days after issuance. This register does not convert that rule into a calendar effective date.",
      }),
      document({
        id: "OMB-M-26-04",
        title: "Increasing Public Trust in Artificial Intelligence Through Unbiased AI Principles",
        version: "M-26-04",
        published: "2025-12-11",
        effective: "UNKNOWN",
        url: "https://www.whitehouse.gov/wp-content/uploads/2025/12/M-26-04-Increasing-Public-Trust-in-Artificial-Intelligence-Through-Unbiased-AI-Principles-1.pdf",
        jurisdiction: "US",
        authority: "OMB",
        superseded: "CURRENT",
        access: "PUBLIC_IDENTIFIER",
        notes: "The OMB memoranda index lists M-26-04 on December 11, 2025. The memorandum body is not copied. No claim is made that a model meets it. Effective date is UNKNOWN in this register.",
      }),
      document({
        id: "OMB-M-24-10",
        title: "Advancing Governance, Innovation, and Risk Management for Agency Use of Artificial Intelligence",
        version: "M-24-10",
        published: "UNKNOWN",
        effective: "UNKNOWN",
        url: "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-21-Accelerating-Federal-Use-of-AI-through-Innovation-Governance-and-Public-Trust.pdf",
        jurisdiction: "US",
        authority: "OMB",
        superseded: "SUPERSEDED",
        supersededBy: "M-25-21",
        access: "PUBLIC_IDENTIFIER",
        notes: "Current only as a superseded pointer. M-25-21 states that it rescinds and replaces M-24-10. The superseded memorandum is not an active mapping.",
      }),
      document({
        id: "OMB-M-24-18",
        title: "Advancing the Responsible Acquisition of Artificial Intelligence in Government",
        version: "M-24-18",
        published: "UNKNOWN",
        effective: "UNKNOWN",
        url: "https://www.whitehouse.gov/wp-content/uploads/2025/02/M-25-22-Driving-Efficient-Acquisition-of-Artificial-Intelligence-in-Government.pdf",
        jurisdiction: "US",
        authority: "OMB",
        superseded: "SUPERSEDED",
        supersededBy: "M-25-22",
        access: "PUBLIC_IDENTIFIER",
        notes: "Current only as a superseded pointer. M-25-22 states that it rescinds and replaces M-24-18. The superseded memorandum is not an active mapping.",
      }),
    ],
  },
];

function frameworkById(frameworkId) {
  return FRAMEWORKS.find((item) => item.framework_id === frameworkId) || null;
}

function documentByVersion(frameworkId, version) {
  const framework = frameworkById(frameworkId);
  if (!framework) return null;
  return framework.documents.find((item) => item.version === version) || null;
}

module.exports = {
  FRAMEWORKS,
  documentByVersion,
  frameworkById,
};
