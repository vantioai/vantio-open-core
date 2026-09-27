"use strict";

const { BYPASS_KINDS, CHILD_TOOLS, PATTERN_KINDS } = require("./vocabulary.cjs");
const { PATTERNS, scanText } = require("./sensitive.cjs");
const { classifyIp, hostListed, ipListed } = require("./match.cjs");
const {
  controlEvidence,
  emit,
  httpConstraints,
  isPlain,
  mark,
  micro,
  own,
  portListed,
  protocolListed,
} = require("./decision.cjs");

const BYPASS_SET = new Set(BYPASS_KINDS);
const PATTERN_SET = new Set(PATTERN_KINDS);
const TOOL_SET = new Set(CHILD_TOOLS);

function pathSees(ctx, kind) {
  ctx.runtime = ctx.runtime || {};
  ctx.runtime[kind] = true;
}

function readHostObservation(ctx, attempt) {
  const path = ctx.path;
  if (!own(attempt, "host_observation")) {
    return { stop: emit(ctx, "EVIDENCE_UNAVAILABLE", "host_observation_absent") };
  }
  const obs = attempt.host_observation;
  if (!isPlain(obs) || obs.evidence !== "supplied" || obs.supplied !== true) {
    return { stop: emit(ctx, "EVIDENCE_UNAVAILABLE", "host_observation_absent") };
  }
  if (obs.this_force_executed === true) {
    return { stop: emit(ctx, "UNKNOWN", "host_execution_claim_rejected") };
  }
  if (typeof obs.enrolled !== "boolean" || typeof obs.attach !== "string" || !Array.isArray(obs.saw)) {
    return { stop: emit(ctx, "UNKNOWN", "host_observation_unclassifiable") };
  }
  for (const item of obs.saw) {
    if (typeof item !== "string") return { stop: emit(ctx, "UNKNOWN", "host_observation_unclassifiable") };
  }
  if (path.id === "host_not_enrolled" || obs.enrolled === false) {
    return { stop: emit(ctx, "UNSUPPORTED", "host_not_enrolled") };
  }
  if (obs.dropped === true && (obs.attach === "none" || path.hostDrop !== true || obs.forwarded_cgroup0 === true)) {
    return { stop: emit(ctx, "UNKNOWN", "host_drop_unexplained") };
  }
  if (obs.dropped == null) {
    return { stop: emit(ctx, "EVIDENCE_UNAVAILABLE", "host_drop_evidence_absent") };
  }
  if (typeof obs.dropped !== "boolean") {
    return { stop: emit(ctx, "UNKNOWN", "host_observation_unclassifiable") };
  }
  if (path.id === "host_cgroup_skb" && (obs.attach === "none" || obs.forwarded_cgroup0 === true)) {
    ctx.hostGap = "cgroup";
  }
  if (path.id === "host_uprobe_tls") ctx.hostGap = "uprobe";
  return {
    value: {
      enrolled: obs.enrolled,
      attach: obs.attach,
      saw: obs.saw,
      dropped: obs.dropped,
      contained: obs.contained === true,
      forwarded_cgroup0: obs.forwarded_cgroup0 === true,
    },
  };
}

function checkBypass(ctx, attempt) {
  mark(ctx, "bypass", "not_in_attempt", null);
  if (!own(attempt, "bypass")) return null;
  const bypass = attempt.bypass;
  if (!isPlain(bypass)) return emit(ctx, "UNKNOWN", "bypass_unclassifiable");
  if (!own(bypass, "kind")) {
    mark(ctx, "bypass", "unavailable", "kind");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "bypass_kind_absent");
  }
  if (typeof bypass.kind !== "string" || !BYPASS_SET.has(bypass.kind)) {
    mark(ctx, "bypass", "unknown", bypass.kind == null ? null : String(bypass.kind));
    return emit(ctx, "UNKNOWN", "bypass_kind_unclassified");
  }
  if (bypass.kind === "browser") {
    mark(ctx, "bypass", "unsupported", "browser");
    return emit(ctx, "UNSUPPORTED", "browser_outside_wrap");
  }
  mark(ctx, "bypass", "gap", bypass.kind);
  return emit(ctx, "ENFORCEMENT_GAP", "application_path_bypass", {
    authority: "DENIED",
    would: "DENIED",
  });
}

function checkRetryChannel(ctx, attempt) {
  mark(ctx, "retry", "not_in_attempt", null);
  if (!own(attempt, "retry")) return null;
  const retry = attempt.retry;
  if (!isPlain(retry)) return emit(ctx, "UNKNOWN", "retry_unclassifiable");
  if (!own(retry, "channel")) {
    mark(ctx, "retry", "unavailable", "channel");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "retry_channel_absent");
  }
  if (retry.channel === "open_socket") {
    mark(ctx, "retry", "gap", "open_socket");
    return emit(ctx, "ENFORCEMENT_GAP", "retry_on_open_socket", { authority: "DENIED", would: "DENIED" });
  }
  if (retry.channel !== "new_request") {
    mark(ctx, "retry", "unknown", String(retry.channel));
    return emit(ctx, "UNKNOWN", "retry_channel_unclassified");
  }
  mark(ctx, "retry", "clear", "new_request");
  return null;
}

