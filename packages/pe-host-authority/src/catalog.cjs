"use strict";

/**
 * Cited mechanisms for the internal host-authority proof.
 * Program names and map names are identifiers from
 * vantio-phantom-engine tip 631e435315cd780d83d3259e111893c1d0569bc3.
 * This module does not contain that repository's source.
 */

const PRIVATE_TIP = "631e435315cd780d83d3259e111893c1d0569bc3";

const CITATIONS = {
  ebpf_program_file: {
    repo: "vantioai/vantio-phantom-engine",
    path: "vantio-phantom-engine/src/main.rs",
    git_sha: PRIVATE_TIP,
    blob: "5b20674536e55faecd5cde75f72a9f0140bb6b2b",
    this_force_read: "FULL_FILE",
  },
  common_contract: {
    repo: "vantioai/vantio-phantom-engine",
    path: "vantio-common/src/lib.rs",
    git_sha: PRIVATE_TIP,
    blob: "f764460fc8ee28c9571be547f317d04cabc9153c",
    this_force_read: "FULL_FILE",
  },
  architecture_state: {
    repo: "vantioai/vantio-phantom-engine",
    path: "architecture_state.md",
    git_sha: PRIVATE_TIP,
    blob: "84d53654894180cbf351d62231f90e564504162c",
    this_force_read: "FULL_FILE",
  },
  reference_monitor: {
    repo: "vantioai/vantio-phantom-engine",
    path: "docs/enterprise/REFERENCE_MONITOR.md",
    git_sha: PRIVATE_TIP,
    blob: "57b0d613267a9ea57b2f94897b5c839727bc5e1f",
    this_force_read: "FULL_FILE",
  },
  loader_source: {
    repo: "vantioai/vantio-phantom-engine",
    path: "vantio-loader/src/main.rs",
    git_sha: PRIVATE_TIP,
    blob: "773f3ab4c201079db331bd862dc5b31ed8a6ba77",
    this_force_read: "NOT_READ",
  },
};

const PRODUCER_CLASSIFICATION = "PE_HOST_AUTHORITY_READY_FOR_COUNCIL";

const DISPOSITIONS = [
  "DENIED_BY_CITED_MECHANISM",
  "LABELED_NOT_DENIED",
  "OBSERVED_ONLY",
  "CITED_DROP",
  "CITED_ALLOW",
  "ENROLLED_BY_CGROUP_ID",
  "CITED_NO_SIGNAL",
  "CITED_OPT_IN_NOT_EXECUTED",
  "INHERIT_NO_WIDEN",
  "REJECTED_NOT_AN_AUTHORITY_INPUT",
  "REJECTED_WORKLOAD",
  "REJECTED_UNATTRIBUTED",
  "NOT_COVERED",
  "NAMED_RESIDUAL",
  "BEST_EFFORT_NOT_PROVED",
  "DETECTED",
  "CHAIN_INTACT",
  "FAIL_CLOSED_GAP",
  "ACCEPTED_CONTRACT_RECORD_ONLY",
  "NOT_REIMPLEMENTED",
];

const PATH_DENY_SYSCALLS = {
  open: { program: "kprobe_open_deny", nr: 2, attach: "primary" },
  openat: { program: "kprobe_openat_deny", nr: 257, attach: "primary" },
  openat2: { program: "kprobe_openat2_deny", nr: 437, attach: "best_effort" },
  creat: { program: "kprobe_creat_deny", nr: 85, attach: "best_effort" },
  truncate: { program: "kprobe_truncate_deny", nr: 76, attach: "best_effort" },
  rename: { program: "kprobe_rename_deny", nr: 82, attach: "best_effort", second_path: true },
  renameat: { program: "kprobe_renameat_deny", nr: 264, attach: "best_effort", second_path: true },
  renameat2: { program: "kprobe_renameat2_deny", nr: 316, attach: "best_effort", second_path: true },
  unlink: { program: "kprobe_unlink_deny", nr: 87, attach: "best_effort" },
  unlinkat: { program: "kprobe_unlinkat_deny", nr: 263, attach: "best_effort" },
  link: { program: "kprobe_link_deny", nr: 86, attach: "best_effort", second_path: true },
  linkat: { program: "kprobe_linkat_deny", nr: 265, attach: "best_effort", second_path: true },
  symlink: { program: "kprobe_symlink_deny", nr: 88, attach: "best_effort", second_path: true },
  symlinkat: { program: "kprobe_symlinkat_deny", nr: 266, attach: "best_effort", second_path: true },
};

const FIXTURE_HOST = {
  enforce_exact: ["/etc/crontab"],
  enforce_dirs: ["/var/lib/vantio-proof/"],
  blocked_exact: ["/tmp/observe-only"],
  blocked_dirs: ["/tmp/observe-dir/"],
  loader_tgid: 4242,
  mode: "scoped",
  kill_mode: 0,
  enrolled_cgroups: [21],
  allow_exact_v4: ["1.1.1.1"],
  allow_cidr_v4: ["1.1.1.0/24"],
  sever_cidr_v4: ["9.9.9.9/32"],
  blocked_tcp_ports: [5432],
  allow_exact_v6: [],
  allow_cidr_v6: [],
  cgroup_skb_attached: false,
  persistence_exact: ["/etc/crontab"],
  device_exact: [],
};

