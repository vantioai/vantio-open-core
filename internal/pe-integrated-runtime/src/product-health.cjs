"use strict";

const path = require("node:path");

const contract = require("../../../packages/shared-health-runtime/contract.json");
const blocked = require("../../../docs/programs/production-readiness/wave3/BLOCKED-INFRA.json");
const {
  HONESTY_FIELDS,
  POSTURE,
  PREFERRED_EXECUTION,
  assertNever,
} = require("./boundary.cjs");

const PRODUCER_CLASSIFICATION = "W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL";
const COUNCIL_STATUS = "PENDING_INDEPENDENT_COUNCIL";
const STARTING_REF = "0cd36cf1d01c4db83a0a6999db0a322441f61c98";
const REGISTER_DIR = path.join(__dirname, "../../../docs/internal/wave3/product-health");

const STATES = new Set(contract.states);
const HEALTHY = new Set(contract.healthy_tokens);
const COLLAPSE_TOKENS = new Set([
  "HEALTHY_ENFORCING",
  "BLOCKED_HOST",
  "ENFORCE",
  "PROMOTED_MATCH",
]);
const DECISION_TOKENS = new Set(["BLOCKED_HOST", "ENFORCE", "PROMOTED_MATCH"]);
const ALLOWED_ROW_EXECUTION = new Set([
  "CONTRACT_ONLY",
  "EVALUATE_ONLY",
  "HOST_ATTACHMENT_FALSE",
  "NOT_PERFORMED",
]);
const ALLOWED_PLANES = new Set(["OBSERVATION", "DECISION"]);
const PLANE_NAMES = Object.freeze([
  "OBSERVATION",
  "DECISION",
  "APPLICATION_ENFORCEMENT",
  "HOST_ENFORCEMENT",
  "CONTAINMENT",
  "REVOCATION",
  "EVIDENCE",
  "INDEPENDENT_VERIFICATION",
]);
const ATTACHMENT_KEYS = Object.freeze([
  "host_attachment",
  "attach_host",
  "load_ebpf",
  "ebpf_loaded",
  "enroll_host",
  "active_protection",
  "kernel_executed",
]);
const SUCCESS_KEYS = Object.freeze([
  "success",
  "green",
  "product_success",
  "proved",
  "proved_external",
  "clean_host_internal_proof",
  "optimistic_success",
]);
const REQUIRED_ROW_TOKENS = Object.freeze([
  "HEALTHY_ENFORCING",
  "BLOCKED_HOST",
  "ENFORCE",
  "PROMOTED_MATCH",
  "EVIDENCE_UNAVAILABLE",
  "ENFORCEMENT_UNKNOWN",
]);

function loadJson(name) {
  return require(path.join(REGISTER_DIR, name));
}

function assertRegister(doc, label) {
  if (doc.producer_classification !== PRODUCER_CLASSIFICATION) {
    throw new Error(label + " producer_classification");
  }
  if (doc.council_status !== COUNCIL_STATUS) throw new Error(label + " council_status");
  if (doc.council_verdict !== null) throw new Error(label + " council_verdict");
  if (doc.self_certified_council_pass !== false) throw new Error(label + " self_certified_council_pass");
  if (doc.starting_ref !== STARTING_REF) throw new Error(label + " starting_ref");
  if (doc.audience !== "INTERNAL_RESTRICTED") throw new Error(label + " audience");
  if (!Array.isArray(doc.vocabulary_states_added) || doc.vocabulary_states_added.length !== 0) {
    throw new Error(label + " vocabulary_states_added");
  }
  for (const field of HONESTY_FIELDS) {
    if (doc[field] !== POSTURE[field]) throw new Error(label + " honesty " + field);
  }
  if (JSON.stringify(doc.preferred_execution) !== JSON.stringify(PREFERRED_EXECUTION)) {
    throw new Error(label + " preferred_execution");
  }
}

function assertRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) throw new Error("product health rows missing");
  const tokens = new Set();
  for (const row of rows) {
    if (tokens.has(row.token)) throw new Error("duplicate product health row " + row.token);
    tokens.add(row.token);
    if (!ALLOWED_PLANES.has(row.plane)) throw new Error("row plane " + row.token);
    if (!ALLOWED_ROW_EXECUTION.has(row.execution)) throw new Error("row execution " + row.token);
    if (row.reported_as_host_enforcement !== false) throw new Error("row host report " + row.token);
    if (row.host_attachment !== false) throw new Error("row host_attachment " + row.token);
    if (row.collapsed_to_success !== false) throw new Error("row collapsed " + row.token);
    if (DECISION_TOKENS.has(row.token) && row.plane !== "DECISION") throw new Error("decision plane " + row.token);
    if (STATES.has(row.token) && row.plane !== "OBSERVATION") throw new Error("observation plane " + row.token);
  }
  for (const token of REQUIRED_ROW_TOKENS) {
    if (!tokens.has(token)) throw new Error("missing product health row " + token);
  }
}

const RUNTIME_REGISTER = loadJson("RUNTIME-REGISTER.json");
const INTEGRATION_REGISTER = loadJson("INTEGRATION-REGISTER.json");
assertRegister(RUNTIME_REGISTER, "PRODUCT-HEALTH-RUNTIME-REGISTER");
assertRegister(INTEGRATION_REGISTER, "PRODUCT-HEALTH-INTEGRATION-REGISTER");
assertRows(INTEGRATION_REGISTER.rows);

function expectedPlane(token) {
  switch (token) {
    case "BLOCKED_HOST":
    case "ENFORCE":
    case "PROMOTED_MATCH":
      return "DECISION";
    case "HEALTHY_ENFORCING":
    case "HEALTHY_OBSERVING":
    case "INTENTIONALLY_DISABLED":
    case "UNSUPPORTED":
    case "PARTIAL_COVERAGE":
    case "DEGRADED":
    case "STALE":
    case "DISCONNECTED":
    case "EVIDENCE_UNAVAILABLE":
    case "ENFORCEMENT_UNKNOWN":
    case "ROLLBACK_INCOMPLETE":
    case "UNINSTALL_INCOMPLETE":
      return "OBSERVATION";
    default:
      return assertNever(token);
  }
}

function packetFacts() {
  const plane = typeof blocked.plane_id === "string" && blocked.plane_id ? blocked.plane_id : "UNKNOWN";
  const requirement = blocked.requirement && typeof blocked.requirement.id === "string"
    ? blocked.requirement.id
    : "UNKNOWN";
  const eligibleCount = typeof blocked.eligible_count === "number" ? blocked.eligible_count : null;
  return {
    document: blocked.document || null,
    plane_id: plane,
    lifecycle: typeof blocked.lifecycle === "string" ? blocked.lifecycle : "UNKNOWN",
    track5_lifecycle: typeof blocked.track5_lifecycle === "string" ? blocked.track5_lifecycle : "UNKNOWN",
    requirement_id: requirement,
    eligible_count: eligibleCount,
    producer_classification: typeof blocked.producer_classification === "string" ? blocked.producer_classification : null,
    named_eligible_plane: plane !== "NONE" && plane !== "UNKNOWN" && eligibleCount > 0,
  };
}

function reportedAsHostEnforcement(hostPlane, token) {
  if (!hostPlane || typeof hostPlane !== "object") return null;
  if (hostPlane.applied === true) return true;
  if (hostPlane.active_protection === true) return true;
  if (hostPlane.kernel_executed === true) return true;
  if (hostPlane.host_attachment === true) return true;
  if (hostPlane.status === "APPLIED") return true;
  if (hostPlane.status === token) return true;
  return false;
}

function reportedAsApplicationEnforcement(appPlane, token) {
  if (!appPlane || typeof appPlane !== "object") return null;
  if (appPlane.applied === true) return true;
  if (appPlane.active_protection === true) return true;
  if (appPlane.status === "APPLIED") return true;
  if (appPlane.status === token) return true;
  return false;
}

function evidenceFor(quote, state) {
  if (state == null) return "PRESENT";
  if (state === "EVIDENCE_UNAVAILABLE") return "UNAVAILABLE";
  if (state === "ENFORCEMENT_UNKNOWN") return "UNKNOWN";
  if (quote.evidence_source == null || quote.evidence_source === "ABSENT") return "MISSING";
  return "PRESENT";
}

function pushToken(list, token) {
  if (!list.includes(token)) list.push(token);
}

