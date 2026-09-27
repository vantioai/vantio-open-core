"use strict";

const { PLANES, assertNever, requestAttachment, sealChild } = require("./boundary.cjs");
const health = require("../../../packages/shared-health-runtime/src/index.cjs");
const ingress = require("../../../packages/pe-ingress-authority/src/index.cjs");
const egress = require("../../../packages/pe-egress-authority/src/index.cjs");
const { FIXTURE_HOST } = require("../../../packages/pe-host-authority/src/catalog.cjs");
const { evaluate: evaluateHost, snapshot: snapshotHost } = require("../../../packages/pe-host-authority/src/evaluate.cjs");
const sequential = require("../../../packages/pe-sequential-authority/src/index.cjs");
const progressive = require("../../../packages/pe-progressive-enforcement/src/index.cjs");
const {
  faultPlanes,
  projectEgress,
  projectHealth,
  projectHost,
  projectIngress,
  projectPolicy,
  projectProgressive,
  projectSequential,
  projectUninstall,
} = require("./project.cjs");

const VERSION_ID = /^[A-Za-z0-9._:-]{1,128}$/;

const OPS = Object.freeze([
  "health",
  "ingress",
  "egress",
  "host_contract",
  "lineage",
  "descendant_host",
  "descendant_grant",
  "sequential",
  "progressive",
  "policy_version",
  "revoke_ingress",
  "revoke_sequential",
  "rollback_ingress",
  "uninstall",
  "evidence",
]);

const PROGRESSIVE_STEPS = Object.freeze([
  "discover",
  "observe",
  "propose",
  "simulate",
  "canary",
  "promote",
  "decide",
  "review",
  "advance_rollout",
  "freeze",
  "thaw",
  "grant_exception",
  "expire_exceptions",
  "revoke_or_rollback",
  "retire",
  "verify_removal",
]);

const OP_SET = new Set(OPS);
const STEP_SET = new Set(PROGRESSIVE_STEPS);

function planeProblems(planes) {
  const problems = [];
  for (const name of PLANES) {
    const row = planes[name];
    if (!row) {
      problems.push("missing_" + name);
      continue;
    }
    for (const problem of sealChild(row)) problems.push(name + "." + problem);
    if (row.applied === true) problems.push(name + ".applied");
  }
  return problems;
}

function childProblems(child) {
  if (!child || typeof child !== "object") return [];
  const problems = sealChild(child);
  if (child.audit) problems.push(...sealChild(child.audit));
  if (child.containment) problems.push(...sealChild(child.containment));
  return problems;
}

