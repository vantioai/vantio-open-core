"use strict";

const { PLANES } = require("./boundary.cjs");
const { PATHS } = require("../../../packages/pe-egress-authority/src/paths.cjs");

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

function notApplied(planes, name, execution) {
  mark(planes, name, "NOT_APPLIED", execution);
}

function holdEnforcement(planes, hostExecution) {
  if (planes.APPLICATION_ENFORCEMENT.status === "ABSENT") {
    notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
  }
  if (planes.HOST_ENFORCEMENT.status === "ABSENT") {
    notApplied(planes, "HOST_ENFORCEMENT", hostExecution);
  }
}

function projectHealth(record) {
  const planes = emptyPlanes();
  mark(planes, "OBSERVATION", record.state, "EVALUATE_ONLY");
  mark(planes, "EVIDENCE", "QUOTED", "EVALUATE_ONLY");
  notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
  notApplied(planes, "HOST_ENFORCEMENT", "HOST_ATTACHMENT_FALSE");
  return planes;
}

function projectIngress(result) {
  const planes = emptyPlanes();
  if (result.authority === "OBSERVED_ONLY") mark(planes, "OBSERVATION", "RECORDED", "EVALUATE_ONLY");
  mark(planes, "DECISION", result.authority, "EVALUATE_ONLY");
  notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
  notApplied(planes, "HOST_ENFORCEMENT", "HOST_ATTACHMENT_FALSE");
  if (result.containment && result.containment.required === true) {
    mark(planes, "CONTAINMENT", "DECISION_RECORDED_ONLY", "NOT_PERFORMED");
  }
  if (result.reason === "revoked") mark(planes, "REVOCATION", "RECORDED_NOT_HOST", "EVALUATE_ONLY");
  mark(planes, "EVIDENCE", result.evidence_decision, "EVALUATE_ONLY");
  return planes;
}

function projectEgress(decision) {
  const planes = emptyPlanes();
  const path = decision.path_id ? PATHS[decision.path_id] : null;
  const hostPath = Boolean(path && path.plane === "host");
  const gap = decision.result === "ENFORCEMENT_GAP";
  mark(planes, "DECISION", decision.result, hostPath ? "CONTRACT_ONLY" : "EVALUATE_ONLY");
  mark(planes, "EVIDENCE", decision.evidence_class || "ABSENT", hostPath ? "CONTRACT_ONLY" : "EVALUATE_ONLY");
  if (hostPath) {
    planes.HOST_ENFORCEMENT = {
      present: true,
      status: gap ? "GAP" : "NOT_APPLIED",
      execution: "CONTRACT_ONLY",
      active_protection: false,
      kernel_executed: false,
      host_attachment: false,
      applied: false,
    };
    notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
  } else {
    planes.APPLICATION_ENFORCEMENT = {
      present: true,
      status: gap ? "GAP" : "NOT_APPLIED",
      execution: "EVALUATE_ONLY",
      active_protection: false,
      kernel_executed: false,
      host_attachment: false,
      applied: false,
    };
    notApplied(planes, "HOST_ENFORCEMENT", "HOST_ATTACHMENT_FALSE");
  }
  if (decision.result === "CONTAINED") mark(planes, "CONTAINMENT", "DECISION_RECORDED_ONLY", "EVALUATE_ONLY");
  if (decision.result === "REVOKED") mark(planes, "REVOCATION", "RECORDED_NOT_HOST", "EVALUATE_ONLY");
  return planes;
}

