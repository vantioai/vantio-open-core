"use strict";

const { resolvePath } = require("./paths.cjs");
const { readPolicy } = require("./policy.cjs");
const {
  applyLatch,
  createContext,
  emit,
  isPlain,
  mark,
  own,
  readDestination,
} = require("./decision.cjs");
const {
  checkBypass,
  checkCredential,
  checkDescendant,
  checkDestination,
  checkDirectSocket,
  checkDns,
  checkHttp,
  checkPattern,
  checkProtocolPort,
  checkRedirect,
  checkResource,
  checkRetryChannel,
  checkSensitive,
  checkSize,
  checkSpend,
  checkTls,
  markUnsetClear,
  pathSees,
  readHostObservation,
} = require("./checks.cjs");

function evaluateInner(ctx, input) {
  if (!isPlain(input)) return emit(ctx, "UNKNOWN", "malformed_case");
  if (own(input, "result") || own(input, "success")) return emit(ctx, "UNKNOWN", "smuggled_result");

  const path = resolvePath(input.path);
  if (!path) return emit(ctx, "UNKNOWN", "unknown_path");
  ctx.path = path;
  mark(ctx, "path_support", path.support === "unsupported" ? "unsupported" : "clear", path.id);

  if (path.support === "unsupported") {
    return emit(ctx, "UNSUPPORTED", "path_declared_unsupported", { authority: "UNSUPPORTED" });
  }
  if (path.support === "gap") {
    mark(ctx, "bypass", "gap", path.id);
    return emit(ctx, "ENFORCEMENT_GAP", "application_path_bypass", { authority: "DENIED", would: "DENIED" });
  }

  const policyRead = readPolicy(input.policy);
  if (!policyRead.ok) return emit(ctx, policyRead.result, policyRead.reason);
  ctx.policy = policyRead.policy;

  if (!own(input, "attempt")) return emit(ctx, "EVIDENCE_UNAVAILABLE", "attempt_absent");
  if (!isPlain(input.attempt)) return emit(ctx, "UNKNOWN", "attempt_unclassifiable");
  ctx.attempt = input.attempt;
  const attempt = input.attempt;

  if (own(attempt, "result") || own(attempt, "action_taken") || own(attempt, "success")) {
    return emit(ctx, "UNKNOWN", "smuggled_result");
  }

  if (!own(attempt, "policy_loaded")) return emit(ctx, "EVIDENCE_UNAVAILABLE", "policy_loaded_not_set");
  if (attempt.policy_loaded === false) {
    mark(ctx, "path_support", "gap", "policy_not_loaded");
    return emit(ctx, "ENFORCEMENT_GAP", "fail_open_policy_not_loaded", { authority: "DENIED", would: "DENIED" });
  }
  if (attempt.policy_loaded !== true) return emit(ctx, "UNKNOWN", "policy_loaded_unclassifiable");

  ctx.evidenceClass = "SUPPLIED_CASE_EVIDENCE";

  if (path.plane === "host") {
    const obs = readHostObservation(ctx, attempt);
    if (obs.stop) return obs.stop;
    ctx.observation = obs.value;
    if (ctx.observation.saw.includes("redirect")) pathSees(ctx, "redirect");
    if (ctx.observation.saw.includes("destination_ip")) pathSees(ctx, "dns");
  }

  const bypass = checkBypass(ctx, attempt);
  if (bypass) return bypass;

  const dest = readDestination(attempt);
  if (dest.bad) return emit(ctx, "UNKNOWN", "destination_unclassifiable");
  ctx.dest = dest.missing ? null : dest;

  const earlyRetry = checkRetryChannel(ctx, attempt);
  if (earlyRetry) return earlyRetry;

  const child = checkDescendant(ctx, attempt);
  if (child) return applyLatch(ctx, child);

  const destination = checkDestination(ctx);
  if (destination) return applyLatch(ctx, destination);

  const proto = checkProtocolPort(ctx);
  if (proto) return applyLatch(ctx, proto);

  const http = checkHttp(ctx, attempt);
  if (http) return applyLatch(ctx, http);

  const socket = checkDirectSocket(ctx);
  if (socket) return applyLatch(ctx, socket);

  const cred = checkCredential(ctx, attempt);
  if (cred) return applyLatch(ctx, cred);

  const pattern = checkPattern(ctx, attempt);
  if (pattern) return applyLatch(ctx, pattern);

  const redirect = checkRedirect(ctx, attempt);
  if (redirect) return applyLatch(ctx, redirect);

  const dns = checkDns(ctx, attempt);
  if (dns) return applyLatch(ctx, dns);

  const tls = checkTls(ctx, attempt);
  if (tls) return applyLatch(ctx, tls);

  const sensitive = checkSensitive(ctx, attempt);
  if (sensitive) return applyLatch(ctx, sensitive);

  const size = checkSize(ctx, attempt);
  if (size) return applyLatch(ctx, size);

  const resource = checkResource(ctx, attempt);
  if (resource) return applyLatch(ctx, resource);

  const spend = checkSpend(ctx, attempt);
  if (spend) return applyLatch(ctx, spend);

  markUnsetClear(ctx);
  if (ctx.observation && ctx.observation.dropped === true) {
    mark(ctx, "destination", "unknown", "drop_without_policy_basis");
    return emit(ctx, "UNKNOWN", "host_drop_unexplained");
  }
  return emit(ctx, "ALLOWED", "policy_permits", { authority: "ALLOWED" });
}

function applyHostGap(ctx, decision) {
  if (!ctx.hostGap) return decision;
  if (decision.result === "EVIDENCE_UNAVAILABLE" || decision.result === "UNKNOWN" || decision.result === "UNSUPPORTED") {
    return decision;
  }
  if (ctx.hostGap === "cgroup") {
    const wish = decision.result === "ENFORCEMENT_GAP" ? decision.authority_disposition : decision.result;
    return emit(ctx, "ENFORCEMENT_GAP", "cgroup_skb_not_attached", { authority: wish, would: wish });
  }
  const wish = decision.result === "ENFORCEMENT_GAP" ? decision.authority_disposition : decision.result;
  return emit(ctx, "ENFORCEMENT_GAP", "uprobe_observe_only", { authority: wish, would: wish });
}

function finish(ctx, decision) {
  let out = decision;
  if (out.result === "ALLOWED" && ctx.redacted) {
    out = applyLatch(ctx, emit(ctx, "REDACTED", "sensitive_redacted", { authority: "REDACTED" }));
  }
  return applyHostGap(ctx, out);
}

function evaluate(input) {
  const ctx = createContext();
  try {
    return finish(ctx, evaluateInner(ctx, input));
  } catch {
    return emit(ctx, "UNKNOWN", "evaluator_fault", { fault: true });
  }
}

module.exports = {
  evaluate,
};