function tokensFrom(contribution) {
  const quote = contribution.quote && typeof contribution.quote === "object" ? contribution.quote : {};
  const decision = contribution.planes && contribution.planes.DECISION ? contribution.planes.DECISION : null;
  const known = [];
  const unknown = [];
  if (typeof quote.state === "string") {
    if (STATES.has(quote.state)) pushToken(known, quote.state);
    else unknown.push(quote.state);
  }
  if (quote.live_wire_action === "BLOCKED_HOST") pushToken(known, "BLOCKED_HOST");
  if (quote.stage === "ENFORCE" || (decision && decision.status === "ENFORCE")) pushToken(known, "ENFORCE");
  if (quote.decision_class === "PROMOTED_MATCH" || (decision && decision.status === "PROMOTED_MATCH")) {
    pushToken(known, "PROMOTED_MATCH");
  }
  return { known, unknown };
}

function citation(contribution, token) {
  const planes = contribution.planes && typeof contribution.planes === "object" ? contribution.planes : null;
  const host = planes ? planes.HOST_ENFORCEMENT : null;
  const app = planes ? planes.APPLICATION_ENFORCEMENT : null;
  const quote = contribution.quote && typeof contribution.quote === "object" ? contribution.quote : {};
  const reported = reportedAsHostEnforcement(host, token);
  const required = expectedPlane(token);
  const state = STATES.has(token) ? token : null;
  return {
    token,
    required_plane: required,
    plane: reported === true ? "HOST_ENFORCEMENT" : required,
    capability: contribution.capability || null,
    op: contribution.op || null,
    reported_as_host_enforcement: reported,
    reported_as_application_enforcement: reportedAsApplicationEnforcement(app, token),
    host_enforcement_status: host ? host.status : null,
    host_enforcement_execution: host ? host.execution : null,
    host_enforcement_applied: host ? host.applied === true : null,
    application_enforcement_status: app ? app.status : null,
    application_enforcement_applied: app ? app.applied === true : null,
    failure_classification: state ? (quote.failure_classification || null) : null,
    failure_classification_basis: state ? (quote.failure_classification_basis || null) : null,
    evidence: evidenceFor(quote, state),
    green: quote.green === true,
    proved: quote.proved === true,
    token_is_not_a_latch: state ? quote.token_is_not_a_latch === true : false,
  };
}

function selectProductState(validStates, unknownStates) {
  if (unknownStates.length > 0 && validStates.length === 0) {
    return {
      state: "ENFORCEMENT_UNKNOWN",
      reason: "unknown_health_state",
      visible_states: unknownStates.slice(),
    };
  }
  if (validStates.length === 0) {
    return {
      state: "EVIDENCE_UNAVAILABLE",
      reason: "shared_health_record_absent",
      visible_states: [],
    };
  }
  const unique = [];
  for (const state of validStates) {
    if (!unique.includes(state)) unique.push(state);
  }
  if (unique.length > 1) {
    return {
      state: "ENFORCEMENT_UNKNOWN",
      reason: "health_states_disagree",
      visible_states: unique,
    };
  }
  return {
    state: unique[0],
    reason: "shared_health_observation",
    visible_states: unique,
  };
}

function requestProblems(request) {
  const attachment = [];
  const optimistic = [];
  if (request == null || typeof request !== "object" || Array.isArray(request)) {
    return { attachment, optimistic };
  }
  for (const key of ATTACHMENT_KEYS) {
    const value = request[key];
    if (value === true) attachment.push(key);
    else if (
      key === "host_attachment"
      && typeof value === "string"
      && value !== "HOST_ATTACHMENT_FALSE"
      && value !== "NOT_PERFORMED"
    ) {
      attachment.push(key);
    }
  }
  for (const key of SUCCESS_KEYS) {
    const value = request[key];
    if (value === true || value === "SUCCESS") optimistic.push(key);
  }
  if (request.collapse_missing === true) optimistic.push("collapse_missing");
  if (request.collapse_unknown === true) optimistic.push("collapse_unknown");
  if (request.collapse_unavailable === true) optimistic.push("collapse_unavailable");
  return { attachment, optimistic };
}

function requestedStates(request) {
  if (request == null || typeof request !== "object" || Array.isArray(request)) return [];
  const asked = [];
  for (const key of ["product_state", "state", "requested_state"]) {
    if (typeof request[key] === "string") asked.push(request[key]);
  }
  return asked;
}

function copyPlane(planes, name) {
  const row = planes && planes[name];
  if (!row || typeof row !== "object") return null;
  return {
    present: row.present === true,
    status: row.status,
    execution: row.execution,
    applied: row.applied === true,
    active_protection: row.active_protection === true,
    kernel_executed: row.kernel_executed === true,
    host_attachment: row.host_attachment === true,
  };
}

