"use strict";

const { PATH_DENY_SYSCALLS, DISPOSITIONS } = require("./catalog.cjs");
const { pathBuffer, matchesEnforce, matchesBlocked } = require("./path-match.cjs");
const { decideV4, decideV6, enrolled } = require("./egress.cjs");
const { inheritTrace, childWiden } = require("./descendant.cjs");

function base(partial) {
  const decision = {
    kernel_executed: false,
    universal_linux: false,
    authority_widened: false,
    execution: "CONTRACT_ONLY",
    ...partial,
  };
  if (!DISPOSITIONS.includes(decision.disposition)) {
    throw new Error(`unknown disposition ${decision.disposition}`);
  }
  return decision;
}

function snapshot(host) {
  return JSON.stringify({
    mode: host.mode,
    kill_mode: host.kill_mode,
    enforce_exact: host.enforce_exact,
    enforce_dirs: host.enforce_dirs,
    enrolled_cgroups: host.enrolled_cgroups,
    allow_exact_v4: host.allow_exact_v4,
    allow_cidr_v4: host.allow_cidr_v4,
  });
}

function pathMatch(host, path) {
  return matchesEnforce(host, pathBuffer(path));
}

function decidePath(host, attempt) {
  const syscall = PATH_DENY_SYSCALLS[attempt.op];
  if (!syscall) {
    return base({
      disposition: "NOT_COVERED",
      mechanism_id: "path_deny_kprobes",
      reason: "syscall_not_in_deny_set",
      op: attempt.op,
    });
  }
  if (attempt.uid === 0) {
    return base({
      disposition: "NAMED_RESIDUAL",
      mechanism_id: "cited_uid0_exclusion",
      residual: "uid_0_excluded",
      program: syscall.program,
    });
  }
  if (attempt.pid === host.loader_tgid) {
    return base({
      disposition: "NAMED_RESIDUAL",
      mechanism_id: "cited_uid0_exclusion",
      residual: "loader_tgid_excluded",
      program: syscall.program,
    });
  }
  const paths = [attempt.path];
  if (syscall.second_path && attempt.path2) paths.push(attempt.path2);
  const matched = paths.some((item) => pathMatch(host, item));
  if (!matched) {
    return base({
      disposition: "NOT_COVERED",
      mechanism_id: "path_deny_kprobes",
      reason: attempt.path.startsWith("/") ? "path_not_in_enforce_maps" : "path_string_not_resolved",
      program: syscall.program,
    });
  }
  if (syscall.attach === "best_effort") {
    return base({
      disposition: "BEST_EFFORT_NOT_PROVED",
      mechanism_id: "path_deny_kprobes",
      program: syscall.program,
      decision_if_attached: "EACCES",
      reason: "attach_not_proved_this_force",
    });
  }
  return base({
    disposition: "DENIED_BY_CITED_MECHANISM",
    mechanism_id: "path_deny_kprobes",
    program: syscall.program,
    effect: "EACCES",
  });
}

function decideObserve(host, attempt) {
  const buf = pathBuffer(attempt.path);
  if (attempt.uid === 0 || !matchesBlocked(host, buf)) {
    return base({
      disposition: "OBSERVED_ONLY",
      mechanism_id: "openat_observe_label",
      program: "kprobe_openat2",
      effect: "NONE",
      reason: attempt.uid === 0 ? "uid_0_not_labeled" : "path_not_in_observe_maps",
    });
  }
  return base({
    disposition: "LABELED_NOT_DENIED",
    mechanism_id: "openat_observe_label",
    program: "kprobe_openat2",
    effect: "NONE",
    label: "ACTION_BLOCKED",
  });
}

function decideFiles(host, attempt) {
  if (attempt.op === "observe_open") return decideObserve(host, attempt);
  return decidePath(host, attempt);
}