function locks(partial) {
  return {
    ok: partial.ok,
    code: partial.code,
    capability: partial.capability,
    op: partial.op,
    planes: partial.planes,
    quote: partial.quote || null,
    policy_version: partial.policy_version || null,
    problems: partial.problems || null,
    child: partial.child,
    active_protection: false,
    host_attachment: false,
    ebpf_loaded: false,
    kernel_executed: false,
    applied_to_host: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function remember(runtime, partial, persist) {
  const contribution = locks(partial);
  if (persist) {
    runtime.seq += 1;
    const evidence = {
      evidence_id: "w3ev-" + String(runtime.seq),
      capability: contribution.capability,
      op: contribution.op,
      ok: contribution.ok,
      code: contribution.code,
      at: runtime.now(),
      independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
      active_protection: false,
    };
    runtime.evidence.push(Object.freeze(evidence));
    runtime.contributions.push(Object.freeze({
      capability: contribution.capability,
      op: contribution.op,
      ok: contribution.ok,
      code: contribution.code,
      planes: JSON.parse(JSON.stringify(contribution.planes)),
      quote: contribution.quote == null ? null : JSON.parse(JSON.stringify(contribution.quote)),
      active_protection: false,
    }));
  }
  return contribution;
}

function refuse(runtime, capability, op, code, problems, persist) {
  return remember(runtime, {
    ok: false,
    code,
    capability,
    op,
    planes: faultPlanes(),
    quote: problems ? { problems } : null,
    problems: problems || null,
    child: null,
  }, persist);
}

function finish(runtime, spec) {
  const problems = planeProblems(spec.planes).concat(childProblems(spec.child));
  if (problems.length) {
    return refuse(runtime, spec.capability, spec.op, "HONESTY_FAULT", problems, true);
  }
  return remember(runtime, spec, true);
}

function citeVersion(runtime, fields) {
  if (typeof fields.version_id !== "string" || !VERSION_ID.test(fields.version_id)) return null;
  const last = runtime.policy_versions[runtime.policy_versions.length - 1];
  if (
    last
    && last.version_id === fields.version_id
    && last.capability === fields.capability
    && last.origin === fields.origin
  ) {
    return last;
  }
  const entry = {
    version_id: fields.version_id,
    capability: fields.capability,
    digest: fields.digest || null,
    prior_version_id: fields.prior_version_id || null,
    origin: fields.origin,
    applied_to_host: false,
    kernel_maps_changed: false,
    at: runtime.now(),
  };
  const frozen = Object.freeze(entry);
  runtime.policy_versions.push(frozen);
  return frozen;
}

function ensureIngress(runtime, input) {
  if (runtime.ingress) return runtime.ingress;
  const envelope = input && typeof input === "object" ? input.envelope : null;
  runtime.ingress = ingress.openSession({
    boot_id: "w3-integrated",
    last_known_sha: envelope && envelope.last_known_sha != null ? envelope.last_known_sha : null,
    applied_sha: envelope && envelope.applied_sha != null ? envelope.applied_sha : null,
    policy_version: envelope && envelope.policy_version != null ? envelope.policy_version : null,
  });
  return runtime.ingress;
}

function quoteHealth(record) {
  return {
    state: record.state,
    freshness: record.freshness,
    independent_verification_status: record.independent_verification_status,
    green: record.audit ? record.audit.green : null,
    proved: record.audit ? record.audit.proved : null,
    live_phantom_enforcement_changed: record.audit ? record.audit.live_phantom_enforcement_changed : null,
    token_is_not_a_latch: true,
  };
}

function quoteIngress(result) {
  return {
    authority: result.authority,
    reason: result.reason,
    packet_effect: result.packet_effect,
    packet_plane: result.packet_plane,
    live_loader_mutated: result.live_loader_mutated,
    ingress_protected_claim: result.ingress_protected_claim,
    containment_effect: result.containment ? result.containment.effect : null,
    cgroup_freeze_applied: result.containment ? result.containment.cgroup_freeze_applied : null,
    idp_revoke: result.idp_revoke,
    grant_id: result.grant_id,
    policy_version: result.policy ? result.policy.version : null,
  };
}

function quoteEgress(decision) {
  return {
    result: decision.result,
    reason: decision.reason,
    path_id: decision.path_id,
    live_wire_action: decision.live_wire_action,
    would_wire_applied: false,
    this_force_executed_host: decision.this_force_executed_host,
    this_force_executed_network: decision.this_force_executed_network,
    optimistic_allow: decision.optimistic_allow,
  };
}

function quoteHost(decision) {
  return {
    disposition: decision.disposition,
    execution: decision.execution,
    kernel_executed: decision.kernel_executed,
    mechanism_id: decision.mechanism_id,
    cited_effect: decision.effect || null,
    cited_effect_applied: false,
    authority_widened: decision.authority_widened,
    maps_changed: Object.prototype.hasOwnProperty.call(decision, "maps_changed") ? decision.maps_changed : null,
    kernel_activated: Object.prototype.hasOwnProperty.call(decision, "kernel_activated") ? decision.kernel_activated : null,
  };
}

function quoteSequential(result) {
  return {
    disposition: result.disposition,
    reason: result.reason,
    invariant: result.invariant,
    axis: result.axis,
    enforcement: result.enforcement,
    host_attachment: result.host_attachment,
    doctrine_present: result.doctrine_present,
    revoked_ids: result.revoked_ids || null,
  };
}

function quoteProgressive(result) {
  return {
    ok: result.ok,
    code: result.code || null,
    stage: result.stage || result.lifecycle_stage || null,
    decision_class: result.decision_class || null,
    host_attachment: result.host_attachment,
    live_enforcement: result.live_enforcement,
    enforcement_attached: result.enforcement_attached,
    applied_to_host: Object.prototype.hasOwnProperty.call(result, "applied_to_host") ? result.applied_to_host : false,
    auto_promoted: result.auto_promoted,
    evidence_id: result.evidence_id || null,
  };
}

function runHealth(runtime, request) {
  const record = health.produce(request.input || {}, request.options || {});
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "shared_health",
    op: "health",
    planes: projectHealth(record),
    child: record,
    quote: quoteHealth(record),
  });
}

function runIngress(runtime, request) {
  const input = request.input && typeof request.input === "object" ? structuredClone(request.input) : request.input;
  const session = ensureIngress(runtime, input);
  const result = ingress.evaluateIngress(input, session);
  const version = result.policy && result.policy.version
    ? citeVersion(runtime, {
      version_id: String(result.policy.version),
      capability: "ingress",
      origin: "ingress_decision",
      digest: result.policy.sha || null,
    })
    : null;
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "ingress",
    op: "ingress",
    planes: projectIngress(result),
    child: result,
    quote: quoteIngress(result),
    policy_version: version,
  });
}

