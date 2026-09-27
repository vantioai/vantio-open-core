"use strict";

const { createHash } = require("node:crypto");

const { PRECEDENCE, PROTECTION_STATE_SET } = require("./constants.cjs");
const { classifyListeners } = require("./classify.cjs");
const { containmentFor, finishResult } = require("./result.cjs");

const UNSUPPORTED_PROTO = new Set(["unix", "vsock", "unix-domain"]);
const DOCKER_DNS = new Set(["127.0.0.11", "::ffff:127.0.0.11"]);
const STALE_POLICY_VERSIONS = new Set(["", "missing", "unversioned", "unknown", "none"]);
const REVOKE_ON = new Set(["revoked", "child_process_escape", "post_accept_denied"]);

function asPlainObject(value) {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  return value;
}

function isPid(value) {
  return Number.isInteger(value) && value > 0;
}

function isStart(value) {
  return Number.isInteger(value) && value > 0;
}

function cgroupUnattributable(value) {
  return value == null || value === "" || value === 0 || value === "0";
}

function attestation(identity, now) {
  if (!identity) return "WINDOW_ABSENT";
  const windowMs = identity.freshness_window_ms;
  if (typeof windowMs !== "number" || !Number.isFinite(windowMs) || windowMs <= 0) return "WINDOW_ABSENT";
  if (typeof now !== "number" || !Number.isFinite(now)) return "WINDOW_ABSENT";
  if (typeof identity.attested_at_ms !== "number" || !Number.isFinite(identity.attested_at_ms)) {
    return "WINDOW_ABSENT";
  }
  if (identity.attested_at_ms > now) return "WINDOW_ABSENT";
  if (now - identity.attested_at_ms > windowMs) return "OUTSIDE_CALLER_WINDOW";
  return "INSIDE_CALLER_WINDOW";
}

function orderFindings(findings) {
  const unique = [];
  const seen = new Set();
  for (const finding of findings) {
    if (seen.has(finding)) continue;
    if (PRECEDENCE.indexOf(finding) === -1) {
      throw new Error(`finding is not in precedence: ${finding}`);
    }
    seen.add(finding);
    unique.push(finding);
  }
  unique.sort((left, right) => PRECEDENCE.indexOf(left) - PRECEDENCE.indexOf(right));
  return unique;
}

function primaryReason(findings) {
  return orderFindings(findings)[0];
}

function grantKey(workload, identity, listener) {
  const enroll = workload && workload.enroll_id ? workload.enroll_id : "";
  const pid = identity && identity.pid ? identity.pid : "";
  const start = identity && identity.starttime ? identity.starttime : "";
  const port = listener && listener.local_port != null ? listener.local_port : "";
  const proto = listener && listener.proto ? listener.proto : "";
  return `${enroll}|${pid}|${start}|${port}|${proto}`;
}

function grantId(session, key, policy) {
  const boot = session ? session.boot_id : "stateless";
  const raw = `${boot}|${key}|${policy.sha}|${policy.version}`;
  return createHash("sha256").update(raw).digest("hex").slice(0, 24);
}

function retireGrant(session, key, revoke) {
  if (!session) return;
  for (const [id, grant] of session.grants) {
    if (grant.key !== key) continue;
    session.grants.delete(id);
    session.dead.add(id);
    if (revoke) session.revoked_keys.add(key);
  }
}

function storeGrant(session, id, key, policy) {
  retireGrant(session, key, false);
  session.grants.set(id, {
    id,
    key,
    boot_id: session.boot_id,
    policy_sha: policy.sha,
    policy_version: policy.version,
  });
  session.events.push({ op: "grant", grant_id: id, key });
}

function policyShape(envelope) {
  const present = Boolean(envelope && envelope.present === true);
  const version = envelope && envelope.policy_version != null ? String(envelope.policy_version) : "";
  const sha = envelope && envelope.applied_sha ? String(envelope.applied_sha) : "";
  return {
    present,
    version: version || null,
    sha: sha || null,
    stale: false,
    fail_mode_effect: "NOT_APPLIED",
  };
}