function namedOnList(hostname, policy) {
  if (!hostname) return false;
  return hostListed(hostname, policy.blocked_hosts) || hostListed(hostname, policy.allowed_hosts);
}

function checkDestination(ctx) {
  const policy = ctx.policy;
  const dest = ctx.dest;
  if (!dest || (dest.hostname == null && dest.ip == null)) {
    mark(ctx, "destination", "unavailable", "destination");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_evidence_absent");
  }
  if (ctx.path.plane === "host") {
    return finishDestination(ctx, dest, policy);
  }
  const named = namedOnList(dest.hostname, policy);
  const catalog = dest.catalog;
  if (catalog == null && !named) {
    mark(ctx, "destination", "unavailable", "scope");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "scope_evidence_absent");
  }
  const inScope = named || catalog === true;
  if (!inScope && policy.scope === "llm_and_named") {
    mark(ctx, "destination", "unsupported", "outside_product_scope");
    return emit(ctx, "UNSUPPORTED", "destination_outside_product_scope");
  }
  if (!inScope && policy.scope === "all_egress") {
    mark(ctx, "destination", "gap", "out_of_scope_pass_through");
    const wish = dest.ip && ipListed(dest.ip, policy.blocked_ips).listed ? "DENIED" : "ALLOWED";
    return emit(ctx, "ENFORCEMENT_GAP", "out_of_scope_pass_through", { authority: wish, would: wish });
  }

  if (dest.hostname && hostListed(dest.hostname, policy.blocked_hosts)) {
    if (hostDidNotDrop(ctx)) {
      mark(ctx, "destination", "gap", "host_did_not_drop");
      return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "destination", "triggered", "blocked_hosts");
    return emit(ctx, "DENIED", "host_not_permitted", { authority: "DENIED" });
  }
  const blockedIp = ipListed(dest.ip, policy.blocked_ips);
  if (blockedIp.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
  if (blockedIp.absent && policy.blocked_ips.length > 0 && !own(ctx.attempt, "dns")) {
    if (!ctx.path.seesResolvedIp) {
      mark(ctx, "destination", "gap", "ip_not_visible");
      return emit(ctx, "ENFORCEMENT_GAP", "destination_ip_not_visible", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "destination", "unavailable", "ip");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_ip_absent");
  }
  if (blockedIp.listed) {
    if (!ctx.path.seesResolvedIp) {
      mark(ctx, "destination", "gap", "ip_not_visible");
      return emit(ctx, "ENFORCEMENT_GAP", "destination_ip_not_visible", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "destination", "triggered", "blocked_ips");
    return emit(ctx, "DENIED", "host_not_permitted", { authority: "DENIED" });
  }
  if (policy.allowed_hosts.length > 0) {
    if (!dest.hostname) {
      mark(ctx, "destination", "unavailable", "hostname");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_hostname_absent");
    }
    if (!hostListed(dest.hostname, policy.allowed_hosts)) {
      mark(ctx, "destination", "triggered", "allowed_hosts");
      return emit(ctx, "DENIED", "not_in_allowed_hosts", { authority: "DENIED" });
    }
  }
  if (policy.allowed_ips.length > 0) {
    const allowedIp = ipListed(dest.ip, policy.allowed_ips);
    if (allowedIp.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
    if (allowedIp.absent) {
      mark(ctx, "destination", "unavailable", "ip");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_ip_absent");
    }
    if (!allowedIp.listed) {
      if (!ctx.path.seesResolvedIp) {
        mark(ctx, "destination", "gap", "ip_not_visible");
        return emit(ctx, "ENFORCEMENT_GAP", "destination_ip_not_visible", { authority: "DENIED", would: "DENIED" });
      }
      mark(ctx, "destination", "triggered", "allowed_ips");
      return emit(ctx, "DENIED", "not_in_allowed_hosts", { authority: "DENIED" });
    }
  }
  if (!ctx.path.seesResolvedIp && (policy.blocked_ips.length > 0 || policy.allowed_ips.length > 0)) {
    mark(ctx, "destination", "gap", "ip_not_visible");
    if (own(ctx.attempt, "dns")) return null;
    return emit(ctx, "ENFORCEMENT_GAP", "destination_ip_not_visible", { authority: "DENIED", would: "DENIED" });
  }
  mark(ctx, "destination", "clear", dest.hostname || dest.ip);
  return null;
}

function checkProtocolPort(ctx) {
  const policy = ctx.policy;
  const constrained = policy.allowed_protocols.length || policy.denied_protocols.length || policy.allowed_ports.length || policy.denied_ports.length;
  if (!constrained) {
    mark(ctx, "protocol_port", "not_in_attempt", null);
    return null;
  }
  const dest = ctx.dest;
  if (policy.allowed_protocols.length || policy.denied_protocols.length) {
    if (!dest.protocol) {
      mark(ctx, "protocol_port", "unavailable", "protocol");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "protocol_evidence_absent");
    }
    const denied = protocolListed(dest.protocol, policy.denied_protocols);
    if (denied.bad) return emit(ctx, "UNKNOWN", "protocol_policy_unclassifiable");
    if (denied.listed) {
      return deniedObserved(ctx, "protocol_port", "denied_protocols", "protocol_not_permitted");
    }
    if (policy.allowed_protocols.length > 0) {
      const allowed = protocolListed(dest.protocol, policy.allowed_protocols);
      if (allowed.bad) return emit(ctx, "UNKNOWN", "protocol_policy_unclassifiable");
      if (!allowed.listed) {
        return deniedObserved(ctx, "protocol_port", "allowed_protocols", "protocol_not_permitted");
      }
    }
  }
  if (policy.allowed_ports.length || policy.denied_ports.length) {
    if (!dest.port) {
      mark(ctx, "protocol_port", "unavailable", "port");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "port_evidence_absent");
    }
    const deniedPort = portListed(dest.port, policy.denied_ports);
    if (deniedPort.bad) return emit(ctx, "UNKNOWN", "port_policy_unclassifiable");
    if (deniedPort.listed) {
      return deniedObserved(ctx, "protocol_port", "denied_ports", "port_not_permitted");
    }
    if (policy.allowed_ports.length > 0) {
      const allowedPort = portListed(dest.port, policy.allowed_ports);
      if (allowedPort.bad) return emit(ctx, "UNKNOWN", "port_policy_unclassifiable");
      if (!allowedPort.listed) {
        return deniedObserved(ctx, "protocol_port", "allowed_ports", "port_not_permitted");
      }
    }
  }
  mark(ctx, "protocol_port", "clear", dest.protocol ? dest.protocol + ":" + (dest.port || "") : dest.port);
  return null;
}

function checkHttp(ctx, attempt) {
  const policy = ctx.policy;
  if (!httpConstraints(policy)) {
    mark(ctx, "http_method_path", "not_in_attempt", null);
    return null;
  }
  if (!ctx.path.seesHttp) {
    mark(ctx, "http_method_path", "gap", "not_visible");
    return emit(ctx, "ENFORCEMENT_GAP", "http_method_not_visible", { authority: "EVIDENCE_UNAVAILABLE", would: "EVIDENCE_UNAVAILABLE" });
  }
  if (!own(attempt, "http") || !isPlain(attempt.http)) {
    mark(ctx, "http_method_path", "unavailable", "http");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "http_evidence_absent");
  }
  const method = typeof attempt.http.method === "string" ? attempt.http.method.trim().toUpperCase() : "";
  const path = typeof attempt.http.path === "string" ? attempt.http.path : "";
  if ((policy.allowed_methods.length || policy.denied_methods.length) && method === "") {
    mark(ctx, "http_method_path", "unavailable", "method");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "http_method_absent");
  }
  if ((policy.allowed_path_prefixes.length || policy.denied_path_prefixes.length) && path === "") {
    mark(ctx, "http_method_path", "unavailable", "path");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "http_path_absent");
  }
  if (policy.denied_methods.map((m) => m.toUpperCase()).includes(method)) {
    mark(ctx, "http_method_path", "triggered", "denied_methods");
    return emit(ctx, "DENIED", "method_not_permitted", { authority: "DENIED" });
  }
  if (policy.allowed_methods.length > 0 && !policy.allowed_methods.map((m) => m.toUpperCase()).includes(method)) {
    mark(ctx, "http_method_path", "triggered", "allowed_methods");
    return emit(ctx, "DENIED", "method_not_permitted", { authority: "DENIED" });
  }
  if (policy.denied_path_prefixes.some((prefix) => path.startsWith(prefix))) {
    mark(ctx, "http_method_path", "triggered", "denied_path_prefixes");
    return emit(ctx, "DENIED", "path_not_permitted", { authority: "DENIED" });
  }
  if (policy.allowed_path_prefixes.length > 0 && !policy.allowed_path_prefixes.some((prefix) => path.startsWith(prefix))) {
    mark(ctx, "http_method_path", "triggered", "allowed_path_prefixes");
    return emit(ctx, "DENIED", "path_not_permitted", { authority: "DENIED" });
  }
  mark(ctx, "http_method_path", "clear", method + " " + path);
  return null;
}