function absentPlanes(planes) {
  if (!planes || typeof planes !== "object") return ["SNAPSHOT_PLANES"];
  const absent = [];
  for (const name of PLANE_NAMES) {
    const row = planes[name];
    if (!row || row.present === false || row.status === "ABSENT") absent.push(name);
  }
  return absent;
}

function rollupReport(citations, token) {
  const rows = citations.filter((row) => row.token === token);
  if (rows.length === 0) return false;
  if (rows.some((row) => row.reported_as_host_enforcement === true)) return true;
  if (rows.some((row) => row.reported_as_host_enforcement == null)) return null;
  return false;
}

function anyReport(values) {
  if (values.some((value) => value === true)) return true;
  if (values.some((value) => value == null)) return null;
  return false;
}

function selectCode(honesty, shapeInvalid, attachment, optimistic) {
  if (honesty) return "HONESTY_FAULT";
  if (attachment.length > 0) return "ATTACHMENT_REFUSED";
  if (optimistic.length > 0) return "OPTIMISTIC_SUCCESS_REFUSED";
  if (shapeInvalid) return "BAD_INPUT";
  return null;
}

function planeCollapsed(plane) {
  if (!plane) return false;
  if (plane.applied === true || plane.active_protection === true || plane.kernel_executed === true) return true;
  if (plane.host_attachment === true) return true;
  if (plane.status === "APPLIED") return true;
  return COLLAPSE_TOKENS.has(plane.status);
}

function seal(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const key of Object.keys(value)) seal(value[key]);
    Object.freeze(value);
  }
  return value;
}