function runEgress(runtime, request) {
  const decision = egress.evaluate(request.input);
  return finish(runtime, {
    ok: true,
    code: null,
    capability: decision.path_id && String(decision.path_id).startsWith("host_") ? "egress_host" : "egress_application",
    op: "egress",
    planes: projectEgress(decision),
    child: decision,
    quote: quoteEgress(decision),
  });
}

function runHost(runtime, request, capability) {
  const attempt = request.attempt;
  if (!attempt || typeof attempt !== "object") return refuse(runtime, capability, request.op, "BAD_INPUT", null, true);
  if (attempt.surface === "evidence_tampering") {
    return refuse(runtime, capability, request.op, "NOT_WIRED", ["prove_not_called"], true);
  }
  if (capability === "descendant_host" && attempt.surface !== "descendants") {
    return refuse(runtime, capability, request.op, "SURFACE_REFUSED", null, true);
  }
  const host = structuredClone(request.host || FIXTURE_HOST);
  const before = snapshotHost(host);
  let decision;
  try {
    decision = evaluateHost(host, attempt);
  } catch (error) {
    return refuse(runtime, capability, request.op, "EVALUATOR_REJECTED", [error.message], true);
  }
  if (snapshotHost(host) !== before) {
    return refuse(runtime, capability, request.op, "HONESTY_FAULT", ["host_mutated"], true);
  }
  let version = null;
  if (decision.disposition === "ACCEPTED_CONTRACT_RECORD_ONLY" && decision.version) {
    version = citeVersion(runtime, {
      version_id: String(decision.version),
      capability: "host_authority",
      origin: "host_contract_citation",
    });
  }
  return finish(runtime, {
    ok: true,
    code: null,
    capability,
    op: request.op,
    planes: projectHost(decision),
    child: decision,
    quote: quoteHost(decision),
    policy_version: version,
  });
}

function runSequential(runtime, request, capability) {
  const result = sequential.evaluate(request.input);
  return finish(runtime, {
    ok: true,
    code: null,
    capability,
    op: request.op,
    planes: projectSequential(result),
    child: result,
    quote: quoteSequential(result),
  });
}

function runDescendantGrant(runtime, request) {
  const result = sequential.proposeDelegation(request.parent, request.request);
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "descendant_grant",
    op: "descendant_grant",
    planes: projectSequential(result),
    child: result,
    quote: quoteSequential(result),
  });
}

function callProgressive(engine, step, input) {
  switch (step) {
    case "discover":
      return progressive.discover(engine, input);
    case "observe":
      return progressive.observe(engine, input);
    case "propose":
      return progressive.propose(engine, input);
    case "simulate":
      return progressive.simulate(engine, input);
    case "canary":
      return progressive.canary(engine, input);
    case "promote":
      return progressive.promote(engine, input);
    case "decide":
      return progressive.decide(engine, input);
    case "review":
      return progressive.review(engine, input);
    case "advance_rollout":
      return progressive.advanceRollout(engine, input);
    case "freeze":
      return progressive.freeze(engine, input);
    case "thaw":
      return progressive.thaw(engine, input);
    case "grant_exception":
      return progressive.grantException(engine, input);
    case "expire_exceptions":
      return progressive.expireDueExceptions(engine, input);
    case "revoke_or_rollback":
      throw new Error("revoke_or_rollback is dispatched before callProgressive");
    case "retire":
      return progressive.retire(engine, input);
    case "verify_removal":
      return progressive.verifyRemoval(engine, input);
    default:
      return assertNever(step);
  }
}

function runProgressive(runtime, request) {
  if (!STEP_SET.has(request.step)) return refuse(runtime, "progressive", "progressive", "UNKNOWN_STEP", null, true);
  if (request.step === "revoke_or_rollback") {
    if (request.input == null || (request.input.lifecycle_op !== "rollback" && request.input.lifecycle_op !== "revoke")) {
      return refuse(runtime, "progressive", "progressive", "BAD_INPUT", null, true);
    }
  }
  let result;
  try {
    if (request.step === "revoke_or_rollback") {
      result = progressive.revokeOrRollback(runtime.progressive, request.input, request.input.lifecycle_op);
    } else {
      result = callProgressive(runtime.progressive, request.step, request.input);
    }
  } catch (error) {
    return refuse(runtime, "progressive", "progressive", "EVALUATOR_REJECTED", [error.message], true);
  }
  return finish(runtime, {
    ok: result.ok === true,
    code: result.ok === true ? null : (result.code || "REFUSED"),
    capability: "progressive",
    op: "progressive:" + request.step,
    planes: projectProgressive(result),
    child: result,
    quote: quoteProgressive(result),
  });
}