function checkDirectSocket(ctx) {
  if (!ctx.path.directSocket) {
    mark(ctx, "direct_socket", "not_in_attempt", null);
    return null;
  }
  mark(ctx, "direct_socket", "clear", ctx.path.id);
  return null;
}

function checkCredential(ctx, attempt) {
  const policy = ctx.policy;
  if (!policy.credential_required && !own(attempt, "credential")) {
    mark(ctx, "credential", "not_in_attempt", null);
    return null;
  }
  if (!own(attempt, "credential") || !isPlain(attempt.credential)) {
    mark(ctx, "credential", "unavailable", "credential");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "credential_evidence_absent");
  }
  const cred = attempt.credential;
  if (typeof cred.present !== "boolean" || typeof cred.revoked !== "boolean" || typeof cred.permitted !== "boolean") {
    mark(ctx, "credential", "unknown", "fields");
    return emit(ctx, "UNKNOWN", "credential_unclassifiable");
  }
  if (policy.credential_required && cred.present !== true) {
    mark(ctx, "credential", "unavailable", "present");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "credential_evidence_absent");
  }
  if (cred.revoked === true) {
    if (cred.control_applied === true && controlEvidence(cred)) {
      mark(ctx, "credential", "triggered", "revoked");
      return emit(ctx, "REVOKED", "credential_revoked", { authority: "REVOKED" });
    }
    mark(ctx, "credential", "gap", "revocation_not_enforced_on_path");
    return emit(ctx, "ENFORCEMENT_GAP", "revocation_not_enforced", { authority: "REVOKED", would: "REVOKED" });
  }
  if (cred.permitted === false) {
    if (cred.control_applied === true && controlEvidence(cred)) {
      mark(ctx, "credential", "triggered", "not_permitted");
      return emit(ctx, "DENIED", "credential_not_permitted", { authority: "DENIED" });
    }
    mark(ctx, "credential", "gap", "credential_policy_not_on_path");
    return emit(ctx, "ENFORCEMENT_GAP", "credential_not_enforced", { authority: "DENIED", would: "DENIED" });
  }
  mark(ctx, "credential", "clear", "present");
  return null;
}

