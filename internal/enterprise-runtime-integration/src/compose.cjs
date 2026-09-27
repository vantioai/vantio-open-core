"use strict";

const crypto = require("node:crypto");

const eg = require("../../enterprise-governance/src/index.cjs");
const pe = require("../../pe-integrated-runtime/src/index.cjs");
const { sealChild } = require("../../pe-integrated-runtime/src/boundary.cjs");
const {
  PLANES,
  assertNever,
  promotionHits,
  sealEnterpriseChild,
} = require("./boundary.cjs");
const {
  enforcementRow,
  faultPlanes,
  joinPlanes,
  projectEnterprise,
  quoteEnterprise,
} = require("./project.cjs");

const OPS = Object.freeze([
  "accept_identity",
  "found_root",
  "recognize_customer",
  "change_owner_set",
  "name_recovery_party",
  "remove_witness",
  "policy",
  "grant",
  "clock",
  "spawn",
  "host_intent",
  "quote_host",
  "freeze",
  "revoke_grant",
  "recover",
  "rollback_intent",
  "uninstall_intent",
  "export_evidence",
  "hash_evidence",
  "inspect",
  "billing_or_support",
  "set_store_available",
  "leave_material",
  "refuse_host_mark",
  "refuse_second_engine",
  "refuse_dry_run",
  "refuse_breakglass",
  "cite_policy",
  "pe",
]);

const OP_SET = new Set(OPS);
const STOP = new Set(["PROMOTION_REFUSED", "ATTACHMENT_REFUSED", "HONESTY_FAULT"]);

const CAPABILITY = Object.freeze({
  accept_identity: "enterprise_e1_title",
  found_root: "enterprise_e1_title",
  recognize_customer: "enterprise_e1_title",
  change_owner_set: "enterprise_e1_title",
  name_recovery_party: "enterprise_e1_title",
  remove_witness: "enterprise_e1_title",
  policy: "enterprise_e2_delegation",
  grant: "enterprise_e2_delegation",
  clock: "enterprise_e2_delegation",
  spawn: "enterprise_e2_delegation",
  host_intent: "enterprise_host_intent",
  quote_host: "enterprise_e3_approval",
  freeze: "enterprise_e3_approval",
  revoke_grant: "enterprise_e3_approval",
  recover: "enterprise_e3_approval",
  inspect: "enterprise_e3_approval",
  billing_or_support: "enterprise_e3_approval",
  refuse_host_mark: "enterprise_e3_approval",
  refuse_second_engine: "enterprise_e3_approval",
  refuse_dry_run: "enterprise_e3_approval",
  refuse_breakglass: "enterprise_e3_approval",
  rollback_intent: "enterprise_record_store",
  uninstall_intent: "enterprise_record_store",
  export_evidence: "enterprise_record_store",
  hash_evidence: "enterprise_record_store",
  set_store_available: "enterprise_record_store",
  leave_material: "enterprise_record_store",
  cite_policy: "policy_citation",
  pe: "pe_integrated_runtime",
});