function composeProductHealth(runtime, options = {}) {
  const request = options.request;
  const shapeInvalid = options.request_shape === "invalid"
    || (request != null && (typeof request !== "object" || Array.isArray(request)));
  const problems = requestProblems(shapeInvalid ? null : request);
  const packet = packetFacts();
  const planes = options.planes;
  const contributions = runtime && Array.isArray(runtime.contributions) ? runtime.contributions : [];
  const citations = [];
  const unknownStates = [];
  const validStates = [];

  for (const contribution of contributions) {
    if (!contribution || typeof contribution !== "object") continue;
    const found = tokensFrom(contribution);
    for (const token of found.known) {
      const row = citation(contribution, token);
      citations.push(row);
      if (STATES.has(token)) validStates.push(token);
    }
    for (const value of found.unknown) unknownStates.push(value);
  }

  const derived = selectProductState(validStates, unknownStates);
  const asked = requestedStates(shapeInvalid ? null : request);
  for (const value of asked) {
    if (value === "SUCCESS") problems.optimistic.push("requested_state");
    else if (value !== derived.state && HEALTHY.has(value) && !HEALTHY.has(derived.state)) {
      problems.optimistic.push("requested_state");
    }
  }

  const hostSummary = copyPlane(planes, "HOST_ENFORCEMENT");
  const applicationSummary = copyPlane(planes, "APPLICATION_ENFORCEMENT");
  const absent = absentPlanes(planes);
  let honesty = citations.some((row) => row.reported_as_host_enforcement === true
    || row.reported_as_application_enforcement === true
    || row.reported_as_host_enforcement == null
    || row.green === true
    || row.proved === true);
  if (planeCollapsed(hostSummary) || planeCollapsed(applicationSummary)) honesty = true;

  const visibleEvidence = [
    { field: "freshness", value: "UNKNOWN", collapsed_to_success: false },
    {
      field: "independent_verification_status",
      value: "NOT_INDEPENDENTLY_VERIFIED",
      collapsed_to_success: false,
    },
  ];
  if (!runtime || !Array.isArray(runtime.contributions)) {
    visibleEvidence.push({ field: "contributions", evidence: "MISSING", collapsed_to_success: false });
  }
  if (derived.reason === "shared_health_record_absent") {
    visibleEvidence.push({
      field: "shared_health",
      state: "EVIDENCE_UNAVAILABLE",
      evidence: "MISSING",
      reason: derived.reason,
      collapsed_to_success: false,
    });
  }
  if (derived.reason === "health_states_disagree" || derived.reason === "unknown_health_state") {
    visibleEvidence.push({
      field: "shared_health",
      state: "ENFORCEMENT_UNKNOWN",
      evidence: "UNKNOWN",
      reason: derived.reason,
      visible_states: derived.visible_states.slice(),
      collapsed_to_success: false,
    });
  }
  for (const row of citations) {
    if (row.evidence === "MISSING" || row.evidence === "UNAVAILABLE" || row.evidence === "UNKNOWN") {
      visibleEvidence.push({
        field: "shared_health",
        token: row.token,
        state: STATES.has(row.token) ? row.token : null,
        evidence: row.evidence,
        collapsed_to_success: false,
      });
    }
    if (STATES.has(row.token) && row.failure_classification == null) {
      visibleEvidence.push({
        field: "failure_classification",
        state: row.token,
        value: null,
        collapsed_to_success: false,
      });
    }
  }
  for (const value of unknownStates) {
    visibleEvidence.push({
      field: "state",
      value,
      evidence: "UNKNOWN",
      collapsed_to_success: false,
    });
  }
  for (const name of absent) {
    visibleEvidence.push({
      field: "plane",
      plane: name,
      evidence: "MISSING",
      collapsed_to_success: false,
    });
  }
  if (packet.plane_id === "UNKNOWN" || packet.requirement_id === "UNKNOWN") {
    visibleEvidence.push({
      field: "eligible_plane",
      value: packet.plane_id,
      evidence: "UNKNOWN",
      collapsed_to_success: false,
    });
  }

  const reports = [
    rollupReport(citations, "HEALTHY_ENFORCING"),
    rollupReport(citations, "BLOCKED_HOST"),
    rollupReport(citations, "ENFORCE"),
    rollupReport(citations, "PROMOTED_MATCH"),
  ];
  const code = selectCode(honesty, shapeInvalid, problems.attachment, problems.optimistic);

  return seal({
    kind: "W3_PRODUCT_HEALTH_FAILURE_TRUTH",
    producer_classification: PRODUCER_CLASSIFICATION,
    council_status: COUNCIL_STATUS,
    council_verdict: null,
    self_certified_council_pass: false,
    audience: "INTERNAL_RESTRICTED",
    vocabulary: {
      source: "packages/shared-health-runtime/contract.json",
      states: contract.states.slice(),
      states_added: [],
    },
    ok: code == null,
    code,
    composed: true,
    product_success: false,
    success_emitted: false,
    optimistic_success: false,
    green: false,
    proved: false,
    reading_means_product_success: false,
    healthier_token_selected: false,
    requested_product_state_ignored: asked.length > 0,
    product_state: derived.state,
    rollup_reason: derived.reason,
    visible_states: derived.visible_states.slice(),
    product_plane: expectedPlane(derived.state),
    healthy_enforcing_reported_as_host_enforcement: reports[0],
    blocked_host_reported_as_host_enforcement: reports[1],
    enforce_stage_reported_as_host_enforcement: reports[2],
    promoted_match_reported_as_host_enforcement: reports[3],
    reported_as_host_enforcement: anyReport(reports),
    decision_reported_as_enforcement: anyReport(reports.slice(1)),
    missing_evidence_collapsed_to_success: false,
    unknown_evidence_collapsed_to_success: false,
    unavailable_evidence_collapsed_to_success: false,
    host_attachment: false,
    host_attachment_status: "HOST_ATTACHMENT_FALSE",
    ebpf_loaded: false,
    kernel_executed: false,
    active_protection: false,
    ceiling_raised: false,
    execution_ceiling: "HOST_ATTACHMENT_FALSE",
    preferred_execution: PREFERRED_EXECUTION,
    eligible_plane: packet.plane_id,
    named_eligible_plane: packet.named_eligible_plane,
    infra_requirement: packet.requirement_id,
    eligible_plane_packet: packet,
    host_enforcement: hostSummary,
    application_enforcement: applicationSummary,
    absent_planes: absent,
    health_observations: citations.filter((row) => STATES.has(row.token)),
    decision_citations: citations.filter((row) => DECISION_TOKENS.has(row.token)),
    visible_evidence: visibleEvidence,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
    freshness: "UNKNOWN",
    request_problems: {
      attachment: problems.attachment.slice(),
      optimistic: problems.optimistic.slice(),
    },
  });
}

module.exports = {
  INTEGRATION_REGISTER,
  PRODUCER_CLASSIFICATION,
  REGISTER_DIR,
  RUNTIME_REGISTER,
  STARTING_REF,
  composeProductHealth,
};