function checkPattern(ctx, attempt) {
  if (!own(attempt, "pattern")) {
    mark(ctx, "pattern", "not_in_attempt", null);
    return null;
  }
  const pattern = attempt.pattern;
  if (!isPlain(pattern)) return emit(ctx, "UNKNOWN", "pattern_unclassifiable");
  if (!own(pattern, "kind")) {
    mark(ctx, "pattern", "unavailable", "kind");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "pattern_kind_absent");
  }
  if (typeof pattern.kind !== "string" || !PATTERN_SET.has(pattern.kind)) {
    mark(ctx, "pattern", "unknown", String(pattern.kind));
    return emit(ctx, "UNKNOWN", "pattern_kind_unclassified");
  }
  if (typeof pattern.contained !== "boolean") {
    mark(ctx, "pattern", "unavailable", "contained");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "pattern_containment_absent");
  }
  if (pattern.contained === true) {
    if (!controlEvidence(pattern)) {
      mark(ctx, "pattern", "unavailable", "control");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "containment_control_absent");
    }
    mark(ctx, "pattern", "triggered", pattern.kind);
    return emit(ctx, "CONTAINED", "pattern_contained", { authority: "CONTAINED" });
  }
  mark(ctx, "pattern", "gap", pattern.kind);
  return emit(ctx, "ENFORCEMENT_GAP", "pattern_not_contained", { authority: "CONTAINED", would: "CONTAINED" });
}

function checkDescendant(ctx, attempt) {
  if (ctx.path.childTool) {
    if (!own(attempt, "descendant") || !isPlain(attempt.descendant)) {
      mark(ctx, "descendant", "unavailable", "descendant");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "descendant_evidence_absent");
    }
  } else if (!own(attempt, "descendant")) {
    mark(ctx, "descendant", "not_in_attempt", null);
    return null;
  }
  const child = attempt.descendant;
  if (!isPlain(child)) return emit(ctx, "UNKNOWN", "descendant_unclassifiable");
  if (typeof child.binary !== "string" || !own(child, "depth")) {
    mark(ctx, "descendant", "unavailable", "binary_or_depth");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "descendant_evidence_absent");
  }
  if (typeof child.depth !== "number" || !Number.isInteger(child.depth) || child.depth < 0) {
    return emit(ctx, "UNKNOWN", "descendant_unclassifiable");
  }
  const binary = child.binary.trim().toLowerCase();
  if (child.depth === 0 && !ctx.path.childTool) {
    mark(ctx, "descendant", "clear", "depth_0");
    return null;
  }
  if (child.depth > 1) {
    mark(ctx, "descendant", "gap", "grandchild");
    return emit(ctx, "ENFORCEMENT_GAP", "grandchild_not_visible", { authority: "DENIED", would: "DENIED" });
  }
  if (!TOOL_SET.has(binary)) {
    if (child.inherits_wrap === true) {
      mark(ctx, "descendant", "gap", "separate_evaluation_required");
      return emit(ctx, "ENFORCEMENT_GAP", "descendant_call_not_in_this_decision", { authority: "EVIDENCE_UNAVAILABLE", would: "EVIDENCE_UNAVAILABLE" });
    }
    mark(ctx, "descendant", "gap", binary);
    return emit(ctx, "ENFORCEMENT_GAP", "descendant_binary_outside_wrap", { authority: "DENIED", would: "DENIED" });
  }
  if (!ctx.path.childTool) {
    mark(ctx, "descendant", "gap", "not_a_child_tool_path");
    return emit(ctx, "ENFORCEMENT_GAP", "descendant_call_not_in_this_decision", { authority: "EVIDENCE_UNAVAILABLE", would: "EVIDENCE_UNAVAILABLE" });
  }
  if (child.depth !== 1) {
    mark(ctx, "descendant", "unavailable", "depth");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "descendant_evidence_absent");
  }
  mark(ctx, "descendant", "clear", binary);
  return null;
}

