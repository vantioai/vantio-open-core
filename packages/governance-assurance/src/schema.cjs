"use strict";

const {
  CAPABILITY_STATES,
  CONFIGURATION_STATES,
  DOMAINS,
  FRESHNESS,
  LIMITS,
  PRODUCTS,
  PROMOTION_BLOCKED_VERIFICATION,
  PROOF_CLASSES,
  RUNTIME_STATES,
  SUPPORT_CLASSES,
  VERIFICATION_STATES,
} = require("./constants.cjs");

const CONTROL_FIELDS = Object.freeze([
  "control_id",
  "title",
  "objective",
  "product",
  "component",
  "capability_version",
  "implementation_state",
  "configuration_state",
  "runtime_state",
  "verification_state",
  "proof_class",
  "evidence_requirements",
  "evidence_artifacts",
  "evidence_freshness",
  "customer_responsibilities",
  "Vantio_responsibilities",
  "third_party_dependencies",
  "limitations",
  "unsupported_paths",
  "external_dependencies",
  "claim_ceiling",
  "supersedes",
  "review_date",
  "primary_support",
  "domain",
  "lifecycle_order",
]);

function inList(list, value) {
  return list.includes(value);
}

function stringList(value) {
  return Array.isArray(value) && value.every((item) => typeof item === "string" && item.length > 0);
}

function boundedText(value) {
  return typeof value === "string" && value.length > 0 && value.length <= LIMITS.maxString;
}

function controlProblems(control) {
  const problems = [];
  if (control === null || typeof control !== "object" || Array.isArray(control)) {
    return ["control is not an object"];
  }
  for (const field of CONTROL_FIELDS) {
    if (control[field] === undefined) problems.push(`missing ${field}`);
  }
  if (!/^GA-\d{2}$/.test(control.control_id || "")) problems.push("control_id");
  if (!boundedText(control.title)) problems.push("title");
  if (!boundedText(control.objective)) problems.push("objective");
  if (!inList(PRODUCTS, control.product)) problems.push("product");
  if (!boundedText(control.component)) problems.push("component");
  if (!boundedText(control.capability_version)) problems.push("capability_version");
  if (!inList(CAPABILITY_STATES, control.implementation_state)) problems.push("implementation_state");
  if (!inList(CONFIGURATION_STATES, control.configuration_state)) problems.push("configuration_state");
  if (!inList(RUNTIME_STATES, control.runtime_state)) problems.push("runtime_state");
  if (!inList(VERIFICATION_STATES, control.verification_state)) problems.push("verification_state");
  if (inList(PROMOTION_BLOCKED_VERIFICATION, control.verification_state)) {
    problems.push("verification promotion blocked in 0.2.0-internal");
  }
  if (!inList(PROOF_CLASSES, control.proof_class)) problems.push("proof_class");
  if (!stringList(control.evidence_requirements)) problems.push("evidence_requirements");
  if (!stringList(control.evidence_artifacts)) problems.push("evidence_artifacts");
  if (!inList(FRESHNESS, control.evidence_freshness)) problems.push("evidence_freshness");
  if (!stringList(control.customer_responsibilities)) problems.push("customer_responsibilities");
  if (!stringList(control.Vantio_responsibilities)) problems.push("Vantio_responsibilities");
  if (!stringList(control.third_party_dependencies)) problems.push("third_party_dependencies");
  if (!stringList(control.limitations)) problems.push("limitations");
  if (!stringList(control.unsupported_paths)) problems.push("unsupported_paths");
  if (!stringList(control.external_dependencies)) problems.push("external_dependencies");
  if (!boundedText(control.claim_ceiling)) problems.push("claim_ceiling");
  if (/%/.test(control.claim_ceiling || "")) problems.push("claim ceiling contains a percent");
  if (control.supersedes !== null && typeof control.supersedes !== "string") problems.push("supersedes");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(control.review_date || "")) problems.push("review_date");
  if (!inList(SUPPORT_CLASSES, control.primary_support)) problems.push("primary_support");
  if (!inList(DOMAINS, control.domain)) problems.push("domain");
  if (!Number.isInteger(control.lifecycle_order)) problems.push("lifecycle_order");
  return problems;
}

function catalogProblems(controls) {
  const problems = [];
  if (!Array.isArray(controls)) return ["catalog is not an array"];
  if (controls.length > LIMITS.maxControls) problems.push("catalog exceeds max controls");
  const ids = new Set();
  const orders = new Set();
  for (const control of controls) {
    const rowProblems = controlProblems(control);
    for (const problem of rowProblems) problems.push(`${control && control.control_id ? control.control_id : "?"}: ${problem}`);
    if (control && ids.has(control.control_id)) problems.push(`duplicate ${control.control_id}`);
    if (control) ids.add(control.control_id);
    if (control && orders.has(control.lifecycle_order)) problems.push(`duplicate order ${control.lifecycle_order}`);
    if (control) orders.add(control.lifecycle_order);
  }
  return problems;
}

module.exports = {
  CONTROL_FIELDS,
  catalogProblems,
  controlProblems,
};
