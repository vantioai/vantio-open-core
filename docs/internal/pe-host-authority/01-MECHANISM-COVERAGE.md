# Mechanism coverage

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_HOST_AUTHORITY_READY_FOR_COUNCIL`

The machine-readable surfaces, mechanisms, and cases live in `packages/pe-host-authority/src/catalog.cjs` and `packages/pe-host-authority/src/cases.cjs`. This page is the reading order. The contract cases in `cases.cjs`, plus the local rows below, are the proof. `HOST-AUTHORITY-MANIFEST.json` records the case count.

Every contract case is `CONTRACT_ONLY`. None of them loaded a program.

## Files — `path_deny_kprobes`, `openat_observe_label`

Supported slice: a non-root, non-loader `open` or `openat` of an enforce exact path, or of a path under an enforce directory prefix, follows the cited `-EACCES` rule. Directory prefixes match only when the stored entry ends in `/` and fits the 64-byte key. The C-string read stops at the first NUL. A relative path is matched as the string that was passed.

Observe maps (`vantio_blocked_exact`, `vantio_blocked_dirs`) label `kprobe_openat2` and do not deny. Enforce maps are a different pair. uid 0 is not labeled.

Limit: `openat2`, `creat`, `truncate`, rename, unlink, link, and symlink are best-effort attaches in the cited file. `write`, `mmap`, `ioctl`, and `execve` are outside the deny set. A path that is not in the maps is outside the rule. uid 0 and the loader tg id are excluded. This force did not read the loader, so whether those kprobes are attached only behind a flag stays `loader_attach_gating` / `NOT_READ_AND_NOT_EXECUTED`.

## Processes — `exec_tracepoints`

Supported slice: `trace_execve` and `trace_execveat` record the filename. They do not deny, including when the filename is an enforce path.

Limit: `SIGKILL` is a cited opt-in after a path deny when `vantio_kill_mode` is set. The architecture file says the loader sets that flag only with `--kill-on-enforce` and `VANTIO_PHANTOM_DENY=1`. That loader path was not read and was not executed. With `kill_mode` 0 the contract records no signal.

## Descendants — `fork_trace_inherit`, `no_child_delegation_object`

Supported slice: `inherit_trace_on_fork` copies the parent trace id when the parent has one. A parent trace of 0 does not mint an id. A child does not receive a wider allowlist. The cited program file has no child-agent delegation object.

Limit: cgroup membership inheritance is a kernel fact this force did not execute. The local child process is a separate row: it is this Node process's child, it sees no `VANTIO_TRACE_ID` and no allowlist, and it is not an eBPF inherit.

## Privileges — `cited_uid0_exclusion`, `local_effective_capabilities`

Supported slice: the cited path-deny rule returns before the override when uid is 0 or the pid is the loader tg id. A workload identity cannot change `mode` in the contract.

Limit: the architecture file says the manifest requests `BPF`, `NET_ADMIN`, and `SYS_ADMIN`, and that live sufficiency of those caps is still open. This force does not close that row. The local row records this process's effective and permitted capability masks and whether this euid can write `/sys/fs/bpf`. On the producer run those masks were zero, the euid was not 0, and the mount was not writable. That is a fact about this process. It is not a loader proof. `local_privilege.disposition` stays `NOT_COVERED` for that shape so the fact cannot be read as enrolled authority.

## Credentials — `no_credential_hook`

Supported slice: presenting a token does not change the authority snapshot, and the token is not copied into the decision. The cited program file has no credential hook. If the path string is in the enforce maps, the file rule applies and the result says `credential_hook: false`.

Limit: `/etc/shadow` is outside the fixture maps, so it stays `NOT_COVERED`. This is not a credential-revocation control.

## Namespaces — `cgroup_id_not_pid`

Supported slice: scoped enrollment is membership of `vantio_enrolled_cgroups`. Cgroup id 0 is not enrolled. A pid or tg id that numerically equals an enrolled cgroup id does not enroll when the cgroup id is 0.

Limit: PID-offset calibration is cited in the architecture file and is `NOT_MEASURED` here.

## Containers — `tc_scoped_egress`, `cgroup_skb_opt_in`

Supported slice, scoped TC, enrolled cgroup: private IPv4 (loopback, `10/8`, `172.16/12`, `192.168/16`, `169.254/16`) passes; a sever CIDR drops before the allowlist; a blocked TCP port drops before the allowlist; an exact or CIDR allow passes; anything else external drops. UDP does not consult the TCP port map. Unenrolled cgroups and cgroup id 0 pass. Audit mode and any other mode pass, and they claim no protection state. Node-wide mode drops without the enrollment check.

`cgroup_skb/egress` uses the same L3 rule only when `cgroup_skb_attached` is true. The fixture leaves it false. The architecture file says `--enroll-watch` does not auto-attach that program. A detached cgroup_skb plane is `NOT_COVERED`. When the contract marks it attached, it does not consult `vantio_enrolled_cgroups` again: attach is the scope. A cgroup id that is absent from the map still follows the L3 rule on that plane.

On TC, a pid in `vantio_tls_severed_pids` drops after the enrollment check and before L3. On an attached cgroup_skb program, the same pid check runs after the mode check and before L3, and that program does not look up `vantio_enrolled_cgroups`. Audit mode on either plane passes before the pid is consulted. An unenrolled TC packet passes before that pid is consulted. A detached cgroup_skb plane stays `NOT_COVERED` even when the pid is in the map. The uprobe cannot block the first matching write; that limit stays in the cited file and is not replayed here.

Limit: VLAN and QinQ parsing is cited and `NOT_REIMPLEMENTED` in this contract. IPv6 unique-local and link-local passes, and other IPv6 destinations drop when no exact allow matches. IPv6 LPM is cited and `NOT_REIMPLEMENTED`; a non-empty `allow_cidr_v6` returns that gap instead of a drop or a pass. Forwarded traffic with cgroup id 0 passes TC and is not covered by a detached cgroup_skb program.

## Devices — `no_device_hook`

Supported slice: the cited program file has no major/minor hook. `mknod` is `NOT_COVERED`. An unlisted device path is `NOT_COVERED`. A device path that has been added to the enforce exact map follows the file rule and still reports `matches_device_number: false`.

## Persistence — `persistence_via_path_deny`

Supported slice: `/etc/crontab` is in the fixture enforce exact map, so non-root `open` follows the file deny rule and `persistence_path_enrolled` is true. Rename of that path is best-effort.

Limit: an unlisted unit path such as `/lib/systemd/system/agent.service` stays `NOT_COVERED`. There is no persistence hunter beyond the path strings in the maps.

## Resource use — `no_host_resource_hook`

Supported slice: the cited program file has no host CPU, memory, GPU, or replication quota. A host quota attempt returns `NOT_COVERED` and `protection_state: coverage_unknown`. A Gate `spend_cap_usd` is recorded as plane `APPLICATION_PATH` and does not fill this surface.

## Monitor disablement — `workload_cannot_disable`

Supported slice: a workload actor cannot unpin maps or clear the mode. The contract state stays unchanged.

Limit: a privileged actor is `NAMED_RESIDUAL` / `privileged_pe_disable`. The contract does not flip the mode to make that residual look successful.

## Policy tampering — `policy_attribution_contract`

Supported slice: a workload actor cannot activate policy. A security actor missing `decision_id`, `version`, `actor_id`, or `rollback_target` is `REJECTED_UNATTRIBUTED`. A security actor with those four fields produces `ACCEPTED_CONTRACT_RECORD_ONLY` with `kernel_activated: false` and `maps_changed: false`.

Limit: a privileged unsigned load is `NAMED_RESIDUAL` / `root_unsigned_map_load`. The cited program file does not check a signature. This contract record is not a kernel activation.

## Evidence tampering — `evidence_hash_chain`

Supported slice: a temporary NDJSON file chains `sha256(prev + newline + canonical record)`. Append verifies as `CHAIN_INTACT`. A truncated copy and a rewritten copy verify as breaks (`TRUNCATED_TAIL`, `HASH_MISMATCH`). The untouched copy still verifies.

Limit: every evidence row carries `prevention: FAIL_CLOSED_GAP`. The owner write succeeds. The chain detects the change. This is not durable storage, not a Spanner commit, and not a WORM claim. `spanner_live_insert` stays `NOT_EXECUTED`.
