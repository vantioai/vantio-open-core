# Clean-host register — Wave 3 Track 4

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_ELIGIBLE_PLANE_NONE_BLOCKED_INFRA_PACKET_READY`

Selected plane: `NONE`

Lifecycle: `BLOCKED_INFRA`

Evidence tier: `UNSET`

Inventory clock: pod probe `2026-09-27T14:34:19Z`; worker list reconfirmed `2026-09-27T14:39:38Z`.

A row is eligible only when every requirement below is met on evidence this force collected. An unknown cell is not a pass. Phantom-Box availability is not a pass.

## 1. Eligibility bar

| Id | Requirement |
| --- | --- |
| E1 | Resettable to a recorded image |
| E2 | Disposable or recoverable |
| E3 | Not a customer host |
| E4 | Not carrying production company operations |
| E5 | Supported Linux distribution |
| E6 | Supported architecture |
| E7 | Compatible kernel (P2 floor: Linux ≥ 5.8) |
| E8 | BTF at `/sys/kernel/btf/vmlinux`, or the kernel capability P2 names in its place |
| E9 | Required modules available for the running kernel |
| E10 | Console or recovery access |
| E11 | Known rollback |
| E12 | Evidence export |
| E13 | Independent verifier access |

P2 is `docs/planning/phantom-engine-production/03-P2-PREREQUISITE-COMPATIBILITY.md`. A host that fails one P2 floor check is `REQUIRED_DEPENDENCY_MISSING` and is not a covered node. This register uses that floor for E7 and E8. P2 does not name a narrower distribution or architecture. This force treats x86_64 as the architecture of the live probe and of the repository's WSL2 evidence class. It does not add an arm64 support claim.

## 2. Planes

| Plane id | What was observed | Verdict |
| --- | --- | --- |
| `cursor-coding-pod` | This producer pod. Detail in `docs/internal/wave3/clean-host/00-POD-PROBE.md`. | `INELIGIBLE` |
| `phantom-box` | One connected Cursor self-hosted worker whose display name is `phantom-box`. Detail in `docs/internal/wave3/clean-host/01-CANDIDATE-PLANES.md`. | `INELIGIBLE` |
| `wsl2-privileged-repository-evidence` | Coverage-matrix rows with `platform_scope` `WSL2_PRIVILEGED` and `this_force` `NOT_EXECUTED`. No path to that host from this pod. | `INELIGIBLE` |
| `kind-local-repository-evidence` | Coverage-matrix rows with `platform_scope` `KIND_LOCAL`. `kind` is absent on this pod. | `INELIGIBLE` |
| `azure-compute` | Subscription list timed out. No subscription id was available. No VM identity was returned. | `NOT_INVENTORIED` |
| `managed-gke-eks-aks` | P2 leaves managed cloud as `DOCUMENTED_REQUIREMENT` / `TARGET_DESIGN`. No cluster client on this pod. | `INELIGIBLE` |

Eligible count: `0`.

Selected plane id: `NONE`.

## 3. Why each named plane fails

### `cursor-coding-pod`

Instance cgroup: `0::/system.slice/pod-gc5te7zkozh5neaqpwm4mgnzpe-3239cabe/init`.

| Check | Result |
| --- | --- |
| E1 Resettable | Fail. No recorded image digest and no reset control for host-attachment state. |
| E2 Disposable or recoverable | Fail. The pod is the producer environment. Boot snapshot `bld-20260927-f7f18e2d-1e93-4ae1-a8e5-adce44c693d5` is the environment build this pod started from. It is not a rollback for an attachment experiment. |
| E3 Customer host | Pass. The pod is a Vantio Cursor cloud agent environment. |
| E4 Production company operations | Pass as observed. No listener on port `5001`. `VANTIO_SOAK_LOCAL` unset. No `.vantio` state directory. |
| E5 Distribution | Observed Ubuntu 24.04.4 LTS. P2 does not list a distribution allow-list. This cell stays `OBSERVED`, not a support certificate. |
| E6 Architecture | Observed `x86_64`. |
| E7 Kernel | Pass on the version floor. `uname -r` is `6.12.94+`. |
| E8 BTF | Fail. `/sys/kernel/btf/vmlinux` is absent for root. |
| E9 Modules | Fail. `/lib/modules/6.12.94+` is absent. Kernel config is absent. |
| E10 Console or recovery | Fail. `sudo -n true` exits 0 inside the pod. No serial or out-of-band recovery path was present. |
| E11 Known rollback | Fail. |
| E12 Evidence export | Fail for host-attachment evidence. This packet is the inventory export. |
| E13 Independent verifier | Fail. `independent_verifier` stays `UNSET`. |

The coding pod has a kernel new enough for the P2 version floor and a root capability set that includes `cap_bpf`. Those facts do not supply BTF, a module tree, or a reset. A Cursor coding pod without those controls is not an eligible plane.

### `phantom-box`

Cursor worker id `af6a140a-5253-4d36-ab6b-6911b2eaca32`. Label `cursor.private_worker.os` = `linux`. `sharedAssignmentAllowed` true. `isInUse` false at `2026-09-27T14:39:38Z`. Connected since `2026-09-27T03:28:53.618Z`.

The worker list API returns no distribution, kernel, architecture, BTF, module, console, or rollback fields. `eligibleForSubagent` true means a later agent could be scheduled onto that worker. This force did not schedule one. That flag is not host-attachment eligibility.

E1 through E13 are `UNVERIFIED` on this worker. Unverified is not a pass. The worker stays connected for shared assignment, so it is not an idle disposable image this force can reset.

Repository text uses Phantom-Box for the local dogfood control plane and excludes it from clean-host proof. This inventory does not claim the connected worker is the port `5001` process. The display name and the exclusion rule are enough to refuse a pass. Availability of the worker is not clean-host proof.

### `wsl2-privileged-repository-evidence`

`docs/planning/phantom-engine-production/COVERAGE-MATRIX.json` records verifier, TC, and uprobe rows with `platform_scope` `WSL2_PRIVILEGED` and `evidence_class` `OBSERVED_FROM_REPOSITORY_EVIDENCE`. `this_force` on those rows is `NOT_EXECUTED`. This force did not re-execute them. No checkout of `vantioai/vantio-phantom-engine` is mounted. `gh repo view vantioai/vantio-phantom-engine` returned `Could not resolve to a Repository`. Paths `/home/zach_vantio/vantio-phantom-engine` and `/mnt/c/Users/zach_vantio/vantio-phantom-engine` are absent.

Those rows do not identify a current machine with a snapshot digest, a console path, or verifier access. Historical repository evidence is not an eligible plane.

### `kind-local-repository-evidence`

`kind`, `docker`, `kubectl`, and `helm` are absent on this pod. `/var/run/docker.sock` is absent. A local `kind` cluster in the coverage matrix shares the host kernel of whatever machine ran it. It is not a separate resettable plane here.

### `azure-compute`

`subscription_list` returned MCP error `-32001` (timeout) on two attempts. `AZURE_SUBSCRIPTION_ID` is unset. The Azure CLI is absent. `compute_vm_get` stopped with `Missing Required options: --subscription`. No virtual machine name, power state, image, or resource group was returned.

This cell is `NOT_INVENTORIED`. It is not a claim that the account contains zero virtual machines. A machine this force cannot name is not an eligible plane.

### `managed-gke-eks-aks`

P2 records GKE, EKS, and AKS as documented vendor classes Vantio has not tested as real clusters. No cluster credential and no cluster client were used. No managed node is an eligible plane in this inventory.

## 4. Register result

| Field | Value |
| --- | --- |
| Eligible plane id | `NONE` |
| Lifecycle | `BLOCKED_INFRA` |
| Baseline preserved | No. No eligible identity exists to snapshot. |
| Track 5 host-attachment lifecycle | None. State stays `BLOCKED_INFRA`. |
| Requirement | `W3-INFRA-REQ-1` in `BLOCKED-INFRA.json` |