function runPolicy(runtime, request) {
  const input = request.input;
  if (!input || typeof input !== "object") return refuse(runtime, "policy_versioning", "policy_version", "BAD_INPUT", null, true);
  if (input.applied_to_host === true || input.kernel_maps_changed === true || input.attach_host === true) {
    return refuse(runtime, "policy_versioning", "policy_version", "ATTACHMENT_REFUSED", null, true);
  }
  const entry = citeVersion(runtime, {
    version_id: input.version_id,
    capability: input.capability || "policy_versioning",
    origin: "recorded",
    digest: typeof input.digest === "string" ? input.digest : null,
    prior_version_id: typeof input.prior_version_id === "string" ? input.prior_version_id : null,
  });
  if (!entry) return refuse(runtime, "policy_versioning", "policy_version", "BAD_VERSION", null, true);
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "policy_versioning",
    op: "policy_version",
    planes: projectPolicy(),
    child: entry,
    quote: {
      version_id: entry.version_id,
      applied_to_host: false,
      kernel_maps_changed: false,
    },
    policy_version: entry,
  });
}

function runRevokeIngress(runtime, request) {
  if (!runtime.ingress) return refuse(runtime, "revocation", "revoke_ingress", "SESSION_ABSENT", null, true);
  const result = ingress.revokeActive(runtime.ingress, request.grant_id);
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "revocation",
    op: "revoke_ingress",
    planes: projectIngress(result),
    child: result,
    quote: quoteIngress(result),
  });
}

function runRevokeSequential(runtime, request) {
  const result = sequential.revoke(request.catalog, request.ledger, request.envelope_id, request.now);
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "revocation",
    op: "revoke_sequential",
    planes: projectSequential(result),
    child: result,
    quote: quoteSequential(result),
  });
}

function runRollbackIngress(runtime) {
  if (!runtime.ingress) return refuse(runtime, "rollback", "rollback_ingress", "SESSION_ABSENT", null, true);
  const result = ingress.rollbackSession(runtime.ingress);
  const version = result.policy && result.policy.version
    ? citeVersion(runtime, {
      version_id: String(result.policy.version),
      capability: "ingress",
      origin: "ingress_rollback",
      digest: result.policy.sha || null,
    })
    : null;
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "rollback",
    op: "rollback_ingress",
    planes: projectIngress(result),
    child: result,
    quote: quoteIngress(result),
    policy_version: version,
  });
}

function runUninstall(runtime, request) {
  const input = request.input || {};
  if (input.performed === true || input.execute === true || input.delete === true || input.detach_host === true) {
    return refuse(runtime, "uninstall", "uninstall", "NOT_PERFORMED", ["uninstall_execution_refused"], true);
  }
  runtime.uninstall = Object.freeze({
    status: "RECORDED_NOT_PERFORMED",
    performed: false,
    files_removed: false,
    host_detached: false,
    reason: typeof input.reason === "string" ? input.reason : null,
  });
  return finish(runtime, {
    ok: true,
    code: null,
    capability: "uninstall",
    op: "uninstall",
    planes: projectUninstall(),
    child: runtime.uninstall,
    quote: runtime.uninstall,
  });
}

function runEvidence(runtime) {
  return remember(runtime, {
    ok: true,
    code: null,
    capability: "evidence",
    op: "evidence",
    planes: (() => {
      const planes = faultPlanes();
      planes.DECISION = {
        present: false,
        status: "ABSENT",
        execution: null,
        active_protection: false,
        kernel_executed: false,
        host_attachment: false,
        applied: false,
      };
      planes.EVIDENCE = {
        present: true,
        status: "RECORDED",
        execution: "NOT_PERFORMED",
        active_protection: false,
        kernel_executed: false,
        host_attachment: false,
        applied: false,
      };
      return planes;
    })(),
    quote: {
      count: runtime.evidence.length,
      independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
    },
    child: runtime.evidence.slice(),
  }, false);
}

