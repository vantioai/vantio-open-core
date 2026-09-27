"use strict";

const { PLANES } = require("./boundary.cjs");

const OBSERVATION_OPS = new Set([
  "accept_identity",
  "inspect",
  "clock",
  "quote_host",
  "set_store_available",
]);

const EVIDENCE_OPS = new Set([
  "export_evidence",
  "hash_evidence",
  "rollback_intent",
  "uninstall_intent",
  "leave_material",
]);

function blankPlane() {
  return {
    present: false,
    status: "ABSENT",
    execution: null,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

function emptyPlanes() {
  const planes = {};
  for (const name of PLANES) planes[name] = blankPlane();
  planes.INDEPENDENT_VERIFICATION = {
    present: true,
    status: "NOT_INDEPENDENTLY_VERIFIED",
    execution: "NOT_PERFORMED",
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
  return planes;
}

function mark(planes, name, status, execution) {
  planes[name] = {
    present: true,
    status,
    execution,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

function holdEnforcement(planes) {
  mark(planes, "APPLICATION_ENFORCEMENT", "NOT_APPLIED", "EVALUATE_ONLY");
  mark(planes, "HOST_ENFORCEMENT", "NOT_APPLIED", "HOST_ATTACHMENT_FALSE");
}

function projectEnterprise(op, result) {
  const planes = emptyPlanes();
  const outcome = result && typeof result.outcome === "string" ? result.outcome : "REFUSED";
  if (OBSERVATION_OPS.has(op)) mark(planes, "OBSERVATION", "RECORDED", "EVALUATE_ONLY");
  if (op === "host_intent") mark(planes, "OBSERVATION", "HOST_INTENT_RECORDED", "NOT_PERFORMED");
  mark(planes, "DECISION", outcome, op === "host_intent" ? "NOT_PERFORMED" : "EVALUATE_ONLY");
  if (op === "revoke_grant") mark(planes, "REVOCATION", "RECORDED_NOT_HOST", "EVALUATE_ONLY");
  if (op === "freeze" || op === "recover") mark(planes, "CONTAINMENT", "DECISION_RECORDED_ONLY", "NOT_PERFORMED");
  if (EVIDENCE_OPS.has(op)) mark(planes, "EVIDENCE", "RECORDED", "NOT_PERFORMED");
  else mark(planes, "EVIDENCE", "RECORDED", "EVALUATE_ONLY");
  holdEnforcement(planes);
  return planes;
}

function faultPlanes() {
  const planes = emptyPlanes();
  mark(planes, "DECISION", "REFUSED", "NOT_PERFORMED");
  mark(planes, "EVIDENCE", "FAULT_RECORDED", "NOT_PERFORMED");
  holdEnforcement(planes);
  return planes;
}

function copyPlane(row) {
  return {
    present: row.present === true,
    status: row.status,
    execution: row.execution,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

function enforcementRow(rows, name) {
  if (rows.length === 0) return blankPlane();
  const gap = rows.some((row) => row.status === "GAP");
  const executions = new Set(rows.map((row) => row.execution));
  let execution = name === "HOST_ENFORCEMENT" ? "HOST_ATTACHMENT_FALSE" : "EVALUATE_ONLY";
  if (executions.has("CONTRACT_ONLY")) execution = "CONTRACT_ONLY";
  return {
    present: true,
    status: gap ? "GAP" : "NOT_APPLIED",
    execution,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

function presentRow(row) {
  return Boolean(row && row.present === true && row.status !== "ABSENT");
}

function joinPlanes(enterprisePlanes, pePlanes) {
  const planes = emptyPlanes();
  for (const name of PLANES) {
    if (name === "INDEPENDENT_VERIFICATION") continue;
    const left = enterprisePlanes ? enterprisePlanes[name] : null;
    const right = pePlanes ? pePlanes[name] : null;
    if (name === "APPLICATION_ENFORCEMENT" || name === "HOST_ENFORCEMENT") {
      const rows = [left, right].filter(presentRow);
      planes[name] = enforcementRow(rows, name);
      continue;
    }
    if (name === "DECISION") {
      const leftOn = presentRow(left);
      const rightOn = presentRow(right);
      if (leftOn && rightOn) {
        mark(planes, "DECISION", "SEPARATED", "EVALUATE_ONLY");
      } else if (leftOn) {
        planes.DECISION = copyPlane(left);
      } else if (rightOn) {
        planes.DECISION = copyPlane(right);
      }
      continue;
    }
    const rows = [left, right].filter(presentRow);
    if (rows.length === 1) planes[name] = copyPlane(rows[0]);
    else if (rows.length > 1) mark(planes, name, "RECORDED", rows[rows.length - 1].execution || "EVALUATE_ONLY");
  }
  return planes;
}

function quoteEnterprise(result) {
  const reason = result && result.reason;
  const recordWritten = result && (
    result.policy_applied === true
    || reason === "POLICY_NARROWED"
    || reason === "POLICY_WIDENED"
  );
  return {
    outcome: result ? result.outcome : null,
    reason: reason || null,
    record_layer_only: true,
    live_customer_authority: false,
    customer_authority_promoted: false,
    host_contacted: false,
    verified_on_host: false,
    credential_created: false,
    external_identity_created: false,
    identity_authenticated: false,
    satisfies_host_proof: false,
    evaluation_only: true,
    record_policy_written: recordWritten === true,
    applied_to_host: false,
    title_holder: result ? result.title_holder : null,
    host_enrolled: false,
    host_protected: false,
    host_enforced: false,
    host_freeze_performed: false,
    host_expanded_authority_cleared: result && result.host_expanded_authority_cleared
      ? result.host_expanded_authority_cleared
      : null,
    grant_minted: false,
  };
}

module.exports = {
  emptyPlanes,
  enforcementRow,
  faultPlanes,
  joinPlanes,
  projectEnterprise,
  quoteEnterprise,
};