function decideProcesses(host, attempt) {
  if (attempt.op === "execve" || attempt.op === "execveat") {
    const onEnforcePath = pathMatch(host, attempt.path);
    return base({
      disposition: "OBSERVED_ONLY",
      mechanism_id: "exec_tracepoints",
      program: attempt.op === "execve" ? "trace_execve" : "trace_execveat",
      effect: "NONE",
      residual: onEnforcePath ? "execve_not_in_path_deny_set" : null,
    });
  }
  if (attempt.op === "kill_after_deny") {
    const pathDecision = decidePath(host, { ...attempt, op: attempt.deny_op || "open" });
    const wouldDeny = pathDecision.disposition === "DENIED_BY_CITED_MECHANISM"
      || pathDecision.decision_if_attached === "EACCES";
    if (!wouldDeny) {
      return base({
        disposition: "CITED_NO_SIGNAL",
        mechanism_id: "path_deny_kprobes",
        reason: "path_not_denied",
      });
    }
    if (host.kill_mode === 0) {
      return base({
        disposition: "CITED_NO_SIGNAL",
        mechanism_id: "path_deny_kprobes",
        reason: "kill_mode_off",
      });
    }
    return base({
      disposition: "CITED_OPT_IN_NOT_EXECUTED",
      mechanism_id: "path_deny_kprobes",
      signal: "SIGKILL",
      hitl: true,
      reason: "kill_mode_requires_loader_flags_not_executed",
    });
  }
  throw new Error(`unknown process op ${attempt.op}`);
}

function decideDescendants(host, attempt) {
  if (attempt.op === "fork_inherit") {
    const parent = {
      trace_id: attempt.trace_id,
      allow_cidr_v4: host.allow_cidr_v4,
    };
    const child = inheritTrace(parent);
    return base({
      disposition: "INHERIT_NO_WIDEN",
      mechanism_id: "fork_trace_inherit",
      program: "inherit_trace_on_fork",
      child_trace_id: child.trace_id,
      child_allow_cidr_v4: child.allow_cidr_v4,
      minted: child.minted,
      widened: false,
    });
  }
  if (attempt.op === "child_widen_cidr") {
    const parent = { trace_id: attempt.trace_id || "0x0c1a", allow_cidr_v4: host.allow_cidr_v4 };
    const result = childWiden(parent, attempt.cidr);
    return base({
      disposition: result.disposition,
      mechanism_id: "no_child_delegation_object",
      added: result.added,
      allow_cidr_v4: result.allow_cidr_v4,
    });
  }
  throw new Error(`unknown descendant op ${attempt.op}`);
}

function decidePrivileges(host, attempt) {
  if (attempt.op === "workload_set_mode") {
    return base({
      disposition: "REJECTED_WORKLOAD",
      mechanism_id: "cited_uid0_exclusion",
      mode_before: host.mode,
      mode_after: host.mode,
      reason: "workload_cannot_set_enforce_mode",
    });
  }
  if (attempt.op === "uid0_open") {
    return decidePath(host, { op: "open", path: attempt.path, uid: 0, pid: attempt.pid || 1 });
  }
  throw new Error(`unknown privilege op ${attempt.op}`);
}

function decideCredentials(host, attempt) {
  if (attempt.op === "present_token") {
    return base({
      disposition: "REJECTED_NOT_AN_AUTHORITY_INPUT",
      mechanism_id: "no_credential_hook",
      token_recorded: false,
      snapshot_unchanged: true,
    });
  }
  if (attempt.op === "open_path") {
    const decision = decidePath(host, { op: "open", path: attempt.path, uid: attempt.uid, pid: attempt.pid });
    return base({
      ...decision,
      mechanism_id: decision.disposition === "NOT_COVERED" ? "no_credential_hook" : decision.mechanism_id,
      credential_hook: false,
    });
  }
  throw new Error(`unknown credential op ${attempt.op}`);
}

function decideNamespaces(host, attempt) {
  if (attempt.op !== "attribute_identity") {
    throw new Error(`unknown namespace op ${attempt.op}`);
  }
  const isEnrolled = enrolled(host, attempt.cgroup_id);
  return base({
    disposition: isEnrolled ? "ENROLLED_BY_CGROUP_ID" : "NOT_COVERED",
    mechanism_id: "cgroup_id_not_pid",
    enrolled: isEnrolled,
    reason: isEnrolled ? "cgroup_id_enrolled" : (attempt.cgroup_id === 0 ? "cgroup_id_0" : "cgroup_not_enrolled"),
    pid_used_as_key: false,
    offset_measured: false,
  });
}

function decideContainers(host, attempt) {
  if (attempt.op === "egress_v4") return base({ ...decideV4(host, attempt), universal_linux: false, authority_widened: false });
  if (attempt.op === "egress_v6") return base({ ...decideV6(host, attempt), universal_linux: false, authority_widened: false });
  throw new Error(`unknown container op ${attempt.op}`);
}