function locks(partial) {
  return {
    ok: partial.ok,
    code: partial.code,
    capability: partial.capability,
    op: partial.op,
    layer: partial.layer,
    planes: partial.planes,
    quote: partial.quote || null,
    child: partial.child == null ? null : partial.child,
    problems: partial.problems || null,
    record_layer_only: true,
    live_customer_authority: false,
    customer_authority_promoted: false,
    host_attachment: false,
    kernel_executed: false,
    ebpf_loaded: false,
    active_protection: false,
    applied_to_host: false,
    published: false,
    announced: false,
    frozen_version_reopened: false,
    credentials_issued: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function remember(composition, partial, persist) {
  const contribution = locks(partial);
  if (persist) {
    composition.seq += 1;
    composition.evidence.push(Object.freeze({
      evidence_id: "w3eg-" + String(composition.seq),
      capability: contribution.capability,
      op: contribution.op,
      ok: contribution.ok,
      code: contribution.code,
      at: composition.now(),
      live_customer_authority: false,
      independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
    }));
    composition.contributions.push(Object.freeze({
      capability: contribution.capability,
      op: contribution.op,
      layer: contribution.layer,
      ok: contribution.ok,
      code: contribution.code,
      planes: JSON.parse(JSON.stringify(contribution.planes)),
      active_protection: false,
      host_attachment: false,
      live_customer_authority: false,
    }));
  }
  return contribution;
}

function refuse(composition, capability, op, code, problems, persist) {
  return remember(composition, {
    ok: false,
    code,
    capability,
    op,
    layer: "enterprise",
    planes: faultPlanes(),
    quote: problems ? { problems, record_layer_only: true, live_customer_authority: false } : null,
    problems: problems || null,
    child: null,
  }, persist);
}

function planeProblems(planes) {
  const problems = [];
  if (!planes || typeof planes !== "object") return ["planes_missing"];
  for (const name of PLANES) {
    const row = planes[name];
    if (!row) {
      problems.push("missing_" + name);
      continue;
    }
    for (const problem of sealChild(row)) problems.push(name + "." + problem);
    if (row.applied === true) problems.push(name + ".applied");
    if (row.status === "APPLIED") problems.push(name + ".status");
  }
  return problems;
}

function finishEnterprise(composition, op, result) {
  const capability = CAPABILITY[op];
  const planes = projectEnterprise(op, result);
  const problems = planeProblems(planes)
    .concat(sealEnterpriseChild(result))
    .concat(result && result.intent ? sealEnterpriseChild(result.intent) : []);
  if (problems.length) return refuse(composition, capability, op, "HONESTY_FAULT", problems, true);
  return remember(composition, {
    ok: true,
    code: null,
    capability,
    op,
    layer: "enterprise",
    planes,
    quote: quoteEnterprise(result),
    child: result,
  }, true);
}

function plainInput(request) {
  if (!Object.prototype.hasOwnProperty.call(request, "input") || request.input == null) return {};
  if (typeof request.input !== "object" || Array.isArray(request.input)) return null;
  return request.input;
}

function withStore(composition, input) {
  if (input.store && input.store !== composition.store) return null;
  return Object.assign({}, input, { store: composition.store });
}

function dispatchEnterprise(composition, op, input) {
  switch (op) {
    case "accept_identity":
      return eg.acceptOpaqueIdentity(composition.store, input);
    case "found_root":
      return eg.foundRoot(composition.store, input);
    case "recognize_customer":
      return eg.recordRecognizedCustomer(composition.store, input);
    case "change_owner_set":
      return eg.changeOwnerSet(composition.store, input);
    case "name_recovery_party":
      return eg.nameRecoveryParty(composition.store, input);
    case "remove_witness":
      return eg.removeWitness(composition.store, input);
    case "policy":
      return eg.recordPolicyDecision(composition.store, input);
    case "grant":
      return eg.proposeGrant(composition.store, input);
    case "clock":
      return eg.noteClock(composition.store, input);
    case "spawn":
      return eg.noteSpawn(composition.store, input);
    case "host_intent":
      return eg.recordHostIntent(composition.store, input);
    case "quote_host":
      return eg.quoteHostReport(composition.store, input);
    case "freeze":
      return eg.recordFreeze(input);
    case "revoke_grant":
      return eg.revokeGrant(composition.store, input);
    case "recover":
      return eg.recover(input);
    case "rollback_intent":
      return eg.recordRollbackIntent(composition.store, input);
    case "uninstall_intent":
      return eg.recordUninstallIntent(composition.store, input);
    case "export_evidence":
      return eg.exportEvidence(composition.store, input);
    case "hash_evidence":
      return eg.hashEvidence(composition.store, input);
    case "inspect":
      return eg.inspect(composition.store, input);
    case "billing_or_support":
      return eg.applyBillingOrSupport(composition.store, input);
    case "set_store_available":
      return eg.setRecordStoreAvailable(composition.store, input.available);
    case "leave_material":
      return eg.leaveFromCustomerHeldMaterial(input);
    case "refuse_host_mark":
      return eg.refuseHostMark();
    case "refuse_second_engine":
      return eg.refuseSecondEnforcementEngine();
    case "refuse_dry_run":
      return eg.refuseDryRunActivation();
    case "refuse_breakglass":
      return eg.refuseBreakglass();
    case "cite_policy":
    case "pe":
      return assertNever(op);
    default:
      return assertNever(op);
  }
}

function quotePe(result) {
  const src = result.quote && typeof result.quote === "object" ? result.quote : {};
  return {
    state: src.state || null,
    result: src.result || null,
    authority: src.authority || null,
    disposition: src.disposition || null,
    reason: src.reason || null,
    version_id: src.version_id || null,
    packet_effect: src.packet_effect || null,
    live_wire_action: src.live_wire_action || null,
    would_wire_applied: false,
    applied_to_host: false,
    kernel_maps_changed: false,
    live_customer_authority: false,
    customer_authority_promoted: false,
    record_layer_only: true,
    this_force_executed_host: false,
    this_force_executed_network: false,
    kernel_executed: false,
    host_attachment: false,
    active_protection: false,
  };
}

function peQuoteProblems(result) {
  const src = result.quote && typeof result.quote === "object" ? result.quote : {};
  const problems = [];
  if (src.would_wire_applied === true) problems.push("would_wire_applied");
  if (src.applied_to_host === true) problems.push("quote.applied_to_host");
  if (src.kernel_executed === true) problems.push("quote.kernel_executed");
  if (src.kernel_maps_changed === true) problems.push("quote.kernel_maps_changed");
  if (src.this_force_executed_host === true) problems.push("quote.this_force_executed_host");
  if (src.this_force_executed_network === true) problems.push("quote.this_force_executed_network");
  if (result.applied_to_host === true) problems.push("applied_to_host");
  if (result.host_attachment === true) problems.push("host_attachment");
  if (result.kernel_executed === true) problems.push("kernel_executed");
  if (result.active_protection === true) problems.push("active_protection");
  if (result.ebpf_loaded === true) problems.push("ebpf_loaded");
  if (result.live_customer_authority === true) problems.push("live_customer_authority");
  return problems;
}

function runPe(composition, request) {
  if (!request.pe || typeof request.pe !== "object" || Array.isArray(request.pe)) {
    return refuse(composition, "pe_integrated_runtime", "pe", "BAD_INPUT", null, true);
  }
  const result = pe.integrate(composition.pe, request.pe);
  const problems = planeProblems(result.planes)
    .concat(sealEnterpriseChild(result))
    .concat(sealChild(result.child))
    .concat(peQuoteProblems(result));
  if (problems.length) {
    return refuse(composition, result.capability || "pe_integrated_runtime", "pe:" + (request.pe.op || "integrate"), "HONESTY_FAULT", problems, true);
  }
  return remember(composition, {
    ok: result.ok === true,
    code: result.code || null,
    capability: result.capability || "pe_integrated_runtime",
    op: "pe:" + (request.pe.op || "integrate"),
    layer: "pe",
    planes: result.planes,
    quote: quotePe(result),
    child: result.child,
  }, true);
}

function runCite(composition) {
  const view = eg.snapshot(composition.store);
  if (!view.title_holder || !view.policy) {
    return refuse(composition, "policy_citation", "cite_policy", "ROOT_ABSENT", null, true);
  }
  if (view.host_enrolled !== false || view.host_protected !== false || view.host_enforced !== false) {
    return refuse(composition, "policy_citation", "cite_policy", "HONESTY_FAULT", ["enterprise_host_flag"], true);
  }
  const versionId = "eg-policy-" + String(view.policy_version);
  const digest = crypto.createHash("sha256").update(JSON.stringify(view.policy)).digest("hex");
  const result = pe.integrate(composition.pe, {
    op: "policy_version",
    input: {
      version_id: versionId,
      capability: "enterprise_record_citation",
      digest,
      applied_to_host: false,
      kernel_maps_changed: false,
    },
  });
  const problems = planeProblems(result.planes).concat(peQuoteProblems(result));
  if (problems.length || result.ok !== true) {
    return refuse(
      composition,
      "policy_citation",
      "cite_policy",
      problems.length ? "HONESTY_FAULT" : (result.code || "CITATION_REFUSED"),
      problems,
      true,
    );
  }
  const quote = quotePe(result);
  quote.outcome = "RECORDED";
  quote.reason = "ENTERPRISE_RECORD_CITED";
  quote.digest = digest;
  quote.citation_is_not_a_proof = true;
  quote.certification = false;
  quote.policy_version = view.policy_version;
  return remember(composition, {
    ok: true,
    code: null,
    capability: "policy_citation",
    op: "cite_policy",
    layer: "citation",
    planes: result.planes,
    quote,
    child: result.child,
  }, true);
}

function integrate(composition, request) {
  if (!composition || composition.kind !== "W3_ENTERPRISE_RUNTIME_COMPOSITION") {
    throw new Error("integrate requires a composition from createComposition");
  }
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    return refuse(composition, "runtime", "integrate", "BAD_INPUT", null, true);
  }
  const promoted = promotionHits(request);
  if (promoted.length) {
    return refuse(composition, "runtime", request.op || "integrate", "PROMOTION_REFUSED", promoted, true);
  }
  if (!OP_SET.has(request.op)) return refuse(composition, "runtime", "integrate", "UNKNOWN_OP", null, true);
  if (request.op === "pe") return runPe(composition, request);
  if (request.op === "cite_policy") return runCite(composition);
  const input = plainInput(request);
  if (input == null) return refuse(composition, CAPABILITY[request.op], request.op, "BAD_INPUT", null, true);
  let bound = input;
  if (request.op === "freeze" || request.op === "recover") {
    bound = withStore(composition, input);
    if (!bound) return refuse(composition, CAPABILITY[request.op], request.op, "STORE_MISMATCH", null, true);
  }
  if (request.op === "set_store_available" && typeof bound.available !== "boolean") {
    return refuse(composition, CAPABILITY[request.op], request.op, "BAD_INPUT", null, true);
  }
  const result = dispatchEnterprise(composition, request.op, bound);
  return finishEnterprise(composition, request.op, result);
}

function separationOf(planes) {
  return {
    observation: planes.OBSERVATION.status,
    decision: planes.DECISION.status,
    application_enforcement: planes.APPLICATION_ENFORCEMENT.status,
    host_enforcement: planes.HOST_ENFORCEMENT.status,
  };
}

function compose(composition, request) {
  if (!composition || composition.kind !== "W3_ENTERPRISE_RUNTIME_COMPOSITION") {
    throw new Error("compose requires a composition from createComposition");
  }
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    return refuse(composition, "runtime", "compose", "BAD_INPUT", null, true);
  }
  const promoted = promotionHits(request);
  if (promoted.length) {
    return refuse(composition, "runtime", "compose", "PROMOTION_REFUSED", promoted, true);
  }
  if (!request.enterprise || typeof request.enterprise !== "object") {
    return refuse(composition, "runtime", "compose", "BAD_INPUT", null, true);
  }
  const enterprise = integrate(composition, request.enterprise);
  let peResult = null;
  if (enterprise.ok === true && request.pe) {
    peResult = integrate(composition, { op: "pe", pe: request.pe });
  }
  const planes = joinPlanes(enterprise.planes, peResult ? peResult.planes : null);
  const problems = planeProblems(planes);
  const stopped = STOP.has(enterprise.code) || (peResult && STOP.has(peResult.code)) || problems.length > 0;
  const ok = !stopped && enterprise.ok === true && (peResult == null || peResult.ok === true);
  return {
    ok,
    code: problems.length ? "HONESTY_FAULT" : (enterprise.ok ? (peResult && peResult.ok === false ? peResult.code : null) : enterprise.code),
    enterprise,
    pe: peResult,
    planes,
    separation: separationOf(planes),
    record_layer_only: true,
    live_customer_authority: false,
    customer_authority_promoted: false,
    host_attachment: false,
    kernel_executed: false,
    ebpf_loaded: false,
    active_protection: false,
    applied_to_host: false,
    published: false,
    announced: false,
    frozen_version_reopened: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function integrateAll(composition, steps) {
  if (!Array.isArray(steps)) return refuse(composition, "runtime", "compose", "BAD_INPUT", null, true);
  const contributions = [];
  for (const step of steps) {
    const contribution = integrate(composition, step);
    contributions.push(contribution);
    if (STOP.has(contribution.code)) break;
  }
  const view = snapshot(composition);
  return {
    ok: contributions.every((item) => item.ok),
    contributions,
    snapshot: view,
    record_layer_only: true,
    live_customer_authority: false,
    customer_authority_promoted: false,
    host_attachment: false,
    kernel_executed: false,
    active_protection: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function aggregatePlane(name, contributions) {
  const absent = {
    present: false,
    status: "ABSENT",
    execution: null,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
  if (name === "INDEPENDENT_VERIFICATION") {
    return {
      present: true,
      status: "NOT_INDEPENDENTLY_VERIFIED",
      execution: "NOT_PERFORMED",
      active_protection: false,
      kernel_executed: false,
      host_attachment: false,
      applied: false,
    };
  }
  const present = [];
  for (const item of contributions) {
    const row = item.planes[name];
    if (row && (row.applied === true || row.active_protection === true || row.kernel_executed === true || row.host_attachment === true || row.status === "APPLIED")) {
      throw new Error("snapshot refused an applied plane");
    }
    if (row && row.present && row.status !== "ABSENT") present.push(row);
  }
  if (name === "HOST_ENFORCEMENT" || name === "APPLICATION_ENFORCEMENT") {
    return enforcementRow(present, name);
  }
  if (present.length === 0) return absent;
  return {
    present: true,
    status: "RECORDED",
    execution: present[present.length - 1].execution,
    active_protection: false,
    kernel_executed: false,
    host_attachment: false,
    applied: false,
  };
}

function snapshot(composition) {
  if (!composition || composition.kind !== "W3_ENTERPRISE_RUNTIME_COMPOSITION") {
    throw new Error("snapshot requires a composition from createComposition");
  }
  const planes = {};
  for (const name of PLANES) planes[name] = aggregatePlane(name, composition.contributions);
  const enterpriseView = eg.snapshot(composition.store);
  const peView = pe.snapshot(composition.pe);
  if (enterpriseView.host_enrolled !== false || enterpriseView.host_protected !== false || enterpriseView.host_enforced !== false) {
    throw new Error("snapshot refused an enterprise host flag");
  }
  if (peView.host_attachment !== false || peView.kernel_executed !== false || peView.active_protection !== false || peView.ebpf_loaded !== false) {
    throw new Error("snapshot refused a runtime host flag");
  }
  return {
    kind: "W3_ENTERPRISE_RUNTIME_SNAPSHOT",
    producer_classification: "W3_ENTERPRISE_RUNTIME_INTEGRATION_READY_FOR_COUNCIL",
    council_status: "PENDING_INDEPENDENT_COUNCIL",
    council_verdict: null,
    self_certified_council_pass: false,
    record_layer_only: true,
    wave2_close: "ENTERPRISE_E1_E3_INTERNAL_MERGED_RECORD_LAYER_ONLY_NO_LIVE_CUSTOMER_AUTHORITY",
    live_customer_authority: false,
    customer_authority_promoted: false,
    published: false,
    announced: false,
    frozen_version_reopened: false,
    planes,
    separation: separationOf(planes),
    enterprise: {
      title_holder: enterpriseView.title_holder,
      policy_version: enterpriseView.policy_version,
      grant_count: enterpriseView.grant_count,
      host_enrolled: false,
      host_protected: false,
      host_enforced: false,
      identity_provider_selected: false,
      grant_states: enterpriseView.active_grant_states,
    },
    pe: {
      producer_classification: peView.producer_classification,
      host_attachment: false,
      host_attachment_status: "HOST_ATTACHMENT_FALSE",
      kernel_executed: false,
      ebpf_loaded: false,
      active_protection: false,
      policy_versions: peView.policy_versions,
      planes: peView.planes,
    },
    evidence_count: composition.evidence.length,
    host_attachment: false,
    host_attachment_status: "HOST_ATTACHMENT_FALSE",
    ebpf_loaded: false,
    loader_mutated: false,
    kernel_executed: false,
    customer_deployed: false,
    credentials_issued: false,
    clean_host_internal_proof: false,
    proved_external: false,
    active_protection: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function createComposition(options = {}) {
  const now = typeof options.now === "function" ? options.now : () => 0;
  const store = options.store || eg.createCustomerHeldStore();
  if (!store || store.marker !== "customer-held-enterprise-record") {
    throw new Error("createComposition requires a customer-held enterprise store");
  }
  return {
    kind: "W3_ENTERPRISE_RUNTIME_COMPOSITION",
    now,
    seq: 0,
    store,
    pe: options.pe || pe.createRuntime({ now }),
    contributions: [],
    evidence: [],
    live_customer_authority: false,
    customer_authority_promoted: false,
    host_attachment: false,
    kernel_executed: false,
    ebpf_loaded: false,
    active_protection: false,
    published: false,
    announced: false,
    frozen_version_reopened: false,
    credentials_issued: false,
  };
}

module.exports = {
  OPS,
  compose,
  createComposition,
  integrate,
  integrateAll,
  snapshot,
};