function projectHost(decision) {
  const planes = emptyPlanes();
  if (decision.disposition === "OBSERVED_ONLY" || decision.disposition === "LABELED_NOT_DENIED") {
    mark(planes, "OBSERVATION", decision.disposition, "CONTRACT_ONLY");
  }
  mark(planes, "DECISION", decision.disposition, "CONTRACT_ONLY");
  planes.HOST_ENFORCEMENT = {
    present: true,
    status: "NOT_APPLIED",
    execution: "CONTRACT_ONLY",
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
  notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
  mark(planes, "EVIDENCE", "CONTRACT_ROW", "CONTRACT_ONLY");
  return planes;
}

function projectSequential(result) {
  const planes = emptyPlanes();
  mark(planes, "DECISION", result.disposition, "EVALUATE_ONLY");
  holdEnforcement(planes, "HOST_ATTACHMENT_FALSE");
  if (result.axis === "lineage" || (typeof result.reason === "string" && result.reason.includes("lineage"))) {
    mark(planes, "OBSERVATION", "LINEAGE_EVALUATED", "EVALUATE_ONLY");
  }
  if (
    (typeof result.reason === "string" && result.reason.includes("revoc"))
    || (Array.isArray(result.revoked_ids) && result.revoked_ids.length > 0)
  ) {
    mark(planes, "REVOCATION", "RECORDED_NOT_HOST", "EVALUATE_ONLY");
  }
  return planes;
}

function projectProgressive(result) {
  const planes = emptyPlanes();
  const decisionClass = result.decision_class || null;
  const stage = result.stage || result.lifecycle_stage || null;
  if (decisionClass === "OBSERVATION" || stage === "DISCOVER" || stage === "OBSERVE") {
    mark(planes, "OBSERVATION", "RECORDED", "EVALUATE_ONLY");
  }
  if (decisionClass && decisionClass !== "OBSERVATION") {
    mark(planes, "DECISION", decisionClass, "EVALUATE_ONLY");
  } else if (result.ok === false) {
    mark(planes, "DECISION", "REFUSED", "EVALUATE_ONLY");
  } else if (stage && stage !== "DISCOVER" && stage !== "OBSERVE") {
    mark(planes, "DECISION", stage, "EVALUATE_ONLY");
  }
  if (decisionClass === "PROMOTED_MATCH" || stage === "ENFORCE" || stage === "REVIEW") {
    notApplied(planes, "APPLICATION_ENFORCEMENT", "EVALUATE_ONLY");
    notApplied(planes, "HOST_ENFORCEMENT", "HOST_ATTACHMENT_FALSE");
  }
  if (decisionClass === "ROLLED_BACK" || stage === "REVOKE_OR_ROLLBACK") {
    mark(planes, "REVOCATION", "RECORDED_NOT_HOST", "EVALUATE_ONLY");
  }
  if (decisionClass === "REMOVED" || stage === "VERIFY_REMOVAL" || stage === "RETIRE") {
    mark(planes, "EVIDENCE", "REMOVAL_RECORDED_NOT_HOST", "NOT_PERFORMED");
  } else if (result.evidence_id) {
    mark(planes, "EVIDENCE", "RECORDED", "EVALUATE_ONLY");
  }
  holdEnforcement(planes, "HOST_ATTACHMENT_FALSE");
  return planes;
}

function projectPolicy() {
  const planes = emptyPlanes();
  mark(planes, "DECISION", "RECORDED", "NOT_PERFORMED");
  mark(planes, "EVIDENCE", "VERSION_RECORDED", "NOT_PERFORMED");
  holdEnforcement(planes, "HOST_ATTACHMENT_FALSE");
  return planes;
}

function projectUninstall() {
  const planes = emptyPlanes();
  mark(planes, "DECISION", "RECORDED_NOT_PERFORMED", "NOT_PERFORMED");
  mark(planes, "EVIDENCE", "RECORDED", "NOT_PERFORMED");
  holdEnforcement(planes, "HOST_ATTACHMENT_FALSE");
  return planes;
}

function faultPlanes() {
  const planes = emptyPlanes();
  mark(planes, "DECISION", "REFUSED", "NOT_PERFORMED");
  mark(planes, "EVIDENCE", "FAULT_RECORDED", "NOT_PERFORMED");
  holdEnforcement(planes, "HOST_ATTACHMENT_FALSE");
  return planes;
}

module.exports = {
  emptyPlanes,
  faultPlanes,
  projectEgress,
  projectHealth,
  projectHost,
  projectIngress,
  projectPolicy,
  projectProgressive,
  projectSequential,
  projectUninstall,
};