function hopHost(hop) {
  if (!isPlain(hop)) return { bad: true };
  if (typeof hop.hostname !== "string") return { unavailable: true };
  const host = hop.hostname.trim().toLowerCase().replace(/\.$/, "");
  if (!host) return { unavailable: true };
  return { host };
}

function hopDenied(policy, hop) {
  const parsed = hopHost(hop);
  if (parsed.bad || parsed.unavailable) return parsed;
  const host = parsed.host;
  if (hostListed(host, policy.blocked_hosts)) return { denied: true, reason: "host_not_permitted" };
  if (policy.allowed_hosts.length > 0 && !hostListed(host, policy.allowed_hosts)) return { denied: true, reason: "not_in_allowed_hosts" };
  return { denied: false };
}

function chainMismatch(ctx, hops) {
  const destHost = ctx.dest && ctx.dest.hostname ? ctx.dest.hostname : "";
  if (!destHost || hops.length === 0) return false;
  const first = hopHost(hops[0]);
  if (first.bad || first.unavailable) return false;
  return first.host !== destHost;
}

function checkRedirect(ctx, attempt) {
  if (!own(attempt, "redirect")) {
    mark(ctx, "redirect", "not_in_attempt", null);
    return null;
  }
  const redirect = attempt.redirect;
  if (!isPlain(redirect) || !Array.isArray(redirect.hops)) {
    mark(ctx, "redirect", "unavailable", "hops");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
  }
  if (redirect.hops.length === 0) {
    mark(ctx, "redirect", "unavailable", "hops");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
  }
  if (chainMismatch(ctx, redirect.hops)) {
    mark(ctx, "redirect", "unknown", "chain_mismatch");
    return emit(ctx, "UNKNOWN", "redirect_unclassifiable");
  }
  if (redirect.hops.length < 2) {
    const single = hopDenied(ctx.policy, redirect.hops[0]);
    if (single.bad) return emit(ctx, "UNKNOWN", "redirect_unclassifiable");
    if (single.unavailable) {
      mark(ctx, "redirect", "unavailable", "hop");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
    }
    mark(ctx, "redirect", "clear", "single_hop");
    return null;
  }
  let anyDenied = false;
  for (const hop of redirect.hops) {
    const verdict = hopDenied(ctx.policy, hop);
    if (verdict.bad) return emit(ctx, "UNKNOWN", "redirect_unclassifiable");
    if (verdict.unavailable) {
      mark(ctx, "redirect", "unavailable", "hop");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "redirect_evidence_absent");
    }
    if (verdict.denied) anyDenied = true;
  }
  const canReeval = ctx.runtime && ctx.runtime.redirect === true;
  if (!canReeval) {
    mark(ctx, "redirect", "gap", "not_reevaluated");
    return emit(ctx, "ENFORCEMENT_GAP", "redirect_not_reevaluated", {
      authority: anyDenied ? "DENIED" : "ALLOWED",
      would: anyDenied ? "DENIED" : "ALLOWED",
    });
  }
  if (anyDenied) {
    return deniedObserved(ctx, "redirect", "hop", "redirect_hop_denied");
  }
  mark(ctx, "redirect", "clear", "reevaluated");
  return null;
}