function declaredMissing(workload, envelope) {
  const expected = envelope && Array.isArray(envelope.expected_listeners) ? envelope.expected_listeners : [];
  const name = workload && workload.workload_name ? String(workload.workload_name) : "";
  return expected
    .filter((row) => {
      const expectedWorkload = String(row.workload || row.container_name || "");
      return !expectedWorkload || expectedWorkload === name;
    })
    .map((row) => ({
      listener_state: "missing",
      port: row.port,
      bind: row.bind,
      protocol: row.protocol || row.proto,
      workload: row.workload || row.container_name || name,
      comm: row.comm,
    }));
}

function resolveListener(workload, listener, envelope) {
  const unsupported = [];
  if (!listener) {
    const missing = declaredMissing(workload, envelope);
    if (missing.length > 0) return { listener_state: "missing", missing, unsupported };
    return { listener_state: "none", missing: [], unsupported };
  }

  const proto = String(listener.proto || "").toLowerCase();
  if (UNSUPPORTED_PROTO.has(proto)) {
    unsupported.push(proto === "unix" || proto === "unix-domain" ? "unix_domain" : "vsock");
    return { listener_state: "unsupported", missing: [], unsupported };
  }
  if (DOCKER_DNS.has(String(listener.local_addr || ""))) {
    unsupported.push("docker_embedded_dns");
    return { listener_state: "unsupported", missing: [], unsupported };
  }

  const observed = {
    local_port: listener.local_port,
    local_addr: listener.local_addr,
    proto,
    workload: workload && workload.workload_name ? workload.workload_name : "",
    comm: listener.owner_comm,
  };
  const classified = classifyListeners([observed], envelope || { expected_listeners: [] });
  const row = classified.listeners[0];
  return {
    listener_state: row.listener_state,
    missing: classified.missing,
    unsupported,
  };
}

function healthFindings(health, accept) {
  const findings = [];
  if (!health) return ["health_or_evidence_unavailable"];
  const coverage = health.coverage;
  const namedCoverage = coverage === "seeing" || coverage === "degraded" || coverage === "honest_idle";
  const unavailable =
    health.loader_up !== true ||
    health.evidence_writable !== true ||
    health.enroll_readable !== true ||
    health.netns_readable !== true ||
    health.trace_map_available !== true ||
    !namedCoverage;
  if (unavailable || health.protection_state === "coverage_unknown") {
    findings.push("health_or_evidence_unavailable");
  }
  if (coverage === "degraded" || health.protection_state === "degraded") {
    findings.push("health_degraded");
  }
  if (coverage === "honest_idle" && accept) findings.push("health_evidence_contradiction");
  if (health.protection_state === "not_enrolled") findings.push("not_enrolled");
  if (health.protection_state === "quarantined") findings.push("already_quarantined");
  if (health.protection_state === "recovery_required") findings.push("recovery_required");
  if (health.protection_state === "policy_stale") findings.push("stale_policy");
  if (health.protection_state === "protection_stale") findings.push("stale_identity");
  return findings;
}

function policyFindings(envelope, session) {
  const findings = [];
  if (!envelope || envelope.present !== true) findings.push("stale_policy");
  const version = envelope && envelope.policy_version != null ? String(envelope.policy_version) : "";
  if (STALE_POLICY_VERSIONS.has(version)) findings.push("stale_policy");
  if (!envelope || !envelope.applied_sha || !envelope.candidate_sha || !envelope.policy_sha) {
    findings.push("stale_policy");
  } else if (envelope.applied_sha !== envelope.candidate_sha || envelope.applied_sha !== envelope.policy_sha) {
    findings.push("stale_policy");
  }
  if (envelope && envelope.expected_listeners != null && !Array.isArray(envelope.expected_listeners)) {
    findings.push("stale_policy");
  }
  if (session && session.epoch > 0) {
    if (session.policy_unrecoverable) findings.push("recovery_required");
    else if (!envelope || envelope.applied_sha !== session.applied_sha) findings.push("stale_policy");
    else if (
      session.policy_version &&
      String(session.policy_version).startsWith("rollback:") &&
      String(envelope.policy_version || "") !== session.policy_version
    ) {
      findings.push("stale_policy");
    }
  }
  return findings;
}

