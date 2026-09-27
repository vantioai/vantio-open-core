# Missing prerequisites

Audience: INTERNAL_RESTRICTED

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

Evidence tier: `UNSET`

These are the prerequisites whose absence stopped the required sequence. They are stated as resources the next authorized lab still needs. This packet does not authorize that lab.

## 1. Clean host

A host that can be reset to a recorded image digest, with a before-state for disk, package database, systemd units, and `/sys/fs/bpf`.

This producer pod is cgroup `0::/system.slice/pod-gaa3lai7yrhjnlcigqmih3fb4q-4c8e13b4/init` on kernel `6.12.94+`. It already contains the Cursor agent toolchain, including `cargo`, Node `v22.14.0`, and clang `18.1.3`. The merged design does not provision a replacement host. This force did not create a VM, a container image, or a cluster.

Observed absences on the pod (`$HOME/.vantio`, port `5001`, `/run/vantio`, pinned BPF objects) describe the pod at probe time. They are not a baseline certificate.

## 2. Compatibility floor from the merged packaging plan

`docs/planning/phantom-engine-production/03-P2-PREREQUISITE-COMPATIBILITY.md` names the floor. On this pod:

| Prerequisite | This pod |
| --- | --- |
| Linux kernel ≥ 5.8 | Present as `6.12.94+` |
| BTF at `/sys/kernel/btf/vmlinux` | Absent, including for root |
| cgroup v2 | Mounted. Controllers: `cpuset cpu io memory hugetlb pids` |
| bpffs at `/sys/fs/bpf` | Mounted, mode `1700`, zero entries |
| `BPF`, `NET_ADMIN`, `SYS_ADMIN` | Present in the sudo root set (`Current: =eip`). Absent from uid 1000 (`Current: =i`) |
| `curl` in the runtime | Present, curl `8.5.0` |
| `libssl.so.3` or `libgnutls.so.30` | Both present |
| Node interface name | `ip` is absent, so no interface was recorded |
| Kernel config and modules for `6.12.94+` | `/proc/config.gz`, `/boot/config-6.12.94+`, and `/lib/modules/6.12.94+` are absent |
| `bpftool` | Absent |
| Container runtime and cluster tools | `docker`, `kind`, `kubectl`, and `helm` are absent |

P2 says a host that fails one of the floor checks is `REQUIRED_DEPENDENCY_MISSING` and is not a covered node. The missing BTF file is that failure.

`unprivileged_bpf_disabled=2` locks unprivileged BPF off. Clang can target `bpfel`. A compiler target does not create `/sys/kernel/btf/vmlinux`.

## 3. Artifact

A readable Phantom Engine tip, plus the bytes named in `02-P1-PACKAGE-ARTIFACT-PROVENANCE.md`: loader binary, post-OSABI-patch embedded object, image digest, and chart version.

This run needs all of the following before an artifact row can exist:

- A credential that can read `vantioai/vantio-phantom-engine`. `gh repo view` on this pod returned `Could not resolve to a Repository`.
- A local checkout of the authorized tip. None is mounted.
- `GHCR_TOKEN` or an equivalent registry credential. Both `GHCR_TOKEN` and `GITHUB_TOKEN` were unset.
- A digest pin. P1 leaves `ghcr.io/vantioai/vantio-phantom-engine:0.1.0` as `UNVERIFIED` and forbids treating tag `latest` as a pin.

CLI `0.3.24` stays closed. The version string in `packages/vantio-cli/package.json` was read. No tarball was packed.

## 4. Install through residual

The later sequence rows share one gate: an install of a verified artifact on a host that already passed the compatibility floor.

Also absent, row by row:

| Row | Additional missing piece |
| --- | --- |
| Observe on the host | An installed observe mode. The loopback exerciser is a different contract. |
| Ingress and egress | A loader attachment and a named node interface. Egress also needs the `cgroup_skb/egress` program the packaging plan says `--enroll-watch` does not auto-attach. |
| Allowed and denied | An enrolled policy and a loaded allow/drop path. |
| App/host correlation | The loader's PID-offset file. `/run/vantio` is absent. |
| Proposal | The customer-owned channel in `EG-SUB-6`, which is `UNSATISFIED`. |
| Simulation | An installed simulation mode. |
| Canary | A second host and an installed version. |
| Enforcement | BTF, a loader, and a non-empty attachment. This force did not call the loader. |
| Restart | A systemd unit. |
| Reboot | A lab host whose reboot is in charter, and a post-boot observer. Reboot was not issued on this pod. |
| Degradation | A running enforcer. |
| Recovery | Customer-held recovery material and `pe_customer_pack.py`, which is not in this repository. |
| Evidence export | A customer-held copy from an installed host. |
| Revocation | A grant and a customer root. No API key was created. |
| Rollback and upgrade | Two pinned digests. No publish was performed. |
| Uninstall | An install to remove. |
| Residual inspection | The post-uninstall map, unit, and package inventory. |

## 5. Phantom-Box

A Phantom-Box soak is not a substitute prerequisite and was not collected. Port `5001` had zero listeners. `VANTIO_SOAK_LOCAL` was unset. The exerciser treats `VANTIO_SOAK_LOCAL=1` and an ingest URL on port `5001` as exit `21`.
