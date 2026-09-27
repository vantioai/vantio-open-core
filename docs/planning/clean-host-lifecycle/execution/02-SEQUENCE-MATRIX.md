# Required proof sequence

Audience: INTERNAL_RESTRICTED

Environment class: `CLEAN_HOST_INTERNAL_PROOF`

Evidence tier: `UNSET`

Every row is `BLOCKED_INFRA`. A `BLOCKED_INFRA` row has no host result. The merged-design exerciser in `03-MERGED-DESIGN-EXERCISER.md` is a separate process result and does not change a row to a pass.

Phantom-Box state was not used to fill any row.

| # | Step | Result | Missing prerequisite |
| --- | --- | --- | --- |
| 1 | Clean baseline | `BLOCKED_INFRA` | A resettable host image with a recorded before-digest. This pod's cgroup is `0::/system.slice/pod-gaa3lai7yrhjnlcigqmih3fb4q-4c8e13b4/init`. The merged design excludes provisioning a second machine, VM image, container build, or Kubernetes job. |
| 2 | Compatibility | `BLOCKED_INFRA` | `/sys/kernel/btf/vmlinux` is absent, `/lib/modules/6.12.94+` is absent, kernel config is absent, `bpftool` is absent, and `unprivileged_bpf_disabled` is `2`. P2 names BTF as a covered-node prerequisite. |
| 3 | Artifact verify | `BLOCKED_INFRA` | This credential cannot resolve `vantioai/vantio-phantom-engine`. No local loader binary, image digest, chart, or embedded eBPF object is on the pod. No GHCR credential is set. |
| 4 | Install | `BLOCKED_INFRA` | No verified artifact and no BTF. Open-core has no host loader or enroll command (`EG-SUB-4` is `PLANNED`). Nothing was installed. |
| 5 | Observe | `BLOCKED_INFRA` | Host observe follows install. Install did not happen. The loopback fixture inside the exerciser is the merged script contract, recorded separately, and is not this row. |
| 6 | Ingress | `BLOCKED_INFRA` | No loader, no BTF, no `ip` command, and no attached TC or cgroup program. `bpffs` entry count is `0`. |
| 7 | Egress | `BLOCKED_INFRA` | No `cgroup_skb/egress` attachment. The packaging plan already records that Kubernetes `--enroll-watch` does not auto-attach that program. This pod has no cluster and no loader. |
| 8 | Allowed | `BLOCKED_INFRA` | No enrolled host and no policy attachment. The free-path shape check accepts only action `OBSERVED`. |
| 9 | Denied | `BLOCKED_INFRA` | No drop path is loaded. `bpffs` is empty. A `BLOCKED` run file is a stop in the merged lab, not a denial proof. |
| 10 | App/host correlation | `BLOCKED_INFRA` | PID-offset calibration belongs to the loader. `/run/vantio` is absent. This pod has a distinct pid namespace from the host init path above, and no calibration file was produced. |
| 11 | Proposal | `BLOCKED_INFRA` | Enterprise activation in `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md` is `PLANNED` and unimplemented. No approval record and no on-host proposer exist here. |
| 12 | Simulation | `BLOCKED_INFRA` | No installed engine with a simulation mode. The investor-demo scaffold is a different program and was not run. |
| 13 | Canary | `BLOCKED_INFRA` | No installed version and no second host to receive a canary. |
| 14 | Enforcement | `BLOCKED_INFRA` | BTF is absent, the loader is absent, and `bpffs` is empty. The merged design excludes kernel and eBPF execution. This force did not load a program. |
| 15 | Restart | `BLOCKED_INFRA` | No `vantio` or `phantom` systemd unit exists to restart. |
| 16 | Reboot | `BLOCKED_INFRA` | No dedicated lab host whose reboot is in charter, and no installed service to observe after boot. Reboot was not issued. |
| 17 | Degradation | `BLOCKED_INFRA` | No running enforcer to degrade. OpenSSL and GnuTLS are both present, so the documented dual-library absence case is not the gap on this pod. |
| 18 | Recovery | `BLOCKED_INFRA` | `EG-SP-3` is specified and `UNSATISFIED`. `python/pe_customer_pack.py` is not in this repository. No pre-containment snapshot exists. |
| 19 | Evidence export | `BLOCKED_INFRA` | `EG-SP-5` export needs an installed host product and a customer-held copy. The exerciser retention bundle is deleted on exit by `check-guards.sh`. |
| 20 | Revocation | `BLOCKED_INFRA` | `EG-SP-2` needs a customer root and a grant. No grant exists. Creating `VANTIO_API_KEY` is stop `S7` exit `21`. No credential was created. |
| 21 | Rollback | `BLOCKED_INFRA` | No installed digest and no previous digest. P1 image rollback is unimplemented. |
| 22 | Upgrade | `BLOCKED_INFRA` | No pair of artifact versions. Publish, tags, and releases stay closed. CLI `0.3.24` was not reopened. |
| 23 | Uninstall | `BLOCKED_INFRA` | No install was performed, so there is no product removal to record. |
| 24 | Residual inspection | `BLOCKED_INFRA` | Product residual inspection follows uninstall. Maps, units, and packages from an install were never created. `bpffs` stayed empty. |

Machine-readable copy: `SEQUENCE.json`.