function identityFindings(workload, identity, listener, accept, now) {
  const findings = [];
  const windowState = attestation(identity, now);
  if (!workload || !workload.enroll_id) findings.push("not_enrolled");
  if (!identity || !isPid(identity.pid) || !isStart(identity.starttime) || !identity.comm) {
    findings.push("identity_unknown");
  }
  if (!workload || !workload.trace_id || !identity || !identity.trace_id) findings.push("identity_unknown");
  if (workload && identity && workload.trace_id && identity.trace_id && workload.trace_id !== identity.trace_id) {
    findings.push("impersonation");
  }
  if (listener && identity && isPid(identity.pid)) {
    if (listener.owner_pid !== identity.pid) findings.push("wrong_process");
    else if (listener.owner_starttime !== identity.starttime || listener.owner_comm !== identity.comm) {
      findings.push("impersonation");
    }
  }
  if (accept && identity && isPid(identity.pid)) {
    if (accept.accepting_pid === identity.pid && accept.accepting_starttime !== identity.starttime) {
      findings.push("impersonation");
    } else if (accept.accepting_pid !== identity.pid || accept.accepting_starttime !== identity.starttime) {
      findings.push("unattributed_accept");
    }
  }
  if (accept) {
    const acceptTrace = typeof accept.accepting_trace_id === "string" ? accept.accepting_trace_id : "";
    if (acceptTrace.length === 0) findings.push("identity_unknown");
    else if (
      (identity && identity.trace_id && acceptTrace !== identity.trace_id) ||
      (workload && workload.trace_id && acceptTrace !== workload.trace_id)
    ) {
      findings.push("impersonation");
    }
  }
  if (windowState === "OUTSIDE_CALLER_WINDOW") findings.push("stale_identity");
  if (windowState === "WINDOW_ABSENT") findings.push("identity_unknown");

  let identityResult = "bound";
  if (findings.includes("wrong_process")) identityResult = "wrong_process";
  else if (findings.includes("impersonation")) identityResult = "impersonation";
  else if (findings.includes("stale_identity")) identityResult = "stale";
  else if (findings.includes("unattributed_accept")) identityResult = "unbound";
  else if (findings.includes("identity_unknown") || findings.includes("not_enrolled")) identityResult = "unknown";
  return { findings, identityResult, windowState };
}

function integrityFindings(workload, envelope) {
  const findings = [];
  const partials = [];
  const observed = workload && workload.executable_digest;
  const expected = workload && workload.executable_digest_expected;
  if (!observed || !expected) findings.push("integrity_unknown");
  else if (observed !== expected) findings.push("modified_executable");

  const imageObserved = workload && workload.image_digest;
  const imageExpected = workload && workload.image_digest_expected;
  const imageRequired = Boolean(envelope && envelope.requires_image_binding === true);
  if (imageObserved && imageExpected) {
    if (imageObserved !== imageExpected) findings.push("image_binding_mismatch");
  } else if (imageRequired) findings.push("integrity_unknown");
  else partials.push("image_digest_binding_not_in_evidence");

  const versionRequired = !envelope || envelope.requires_version_binding !== false;
  if (versionRequired) {
    if (!workload || !workload.version || !workload.version_expected) findings.push("integrity_unknown");
    else if (workload.version !== workload.version_expected) findings.push("version_binding_mismatch");
  }

  let integrityResult = "bound";
  if (findings.includes("modified_executable")) integrityResult = "modified_executable";
  else if (findings.includes("image_binding_mismatch")) integrityResult = "image_unbound";
  else if (findings.includes("version_binding_mismatch")) integrityResult = "version_unbound";
  else if (findings.includes("integrity_unknown")) integrityResult = "unknown";
  return { findings, integrityResult, partials };
}

function credentialFindings(credential, enrollId, integrityResult, authorityClaim) {
  const findings = [];
  let credentialResult = "absent";
  if (authorityClaim === "credential") {
    findings.push("credential_is_not_integrity");
    credentialResult = "not_integrity";
  }
  if (!credential || credential.presented !== true) {
    return { findings, credentialResult };
  }
  if (credential.valid !== true) {
    findings.push("credential_invalid");
    return { findings, credentialResult: "invalid" };
  }
  if (credential.bound_workload_id && enrollId && credential.bound_workload_id !== enrollId) {
    findings.push("valid_credential_wrong_workload");
    return { findings, credentialResult: "valid_wrong_workload" };
  }
  if (!credential.bound_workload_id || integrityResult !== "bound") {
    findings.push("credential_is_not_integrity");
    return { findings, credentialResult: "not_integrity" };
  }
  return { findings, credentialResult: authorityClaim === "credential" ? "not_integrity" : "valid_bound" };
}

