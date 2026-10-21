# P2 — prerequisite and compatibility

Audience: INTERNAL_RESTRICTED

Producer classification: `PHANTOM_WAVE1_PACKAGING_HEALTH_PLAN_READY_FOR_COUNCIL`

Status: `PLAN_ONLY`. No host was probed. `scripts/cloud_platform_readiness.py` in `vantio-enterprise` was read and not run.

## 1. Prerequisite set named by the deploy manifests

The raw DaemonSet header and `docs/product-spec.md` name the same floor. A host that fails one of these is `REQUIRED_DEPENDENCY_MISSING` in the verifier vocabulary (`05-SHARED-HEALTH-VOCABULARY.md`). It is not a covered node.

| Check | Source | Planning status |
| --- | --- | --- |
| Linux kernel ≥ 5.8 | Product spec; raw DaemonSet header; enterprise readiness script `MIN_KERNEL = (5, 8)` | `DOCUMENTED_REQUIREMENT` |
| BTF at `/sys/kernel/btf/vmlinux` | Raw DaemonSet header; readiness script | `DOCUMENTED_REQUIREMENT` |
| cgroup v2 unified hierarchy | Raw DaemonSet header; architecture enrollment section | `DOCUMENTED_REQUIREMENT` |
| bpffs at `/sys/fs/bpf` | Raw DaemonSet volume `type: Directory`; product spec notes `kind` does not mount it by default | `DOCUMENTED_REQUIREMENT`. A missing mount is a prerequisite failure, not a verifier rejection of the program bytes |
| Capabilities `BPF`, `NET_ADMIN`, `SYS_ADMIN`; `privileged: false` | Helm template and raw manifest | Specified. The architecture matrix still lists “minimal caps sufficient” as requiring the hardened deploy path. That row stays `NOT_EXECUTED` for this force |
| `hostPID: true` and `hostNetwork: true` | Both manifests | Specified. PID calibration and TC attach depend on them. This plan does not add a second mode |
| `curl` in the runtime image | Dockerfile runtime stage | Specified so PID-offset calibration can spawn a TLS client. The loader’s own HTTP client is rustls and does not hit the OpenSSL or GnuTLS uprobes. That split is in `architecture_state.md` |
| `libssl.so.3` or `libgnutls.so.30` | Architecture uprobe section: path resolved at runtime; each probe is non-fatal | TLS observe degrades when both are absent. Fork, syscall, and TC paths are a separate coverage row |
| Node interface | Helm default `eth0`. Cloud checklist names `ens5` for EKS Nitro | `DOCUMENTED_REQUIREMENT` per platform. Not bake-off verified |
| `readOnlyRootFilesystem: true` with writable `emptyDir` at `/run/vantio` | Both manifests | Heartbeat and PID-offset files must use `VANTIO_HEARTBEAT_PATH` and `VANTIO_PID_OFFSET_PATH`. The architecture file says the `/run/vantio/pid_offset` override is not yet re-verified live |

Control-plane scheduling stays off unless `scheduleOnControlPlane` is set. The chart comment and the raw manifest both say that opt-in must not be combined with enforcement. Helm defaults `enforce: false` and `nodeWideEnforcement: false`.

## 2. Deployment profile

`python/pe_protection_state.py` and `docs/internal/VERIFIER_CONTRACT.md` define:

| `VANTIO_DEPLOYMENT_PROFILE` | Gate absent |
| --- | --- |
| `bundled_gate` or unset | `control_plane_unreachable`, protection state `degraded` when enroll and enforce are otherwise latched |
| `no_gate` | `OPTIONAL_COMPONENT_ABSENT`. That value is not `PASS` and does not upgrade the overall result |
| `unknown` | Same coupling as `bundled_gate` |

Finding F-07 records that this profile is not yet documented in the operations guide. P2 keeps the code as the machine contract and the guide as a documentation gap.

## 3. Platform scope

The enterprise readiness script’s own honesty block defines three labels. This plan adopts them for P2 and does not add a fourth “verified on cloud” label.

| Label | Meaning in that script |
| --- | --- |
| `VERIFIED_ON_REFERENCE_HOST` | Live check on the machine running the script. The script names that machine as Vantio’s own reference host |
| `DOCUMENTED_REQUIREMENT` | Public vendor requirement class for EKS, GKE, or AKS. The script states Vantio has not tested that real cluster |
| `UNVERIFIED` | No access, or no single baseline. The script uses this for generic on-prem |

`docs/enterprise/CLOUD_VALIDATION_CHECKLIST.md` leaves GKE, EKS, and AKS boxes open and leaves live Spanner as `TARGET`. Its sign-off section says marketing may move past “live-verified on kind / privileged Linux” only after the managed-node functional rows, and optionally Spanner, are checked for that cloud. This force did not check them.

Local `kind` rows in the architecture matrix stay `TESTED_LOCAL` when the matrix says so, with evidence class `OBSERVED_FROM_REPOSITORY_EVIDENCE`. They do not fill the managed-cloud columns.

## 4. Compatibility gaps already named in source

| Gap | Where it is named | P2 disposition |
| --- | --- | --- |
| Kubernetes `--enroll-watch` does not auto-attach `cgroup_skb/egress` | Architecture roadmap | Non-`hostNetwork` forwarded pod egress remains a residual under TC alone. Docker `--enroll-docker-watch` plus `--cgroup-skb-enforce` is a different path and is not a K8s proof |
| Cross-pod TLS when the pod base image differs from the loader image | Architecture matrix | `TARGET_DESIGN` |
| IPv6 CIDR allowlist live test | Architecture matrix | Implemented in source; live dual-stack test not recorded |
| VLAN/QinQ on real tagged frames | Architecture matrix | Parser exists; live tags not recorded |
| Forwarded traffic with cgroup id 0 | Architecture enforcement section | Designed to pass. The caveat is not recorded as exercised |
| Minimal caps on a live hardened pod | Architecture matrix | Open runtime row |
| `VANTIO_DEPLOYMENT_PROFILE` in the customer-shipped guide | Remediation F-07 | Documentation gap |
| Enterprise-tree compatibility matrix files | Section 4 of `01-PRIVATE-PE-ACCESS-AND-COMMIT-CONSTRAINTS.md` | Missing from the listed `docs/ops/` tree |
| Signal Share | Helm `telemetry.signalShare.enabled: false`. Register F-12: `PHASE1_TRANSMIT_LOCKED` in `signal_share/encoder.py`, `may_transmit()` false while that lock holds | Default off. F-12 says the lock is phase 1 and is not claimed permanent |
| Windows and macOS Control | Protection-state module’s default not-covered list | Out of scope for this engine |

## 5. What a later compatibility run must emit

Each row emits one shared health fact (`05-SHARED-HEALTH-VOCABULARY.md`) with `subject` `HOST_PREREQUISITE` and a `platform_scope`. A reference-host pass sets `platform_scope` to `REFERENCE_HOST`. It leaves `MANAGED_CLOUD` and `STRANGER_HOST` as `UNVERIFIED`.

This force emits no live row. `COVERAGE-MATRIX.json` records the repository claims and marks `this_force` as `NOT_EXECUTED`.