function integrate(runtime, request) {
  if (!runtime || runtime.kind !== "PE_INTEGRATED_RUNTIME") {
    throw new Error("integrate requires a runtime from createRuntime");
  }
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    return refuse(runtime, "runtime", "integrate", "BAD_INPUT", null, true);
  }
  const attached = requestAttachment(request);
  if (attached.length) return refuse(runtime, "runtime", request.op || "integrate", "ATTACHMENT_REFUSED", attached, true);
  if (!OP_SET.has(request.op)) return refuse(runtime, "runtime", "integrate", "UNKNOWN_OP", null, true);
  switch (request.op) {
    case "health":
      return runHealth(runtime, request);
    case "ingress":
      return runIngress(runtime, request);
    case "egress":
      return runEgress(runtime, request);
    case "host_contract":
      return runHost(runtime, request, "host_authority");
    case "lineage":
      return runSequential(runtime, request, "process_lineage");
    case "descendant_host":
      return runHost(runtime, request, "descendant_host");
    case "descendant_grant":
      return runDescendantGrant(runtime, request);
    case "sequential":
      return runSequential(runtime, request, "sequential_aggregate");
    case "progressive":
      return runProgressive(runtime, request);
    case "policy_version":
      return runPolicy(runtime, request);
    case "revoke_ingress":
      return runRevokeIngress(runtime, request);
    case "revoke_sequential":
      return runRevokeSequential(runtime, request);
    case "rollback_ingress":
      return runRollbackIngress(runtime);
    case "uninstall":
      return runUninstall(runtime, request);
    case "evidence":
      return runEvidence(runtime);
    default:
      return assertNever(request.op);
  }
}

function integrateAll(runtime, steps) {
  if (!Array.isArray(steps)) return refuse(runtime, "runtime", "compose", "BAD_INPUT", null, true);
  const contributions = [];
  for (const step of steps) {
    const contribution = integrate(runtime, step);
    contributions.push(contribution);
    if (contribution.code === "ATTACHMENT_REFUSED" || contribution.code === "HONESTY_FAULT") break;
  }
  const view = snapshot(runtime);
  return {
    ok: contributions.every((item) => item.ok),
    contributions,
    snapshot: view,
    active_protection: false,
    host_attachment: false,
    ebpf_loaded: false,
    kernel_executed: false,
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
    if (row && row.present && row.status !== "ABSENT") present.push(row);
    if (row && (row.applied === true || row.active_protection === true || row.kernel_executed === true || row.host_attachment === true)) {
      throw new Error("snapshot refused an applied plane");
    }
  }
  if (name === "HOST_ENFORCEMENT" || name === "APPLICATION_ENFORCEMENT") {
    if (present.length === 0) return absent;
    const gap = present.some((row) => row.status === "GAP");
    const executions = new Set(present.map((row) => row.execution));
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

function snapshot(runtime) {
  const planes = {};
  for (const name of PLANES) planes[name] = aggregatePlane(name, runtime.contributions);
  return {
    kind: "PE_INTEGRATED_RUNTIME_SNAPSHOT",
    producer_classification: "W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL",
    council_status: "PENDING_INDEPENDENT_COUNCIL",
    council_verdict: null,
    planes,
    quotes: runtime.contributions.map((item) => ({
      capability: item.capability,
      op: item.op,
      ok: item.ok,
      code: item.code,
      quote: item.quote,
    })),
    policy_versions: runtime.policy_versions.map((entry) => ({ ...entry, applied_to_host: false, kernel_maps_changed: false })),
    uninstall: runtime.uninstall,
    evidence_count: runtime.evidence.length,
    in_process_promoted_rule_ids: progressive.activeEnforcement(runtime.progressive),
    in_process_promoted_rules_are_host_enforcement: false,
    active_protection: false,
    host_attachment: false,
    host_attachment_status: "HOST_ATTACHMENT_FALSE",
    ebpf_loaded: false,
    loader_mutated: false,
    kernel_executed: false,
    customer_deployed: false,
    clean_host_internal_proof: false,
    proved_external: false,
    independent_verification_status: "NOT_INDEPENDENTLY_VERIFIED",
  };
}

function createRuntime(options = {}) {
  const now = typeof options.now === "function" ? options.now : () => 0;
  return {
    kind: "PE_INTEGRATED_RUNTIME",
    now,
    seq: 0,
    ingress: null,
    progressive: progressive.createEngine({ now }),
    policy_versions: [],
    evidence: [],
    contributions: [],
    uninstall: {
      status: "NOT_REQUESTED",
      performed: false,
      files_removed: false,
      host_detached: false,
    },
    host_attachment: false,
    ebpf_loaded: false,
    active_protection: false,
  };
}

module.exports = {
  OPS,
  PROGRESSIVE_STEPS,
  createRuntime,
  integrate,
  integrateAll,
  snapshot,
};