function postFindings(input, identity, workload) {
  const behaviors = input.post_accept && Array.isArray(input.post_accept.behaviors) ? input.post_accept.behaviors : [];
  if (!input.accept) {
    return { findings: [], postAccept: behaviors.length > 0 ? "unjoined" : "not_applicable" };
  }
  const findings = [];
  for (const behavior of behaviors) {
    if (!behavior || typeof behavior !== "object") {
      findings.push("post_accept_unjoined");
      continue;
    }
    const escaped =
      behavior.kind === "cgroup_escape" ||
      (behavior.cgroup_id != null && workload && behavior.cgroup_id !== workload.cgroup_id);
    if (escaped) {
      findings.push("child_process_escape");
      continue;
    }
    if (behavior.trace_id && identity && identity.trace_id && behavior.trace_id !== identity.trace_id) {
      findings.push("post_accept_unjoined");
      continue;
    }
    if (behavior.cgroup_id == null || !workload || behavior.cgroup_id !== workload.cgroup_id) {
      findings.push("post_accept_unjoined");
      continue;
    }
    if (behavior.authorized !== true) findings.push("post_accept_denied");
  }
  let postAccept = "permitted";
  if (findings.includes("child_process_escape")) postAccept = "child_escape";
  else if (findings.includes("post_accept_denied")) postAccept = "denied";
  else if (findings.includes("post_accept_unjoined")) postAccept = "unjoined";
  return { findings, postAccept };
}

function acceptJoinsListener(accept, listener) {
  if (!accept || !listener) return false;
  const acceptPort = Number(accept.local_port);
  const listenerPort = Number(listener.local_port);
  if (!Number.isInteger(acceptPort) || !Number.isInteger(listenerPort) || acceptPort !== listenerPort) {
    return false;
  }
  if (accept.proto != null && String(accept.proto) !== "") {
    if (String(accept.proto).toLowerCase() !== String(listener.proto || "").toLowerCase()) return false;
  }
  return true;
}