function checkDns(ctx, attempt) {
  if (!own(attempt, "dns")) {
    mark(ctx, "dns", "not_in_attempt", null);
    return null;
  }
  const dns = attempt.dns;
  if (!isPlain(dns) || !Array.isArray(dns.answers)) {
    mark(ctx, "dns", "unavailable", "answers");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "dns_evidence_absent");
  }
  if (dns.answers.length === 0) {
    mark(ctx, "dns", "unavailable", "answers");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "dns_evidence_absent");
  }
  for (const answer of dns.answers) {
    if (typeof answer !== "string" || !classifyIp(answer)) return emit(ctx, "UNKNOWN", "dns_unclassifiable");
  }
  const unique = new Set(dns.answers.map((a) => a.trim().toLowerCase()));
  const selected = typeof dns.selected === "string" ? dns.selected : null;
  const atConnect = typeof dns.at_connect === "string" ? dns.at_connect : null;
  if (unique.size > 1 && selected == null && atConnect == null) {
    mark(ctx, "dns", "unknown", "unresolved");
    return emit(ctx, "UNKNOWN", "dns_answers_unresolved");
  }
  if (selected && !unique.has(selected.trim().toLowerCase())) {
    mark(ctx, "dns", "unknown", "selected_not_in_answers");
    return emit(ctx, "UNKNOWN", "dns_answers_unresolved");
  }
  const used = atConnect || selected || dns.answers[0];
  const blocked = ipListed(used, ctx.policy.blocked_ips);
  if (blocked.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
  const denied = blocked.listed;
  const changed = atConnect != null && selected != null && atConnect.trim().toLowerCase() !== selected.trim().toLowerCase();
  const canRecheck = ctx.runtime && ctx.runtime.dns === true;
  if ((changed || denied) && !canRecheck) {
    mark(ctx, "dns", "gap", changed ? "changed" : "answer_denied");
    return emit(ctx, "ENFORCEMENT_GAP", changed ? "dns_change_not_rechecked" : "dns_answer_not_visible", {
      authority: denied || changed ? "DENIED" : "ALLOWED",
      would: "DENIED",
    });
  }
  if (changed && dns.rechecked !== true) {
    mark(ctx, "dns", "gap", "changed");
    return emit(ctx, "ENFORCEMENT_GAP", "dns_change_not_rechecked", { authority: "DENIED", would: "DENIED" });
  }
  if (denied) {
    if (hostDidNotDrop(ctx)) {
      mark(ctx, "dns", "gap", "host_did_not_drop");
      return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "dns", "triggered", used);
    return emit(ctx, "DENIED", "dns_answer_denied", { authority: "DENIED" });
  }
  if (!ctx.path.seesResolvedIp && (ctx.policy.blocked_ips.length > 0 || ctx.policy.allowed_ips.length > 0)) {
    let blockedAnswer = false;
    for (const answer of dns.answers) {
      const hit = ipListed(answer, ctx.policy.blocked_ips);
      if (hit.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
      if (hit.listed) blockedAnswer = true;
    }
    mark(ctx, "dns", "gap", blockedAnswer ? "blocked_answer_not_selected" : "ip_not_visible");
    return emit(ctx, "ENFORCEMENT_GAP", blockedAnswer ? "dns_answer_not_visible" : "destination_ip_not_visible", {
      authority: "DENIED",
      would: "DENIED",
    });
  }
  mark(ctx, "dns", "clear", used);
  return null;
}

function checkTls(ctx, attempt) {
  const required = ctx.policy.require_tls_peer;
  if (!required && !own(attempt, "tls")) {
    mark(ctx, "tls", "not_in_attempt", null);
    return null;
  }
  if (!own(attempt, "tls") || !isPlain(attempt.tls)) {
    if (!ctx.path.tlsPeerVerified) {
      mark(ctx, "tls", "gap", "peer_not_visible");
      return emit(ctx, "ENFORCEMENT_GAP", "tls_peer_not_visible", { authority: "EVIDENCE_UNAVAILABLE", would: "EVIDENCE_UNAVAILABLE" });
    }
    mark(ctx, "tls", "unavailable", "tls");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "tls_evidence_absent");
  }
  const peer = typeof attempt.tls.peer_name === "string" ? attempt.tls.peer_name.trim().toLowerCase().replace(/\.$/, "") : "";
  if (peer === "") {
    mark(ctx, "tls", "unavailable", "peer_name");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "tls_evidence_absent");
  }
  const host = ctx.dest && ctx.dest.hostname ? ctx.dest.hostname : "";
  const verified = ctx.path.tlsPeerVerified === true || tlsControlApplied(attempt.tls);
  if (host && peer !== host) {
    if (hostDidNotDrop(ctx)) {
      mark(ctx, "tls", "gap", "host_did_not_drop");
      return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
    }
    if (!verified) {
      mark(ctx, "tls", "gap", "mismatch_not_visible");
      return emit(ctx, "ENFORCEMENT_GAP", "tls_peer_not_visible", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "tls", "triggered", "mismatch");
    return emit(ctx, "DENIED", "tls_destination_mismatch", { authority: "DENIED" });
  }
  if (required && !verified) {
    mark(ctx, "tls", "gap", "supplied_not_path_observed");
    return emit(ctx, "ENFORCEMENT_GAP", "tls_peer_not_visible", { authority: "EVIDENCE_UNAVAILABLE", would: "EVIDENCE_UNAVAILABLE" });
  }
  mark(ctx, "tls", "clear", peer);
  return null;
}