const SURFACES = [
  {
    id: "files",
    mechanisms: ["path_deny_kprobes", "openat_observe_label"],
    supported_authority:
      "Non-root, non-loader open and openat of an enforce exact path or directory prefix follow the cited deny rule. Observe-label maps do not deny. Unlisted paths and syscalls outside the deny set are outside the rule.",
  },
  {
    id: "processes",
    mechanisms: ["exec_tracepoints", "path_deny_kprobes"],
    supported_authority:
      "execve and execveat are observe-only in the cited tracepoints. SIGKILL is a separate opt-in after a path deny, and it is not executed here.",
  },
  {
    id: "descendants",
    mechanisms: ["fork_trace_inherit", "no_child_delegation_object"],
    supported_authority:
      "A child copies the parent trace id when the parent has one, and does not receive a wider allowlist. No child-agent delegation object exists in the cited program file.",
  },
  {
    id: "privileges",
    mechanisms: ["cited_uid0_exclusion", "local_effective_capabilities"],
    supported_authority:
      "The cited path-deny rule skips uid 0 and the loader tg id. This process's effective capability set is recorded as a local fact. Loader capability sufficiency is not re-proved.",
  },
  {
    id: "credentials",
    mechanisms: ["no_credential_hook", "path_deny_kprobes"],
    supported_authority:
      "A presented token does not change authority. The cited program file has no credential hook. A credential path is covered only when the file rule matches that path string.",
  },
  {
    id: "namespaces",
    mechanisms: ["cgroup_id_not_pid"],
    supported_authority:
      "Scoped enrollment is a cgroup id. A pid number, including a number that collides with a cgroup id, is not an enrollment key. PID-offset calibration is not measured here.",
  },
  {
    id: "containers",
    mechanisms: ["tc_scoped_egress", "cgroup_skb_opt_in", "tls_content_sever"],
    supported_authority:
      "Scoped TC drops enrolled cgroups' non-allowlisted external IPv4 after the enrollment check. On TC, a content-sever pid drops only after that check. An attached cgroup_skb program applies the same L3 rule and the same content-sever check without consulting the enrolled map. A detached cgroup_skb program does not run.",
  },
  {
    id: "devices",
    mechanisms: ["no_device_hook", "path_deny_kprobes"],
    supported_authority:
      "The cited program file has no device-number hook. A device path is covered only as a path string under the file rule.",
  },
  {
    id: "persistence",
    mechanisms: ["persistence_via_path_deny"],
    supported_authority:
      "A persistence path is covered only when that path string is in the enforce maps. Unlisted persistence locations stay outside the rule.",
  },
  {
    id: "resource_use",
    mechanisms: ["no_host_resource_hook"],
    supported_authority:
      "The cited program file has no host CPU, memory, GPU, or replication quota. A Gate spend cap is a different plane and does not fill this surface.",
  },
  {
    id: "monitor_disablement",
    mechanisms: ["workload_cannot_disable"],
    supported_authority:
      "A workload identity cannot clear enforcement in this contract. A privileged operator remains a named residual and is not recorded as a pass.",
  },
  {
    id: "policy_tampering",
    mechanisms: ["policy_attribution_contract"],
    supported_authority:
      "An unattributed or workload policy change does not become a contract record. An attributed security record stays off the kernel maps. Root loading unsigned maps remains a named residual.",
  },
  {
    id: "evidence_tampering",
    mechanisms: ["evidence_hash_chain"],
    supported_authority:
      "An append-only hash chain detects truncate and rewrite of the proof ledger. The file owner can still change the file. That prevention gap stays fail-closed.",
  },
];