function evaluateIngress(input, session) {
  if (!asPlainObject(input)) {
    return finishResult({
      reason: "evidence_malformed",
      findings: ["evidence_malformed"],
      listener_state: "none",
      identity_result: "unknown",
      identity_attestation: "WINDOW_ABSENT",
      integrity_result: "unknown",
      credential_result: "absent",
      post_accept: "not_applicable",
      protection_state_echo: null,
      unsupported: [],
      partials: [],
      notices: [],
      policy: policyShape(null),
      grant_id: null,
      grants_carried: session ? session.grants.size : 0,
      boot_id: session ? session.boot_id : null,
      association_not_causation: false,
    });
  }

  const workload = asPlainObject(input.workload);
  const identity = asPlainObject(input.identity);
  const listener = asPlainObject(input.listener);
  const envelope = asPlainObject(input.envelope);
  const health = asPlainObject(input.health);
  const accept = asPlainObject(input.accept);
  const findings = [];
  const unsupported = [];
  const partials = [];
  const notices = [];

  if (input.mutate_live_loader === true) findings.push("live_loader_mutation_refused");
  if (input.authority_claim === "reachability") findings.push("reachability_is_not_authority");

  const listenerView = resolveListener(workload, listener, envelope);
  unsupported.push(...listenerView.unsupported);
  if (listenerView.listener_state === "unsupported") findings.push("unsupported_path");
  if (accept && (accept.mechanism === "io_uring" || accept.path === "io_uring")) {
    unsupported.push("io_uring_accept");
    findings.push("unsupported_path");
  }
  const acceptProto = String((accept && accept.proto) || (listener && listener.proto) || "").toLowerCase();
  if (accept && acceptProto === "udp") {
    unsupported.push("udp_peer_attribution");
    findings.push("unsupported_path");
  }

  if (workload && cgroupUnattributable(workload.cgroup_id)) findings.push("unattributable_cgroup");
  if (!workload) findings.push("not_enrolled");

  findings.push(...healthFindings(health, accept));
  findings.push(...policyFindings(envelope, session));

  const identityView = identityFindings(workload, identity, listener, accept, input.now_ms);
  findings.push(...identityView.findings);

  const integrityView = integrityFindings(workload, envelope);
  findings.push(...integrityView.findings);
  partials.push(...integrityView.partials);

  const credentialView = credentialFindings(
    identity && asPlainObject(identity.credential),
    workload && workload.enroll_id,
    integrityView.integrityResult,
    input.authority_claim,
  );
  findings.push(...credentialView.findings);

  if (listenerView.listener_state === "unexpected") findings.push("unexpected_listener");
  if (
    accept &&
    listener &&
    listenerView.listener_state === "expected" &&
    !acceptJoinsListener(accept, listener)
  ) {
    findings.push("unexpected_listener");
  }

  const postView = postFindings(
    { accept, post_accept: asPlainObject(input.post_accept) },
    identity,
    workload,
  );
  findings.push(...postView.findings);

  const key = grantKey(workload, identity, listener);
  if (session && session.revoked_keys.has(key)) findings.push("revoked");
  if (input.replay_grant_id && session && session.dead.has(input.replay_grant_id)) {
    findings.push("grant_not_carried");
  }

  if (listener && (listener.iface == null || listener.iface === "")) partials.push("iface_unnamed");
  if (envelope && envelope.fail_mode === "fail_closed") notices.push("fail_closed_packet_plane_not_authorized");
  partials.push("full_iface_attribution_not_present");

  const blocking = findings.filter(
    (finding) =>
      finding !== "expected_listener_is_not_authority" &&
      finding !== "undeclared_listener_is_not_authority" &&
      finding !== "missing_listener_is_not_authority" &&
      finding !== "permitted_after_accept",
  );

  if (blocking.length === 0) {
    if (listenerView.listener_state === "expected" && accept) findings.push("permitted_after_accept");
    else if (listenerView.listener_state === "expected") findings.push("expected_listener_is_not_authority");
    else if (listenerView.listener_state === "undeclared") findings.push("undeclared_listener_is_not_authority");
    else findings.push("missing_listener_is_not_authority");
  }

  const ordered = orderFindings(findings);
  const reason = primaryReason(ordered);
  const policy = policyShape(envelope);
  policy.stale = ordered.includes("stale_policy") || ordered.includes("recovery_required");
  if (session && session.epoch > 0 && session.policy_version) policy.version = session.policy_version;

  let issued = null;
  if (reason === "permitted_after_accept" && session) {
    issued = grantId(session, key, policy);
    storeGrant(session, issued, key, policy);
  } else if (session) {
    const stopReason = ordered.find((finding) => REVOKE_ON.has(finding)) || null;
    retireGrant(session, key, stopReason != null);
    if (stopReason) {
      session.events.push({ op: "authority_stopped", reason: stopReason, key });
    }
  } else if (reason === "permitted_after_accept") {
    issued = grantId(null, key, policy);
  }

  const echo =
    health && PROTECTION_STATE_SET.has(health.protection_state) ? health.protection_state : null;

  let identityResult = identityView.identityResult;
  if (ordered.includes("wrong_process")) identityResult = "wrong_process";
  else if (ordered.includes("impersonation")) identityResult = "impersonation";
  else if (ordered.includes("stale_identity")) identityResult = "stale";
  else if (ordered.includes("unattributed_accept")) identityResult = "unbound";
  else if (ordered.includes("identity_unknown") || ordered.includes("not_enrolled")) identityResult = "unknown";

  return finishResult({
    reason,
    findings: ordered,
    listener_state: listenerView.listener_state,
    identity_result: identityResult,
    identity_attestation: identityView.windowState,
    integrity_result: integrityView.integrityResult,
    credential_result: credentialView.credentialResult,
    post_accept: postView.postAccept,
    protection_state_echo: echo,
    unsupported,
    partials,
    notices,
    policy,
    grant_id: issued,
    grants_carried: session ? session.grants.size : issued ? 1 : 0,
    boot_id: session ? session.boot_id : null,
    association_not_causation: Boolean(accept),
    containment: containmentFor(reason, ordered),
  });
}

module.exports = {
  evaluateIngress,
  grantKey,
};