function checkSensitive(ctx, attempt) {
  const action = ctx.policy.sensitive_action;
  for (const type of ctx.policy.pii_types) {
    const key = String(type).trim().toLowerCase();
    if (!PATTERNS[key]) return emit(ctx, "UNKNOWN", "pii_type_unclassified");
  }
  if (action === "ignore" && !own(attempt, "body") && !own(attempt, "sensitive")) {
    mark(ctx, "sensitive", "not_in_attempt", null);
    return null;
  }
  if (action === "ignore") {
    mark(ctx, "sensitive", "clear", "ignore");
    return null;
  }
  if (!own(attempt, "body") || !isPlain(attempt.body)) {
    mark(ctx, "sensitive", "unavailable", "body");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "body_evidence_absent");
  }
  const body = attempt.body;
  if (body.kind === "empty") {
    mark(ctx, "sensitive", "clear", "empty");
    ctx.bodyBytes = 0;
    return null;
  }
  if (body.kind === "unscanned" || body.kind === "stream" || body.kind === "file" || body.kind === "pipe") {
    mark(ctx, "sensitive", "gap", body.kind);
    return emit(ctx, "ENFORCEMENT_GAP", "unscanned_body", {
      authority: action === "deny" ? "DENIED" : "REDACTED",
      would: action === "deny" ? "DENIED" : "REDACTED",
    });
  }
  if (body.kind !== "text" && body.kind !== "json") return emit(ctx, "UNKNOWN", "body_unclassifiable");
  if (!ctx.path.redactMaterialized && action === "redact") {
    mark(ctx, "sensitive", "gap", "path_cannot_redact");
    return emit(ctx, "ENFORCEMENT_GAP", "redact_not_visible", { authority: "REDACTED", would: "REDACTED" });
  }
  if (!ctx.path.redactMaterialized && action === "deny") {
    mark(ctx, "sensitive", "gap", "path_cannot_deny_sensitive");
    return emit(ctx, "ENFORCEMENT_GAP", "sensitive_deny_not_visible", { authority: "DENIED", would: "DENIED" });
  }
  const scanned = scanText(body.text, ctx.policy.pii_types);
  if (!scanned.ok) return emit(ctx, "UNKNOWN", "body_unclassifiable");
  ctx.bodyBytes = scanned.bytes;
  const found = scanned.found;
  if (own(attempt, "sensitive") && isPlain(attempt.sensitive) && typeof attempt.sensitive.present === "boolean") {
    const flag = attempt.sensitive.present;
    if (flag !== (found.length > 0)) return emit(ctx, "UNKNOWN", "sensitive_evidence_contradicts");
  }
  if (found.length === 0) {
    mark(ctx, "sensitive", "clear", "none");
    return null;
  }
  if (action === "deny") {
    if (isPlain(attempt.sensitive) && attempt.sensitive.control_applied === true && controlEvidence(attempt.sensitive)) {
      mark(ctx, "sensitive", "triggered", found.join(","));
      return emit(ctx, "DENIED", "sensitive_denied", { authority: "DENIED" });
    }
    mark(ctx, "sensitive", "gap", "deny_not_on_path");
    return emit(ctx, "ENFORCEMENT_GAP", "sensitive_deny_not_enforced", { authority: "DENIED", would: "DENIED" });
  }
  ctx.redacted = true;
  ctx.redactionClasses = found;
  mark(ctx, "sensitive", "clear", "redacted_pending");
  return null;
}

function checkSize(ctx, attempt) {
  if (!(ctx.policy.max_request_bytes > 0)) {
    mark(ctx, "payload_size", "not_in_attempt", null);
    return null;
  }
  if (!ctx.path.sizeGate) {
    mark(ctx, "payload_size", "gap", "not_visible");
    return emit(ctx, "ENFORCEMENT_GAP", "size_not_visible", { authority: "DENIED", would: "DENIED" });
  }
  let bytes = ctx.bodyBytes;
  if (own(attempt, "size")) {
    if (!isPlain(attempt.size) || typeof attempt.size.bytes !== "number" || !Number.isInteger(attempt.size.bytes) || attempt.size.bytes < 0) {
      return emit(ctx, "UNKNOWN", "size_unclassifiable");
    }
    bytes = attempt.size.bytes;
  }
  if (bytes == null) {
    mark(ctx, "payload_size", "unavailable", "bytes");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "size_evidence_absent");
  }
  if (bytes > ctx.policy.max_request_bytes) {
    mark(ctx, "payload_size", "triggered", String(bytes));
    return emit(ctx, "DENIED", "payload_size", { authority: "DENIED" });
  }
  mark(ctx, "payload_size", "clear", String(bytes));
  return null;
}

function checkResource(ctx, attempt) {
  const resource = ctx.policy.resource;
  if (!resource || resource.max_child_processes == null) {
    mark(ctx, "resource", "not_in_attempt", null);
    return null;
  }
  if (!own(attempt, "resource") || !isPlain(attempt.resource)) {
    mark(ctx, "resource", "unavailable", "resource");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "resource_evidence_absent");
  }
  const count = attempt.resource.child_processes;
  if (typeof count !== "number" || !Number.isInteger(count) || count < 0) {
    return emit(ctx, "UNKNOWN", "resource_unclassifiable");
  }
  if (count > resource.max_child_processes) {
    if (attempt.resource.control_applied === true && controlEvidence(attempt.resource)) {
      mark(ctx, "resource", "triggered", "child_processes");
      return emit(ctx, "CONTAINED", "resource_contained", { authority: "CONTAINED" });
    }
    mark(ctx, "resource", "gap", "child_processes");
    return emit(ctx, "ENFORCEMENT_GAP", "resource_not_contained", { authority: "CONTAINED", would: "CONTAINED" });
  }
  mark(ctx, "resource", "clear", String(count));
  return null;
}