const MECHANISMS = {
  path_deny_kprobes: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    maps: ["vantio_enforce_exact", "vantio_enforce_dirs", "vantio_self_tgid"],
    this_force: "CONTRACT_ONLY",
  },
  openat_observe_label: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    programs: ["kprobe_openat2"],
    maps: ["vantio_blocked_exact", "vantio_blocked_dirs"],
    this_force: "CONTRACT_ONLY",
  },
  exec_tracepoints: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    programs: ["trace_execve", "trace_execveat"],
    this_force: "CONTRACT_ONLY",
  },
  fork_trace_inherit: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    programs: ["inherit_trace_on_fork"],
    maps: ["vantio_trace_map"],
    this_force: "CONTRACT_ONLY",
  },
  no_child_delegation_object: {
    kind: "ABSENCE_IN_CITED_PROGRAM_FILE",
    citation: "ebpf_program_file",
    this_force: "ABSENCE_BOUNDED_TO_CITED_FILE",
  },
  cited_uid0_exclusion: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    this_force: "CONTRACT_ONLY",
  },
  local_effective_capabilities: {
    kind: "LOCAL_PROCESS_FACT",
    this_force: "EXECUTED_ON_THIS_PROCESS",
  },
  no_credential_hook: {
    kind: "ABSENCE_IN_CITED_PROGRAM_FILE",
    citation: "ebpf_program_file",
    this_force: "ABSENCE_BOUNDED_TO_CITED_FILE",
  },
  cgroup_id_not_pid: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    maps: ["vantio_enrolled_cgroups"],
    this_force: "CONTRACT_ONLY",
  },
  tc_scoped_egress: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    programs: ["tc_enforce"],
    maps: ["vantio_enforce_mode", "vantio_enrolled_cgroups", "vantio_allowlist", "vantio_allowlist_cidr4", "vantio_sever_cidr4", "vantio_blocked_ports"],
    this_force: "CONTRACT_ONLY",
  },
  cgroup_skb_opt_in: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    programs: ["cgroup_skb_egress_enforce"],
    this_force: "CONTRACT_ONLY",
  },
  tls_content_sever: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    maps: ["vantio_tls_severed_pids"],
    this_force: "CONTRACT_ONLY",
  },
  no_device_hook: {
    kind: "ABSENCE_IN_CITED_PROGRAM_FILE",
    citation: "ebpf_program_file",
    this_force: "ABSENCE_BOUNDED_TO_CITED_FILE",
  },
  persistence_via_path_deny: {
    kind: "CITED_KERNEL_PROGRAMS",
    citation: "ebpf_program_file",
    this_force: "CONTRACT_ONLY",
  },
  no_host_resource_hook: {
    kind: "ABSENCE_IN_CITED_PROGRAM_FILE",
    citation: "ebpf_program_file",
    this_force: "ABSENCE_BOUNDED_TO_CITED_FILE",
  },
  workload_cannot_disable: {
    kind: "CONTRACT_RULE",
    citation: "reference_monitor",
    this_force: "CONTRACT_ONLY",
  },
  policy_attribution_contract: {
    kind: "CONTRACT_RULE",
    citation: "reference_monitor",
    this_force: "CONTRACT_ONLY",
  },
  evidence_hash_chain: {
    kind: "LOCAL_USERSPACE_LEDGER",
    this_force: "EXECUTED_ON_TEMP_FILE",
  },
};

const NOT_REIMPLEMENTED = [
  {
    id: "vlan_qinq_parse",
    cited_in: "ebpf_program_file",
    this_force: "NOT_REIMPLEMENTED",
  },
  {
    id: "ipv6_lpm",
    cited_in: "ebpf_program_file",
    this_force: "NOT_REIMPLEMENTED",
  },
  {
    id: "pid_offset_calibration",
    cited_in: "architecture_state",
    this_force: "NOT_MEASURED",
  },
  {
    id: "loader_attach_gating",
    cited_in: "loader_source",
    this_force: "NOT_READ_AND_NOT_EXECUTED",
  },
  {
    id: "cgroup_skb_k8s_enroll_watch_attach",
    cited_in: "architecture_state",
    this_force: "CITED_GAP_NOT_EXECUTED",
  },
  {
    id: "minimal_caps_sufficiency",
    cited_in: "architecture_state",
    this_force: "NOT_INDEPENDENTLY_VERIFIED",
  },
  {
    id: "spanner_live_insert",
    cited_in: "architecture_state",
    this_force: "NOT_EXECUTED",
  },
];

const CLAIMS = [
  "This is an internal contract proof of cited mechanisms, plus local userspace checks on this process.",
  "No eBPF program was loaded.",
  "The Phantom Engine loader was not modified.",
  "Each surface names its mechanism and the limit of that mechanism.",
  "This host is not under a claim of universal Linux control.",
  "Privileged disable of the monitor remains a named residual.",
  "Hash-chain detection does not stop the file owner from changing the file.",
  "A Gate spend cap is an application-path control and is not host resource authority.",
  "PE_HOST_AUTHORITY_READY_FOR_COUNCIL means ready for a separate council. It is not a council verdict.",
];

const PATH_KEY_LEN = 64;

function freeze(value) {
  if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
  for (const child of Object.values(value)) freeze(child);
  return Object.freeze(value);
}

freeze(FIXTURE_HOST);
freeze(SURFACES);
freeze(MECHANISMS);
freeze(NOT_REIMPLEMENTED);
freeze(CLAIMS);
freeze(DISPOSITIONS);
freeze(CITATIONS);
freeze(PATH_DENY_SYSCALLS);

module.exports = {
  PRIVATE_TIP,
  CITATIONS,
  PRODUCER_CLASSIFICATION,
  DISPOSITIONS,
  PATH_DENY_SYSCALLS,
  FIXTURE_HOST,
  SURFACES,
  MECHANISMS,
  NOT_REIMPLEMENTED,
  CLAIMS,
  PATH_KEY_LEN,
};