function decideDevices(host, attempt) {
  if (attempt.op === "mknod") {
    return base({
      disposition: "NOT_COVERED",
      mechanism_id: "no_device_hook",
      reason: "device_number_not_a_hook",
      major: attempt.major,
      minor: attempt.minor,
    });
  }
  if (attempt.op === "open_path") {
    const decision = decidePath(host, { op: "open", path: attempt.path, uid: attempt.uid, pid: attempt.pid });
    return base({
      ...decision,
      mechanism_id: decision.disposition === "NOT_COVERED" && !pathMatch(host, attempt.path)
        ? "no_device_hook"
        : decision.mechanism_id,
      matches_device_number: false,
    });
  }
  throw new Error(`unknown device op ${attempt.op}`);
}

function decidePersistence(host, attempt) {
  const enrolledPath = host.persistence_exact.includes(attempt.path);
  const decision = decidePath(host, attempt);
  return base({
    ...decision,
    mechanism_id: "persistence_via_path_deny",
    persistence_path_enrolled: enrolledPath,
    file_rule: decision.mechanism_id,
  });
}

function decideResource(attempt) {
  if (attempt.op === "host_quota") {
    return base({
      disposition: "NOT_COVERED",
      mechanism_id: "no_host_resource_hook",
      protection_state: "coverage_unknown",
      kind: attempt.kind,
    });
  }
  if (attempt.op === "gate_spend_cap") {
    return base({
      disposition: "NOT_COVERED",
      mechanism_id: "no_host_resource_hook",
      protection_state: "coverage_unknown",
      different_plane: "APPLICATION_PATH",
    });
  }
  throw new Error(`unknown resource op ${attempt.op}`);
}

function decideMonitor(host, attempt) {
  if (attempt.actor === "workload") {
    return base({
      disposition: "REJECTED_WORKLOAD",
      mechanism_id: "workload_cannot_disable",
      op: attempt.op,
      mode_after: host.mode,
      enrolled_after: host.enrolled_cgroups.slice(),
    });
  }
  if (attempt.actor === "privileged") {
    return base({
      disposition: "NAMED_RESIDUAL",
      mechanism_id: "workload_cannot_disable",
      residual: "privileged_pe_disable",
      op: attempt.op,
      mode_after: host.mode,
      state_changed_in_contract: false,
    });
  }
  throw new Error(`unknown monitor actor ${attempt.actor}`);
}

function decidePolicy(host, attempt) {
  if (attempt.actor === "workload") {
    return base({
      disposition: "REJECTED_WORKLOAD",
      mechanism_id: "policy_attribution_contract",
      contract_active: false,
      kernel_activated: false,
      maps_changed: false,
      snapshot: snapshot(host),
    });
  }
  if (attempt.actor === "privileged") {
    return base({
      disposition: "NAMED_RESIDUAL",
      mechanism_id: "policy_attribution_contract",
      residual: "root_unsigned_map_load",
      contract_active: false,
      kernel_activated: false,
      maps_changed: false,
    });
  }
  if (attempt.actor === "security") {
    const missing = ["decision_id", "version", "actor_id", "rollback_target"].filter((key) => !attempt[key]);
    if (missing.length > 0) {
      return base({
        disposition: "REJECTED_UNATTRIBUTED",
        mechanism_id: "policy_attribution_contract",
        reason: "missing_attribution",
        missing,
        contract_active: false,
        kernel_activated: false,
        maps_changed: false,
      });
    }
    return base({
      disposition: "ACCEPTED_CONTRACT_RECORD_ONLY",
      mechanism_id: "policy_attribution_contract",
      contract_active: true,
      kernel_activated: false,
      maps_changed: false,
      version: attempt.version,
    });
  }
  throw new Error(`unknown policy actor ${attempt.actor}`);
}

function evaluate(host, attempt) {
  switch (attempt.surface) {
    case "files":
      return decideFiles(host, attempt);
    case "processes":
      return decideProcesses(host, attempt);
    case "descendants":
      return decideDescendants(host, attempt);
    case "privileges":
      return decidePrivileges(host, attempt);
    case "credentials":
      return decideCredentials(host, attempt);
    case "namespaces":
      return decideNamespaces(host, attempt);
    case "containers":
      return decideContainers(host, attempt);
    case "devices":
      return decideDevices(host, attempt);
    case "persistence":
      return decidePersistence(host, attempt);
    case "resource_use":
      return decideResource(attempt);
    case "monitor_disablement":
      return decideMonitor(host, attempt);
    case "policy_tampering":
      return decidePolicy(host, attempt);
    case "evidence_tampering":
      throw new Error("evidence_tampering is executed by proveEvidence, not the pure evaluator");
    default: {
      const unknown = attempt.surface;
      throw new Error(`unknown surface ${unknown}`);
    }
  }
}

module.exports = {
  evaluate,
  snapshot,
};