function checkSpend(ctx, attempt) {
  if (!(ctx.policy.spend_cap_usd > 0)) {
    mark(ctx, "spend", "not_in_attempt", null);
    return null;
  }
  if (!own(attempt, "spend") || !isPlain(attempt.spend)) {
    mark(ctx, "spend", "unavailable", "spend");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "spend_evidence_absent");
  }
  const phase = attempt.spend.phase;
  if (phase !== "before_send" && phase !== "subsequent" && phase !== "mid_stream") {
    mark(ctx, "spend", "unknown", phase == null ? null : String(phase));
    return emit(ctx, "UNKNOWN", "spend_phase_unclassified");
  }
  const spent = micro(attempt.spend.spent_usd);
  const cap = micro(ctx.policy.spend_cap_usd);
  if (spent == null || cap == null) {
    mark(ctx, "spend", "unavailable", "spent_usd");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "spend_evidence_absent");
  }
  const over = spent >= cap;
  if (phase === "mid_stream") {
    mark(ctx, "spend", "gap", "mid_stream");
    return emit(ctx, "ENFORCEMENT_GAP", "spend_cap_cannot_block_mid_stream", {
      authority: over ? "DENIED" : "ALLOWED",
      would: over ? "DENIED" : "ALLOWED",
    });
  }
  if (!ctx.path.spendSubsequent) {
    mark(ctx, "spend", "gap", "not_visible");
    return emit(ctx, "ENFORCEMENT_GAP", "spend_not_visible", {
      authority: over ? "DENIED" : "ALLOWED",
      would: over ? "DENIED" : "ALLOWED",
    });
  }
  if (over) {
    mark(ctx, "spend", "triggered", "cap");
    return emit(ctx, "DENIED", "spend_cap", { authority: "DENIED" });
  }
  mark(ctx, "spend", "clear", phase);
  return null;
}

function markUnsetClear(ctx) {
  if (ctx.redacted) {
    mark(ctx, "sensitive", "triggered", (ctx.redactionClasses || []).join(","));
  }
}

function hostDidNotDrop(ctx) {
  return ctx.path.plane === "host" && ctx.observation && ctx.observation.dropped === false;
}

function tlsControlApplied(tls) {
  return isPlain(tls) && tls.control_applied === true && controlEvidence(tls);
}

function deniedObserved(ctx, dimension, detail, reason) {
  if (hostDidNotDrop(ctx)) {
    mark(ctx, dimension, "gap", "host_did_not_drop");
    return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
  }
  mark(ctx, dimension, "triggered", detail);
  return emit(ctx, "DENIED", reason, { authority: "DENIED" });
}

function finishDestination(ctx, dest, policy) {
  if (dest.hostname && hostListed(dest.hostname, policy.blocked_hosts)) {
    if (hostDidNotDrop(ctx)) {
      mark(ctx, "destination", "gap", "host_did_not_drop");
      return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "destination", "triggered", "blocked_hosts");
    return emit(ctx, "DENIED", "host_not_permitted", { authority: "DENIED" });
  }
  const blockedIp = ipListed(dest.ip, policy.blocked_ips);
  if (blockedIp.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
  if (blockedIp.absent && policy.blocked_ips.length > 0) {
    mark(ctx, "destination", "unavailable", "ip");
    return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_ip_absent");
  }
  if (blockedIp.listed) {
    if (hostDidNotDrop(ctx)) {
      mark(ctx, "destination", "gap", "host_did_not_drop");
      return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
    }
    mark(ctx, "destination", "triggered", "blocked_ips");
    return emit(ctx, "DENIED", "host_not_permitted", { authority: "DENIED" });
  }
  if (policy.allowed_hosts.length > 0) {
    if (!dest.hostname) {
      mark(ctx, "destination", "unavailable", "hostname");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_hostname_absent");
    }
    if (!hostListed(dest.hostname, policy.allowed_hosts)) {
      if (hostDidNotDrop(ctx)) {
        mark(ctx, "destination", "gap", "host_did_not_drop");
        return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
      }
      mark(ctx, "destination", "triggered", "allowed_hosts");
      return emit(ctx, "DENIED", "not_in_allowed_hosts", { authority: "DENIED" });
    }
  }
  if (policy.allowed_ips.length > 0) {
    const allowedIp = ipListed(dest.ip, policy.allowed_ips);
    if (allowedIp.bad) return emit(ctx, "UNKNOWN", "ip_policy_unclassifiable");
    if (allowedIp.absent) {
      mark(ctx, "destination", "unavailable", "ip");
      return emit(ctx, "EVIDENCE_UNAVAILABLE", "destination_ip_absent");
    }
    if (!allowedIp.listed) {
      if (hostDidNotDrop(ctx)) {
        mark(ctx, "destination", "gap", "host_did_not_drop");
        return emit(ctx, "ENFORCEMENT_GAP", "host_did_not_drop", { authority: "DENIED", would: "DENIED" });
      }
      mark(ctx, "destination", "triggered", "allowed_ips");
      return emit(ctx, "DENIED", "not_in_allowed_hosts", { authority: "DENIED" });
    }
  }
  mark(ctx, "destination", "clear", dest.hostname || dest.ip);
  return null;
}


module.exports = {
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
};
