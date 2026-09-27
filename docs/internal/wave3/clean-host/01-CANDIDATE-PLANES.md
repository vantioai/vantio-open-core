# Candidate planes outside the producer pod

Audience: INTERNAL_RESTRICTED

Inventory clock for the worker list: `2026-09-27T14:39:38Z`

Source commit: `0620f10ee52d3abcea18c1c988df02f687f51b36`

This file records planes named from a worker list, from repository coverage rows, and from a failed cloud-account read. No row was attached.

## 1. `phantom-box`

| Fact | Observed value |
| --- | --- |
| Source | Cursor `list-self-hosted-workers`, scope `all`, status `all` |
| `totalCount` | `1` |
| `hasMore` | false |
| `workerId` | `af6a140a-5253-4d36-ab6b-6911b2eaca32` |
| `displayName` | `phantom-box` |
| `machineDisplayName` | `phantom-box` |
| `machineId` | `59a8d664294e185354d4ea6bb00385d5f8308ad3763dc2d62c8bd2e1bcac6e5a` |
| OS label | `linux` |
| `sharedAssignmentAllowed` | true |
| `isInUse` | false |
| `activeBcId` | null |
| `repos` | empty |
| `connectedAt` | `2026-09-27T03:28:53.618Z` (`connectedAtMs` `1790479733618`) |
| `eligibleForSubagent` | true |
| Distribution, kernel, BTF, modules, console, rollback | not in the worker payload |

`eligibleForSubagent` means a subagent could be placed on that worker. This force placed none. The producer run has `usePrivateWorker` false.

Shared assignment means the worker accepts concurrent agent work. That registration is not a recorded image reset.

The clean-host design in `docs/planning/clean-host-lifecycle/01-ARCHITECTURE.md` describes Phantom-Box as the local dogfood control plane and excludes it. This force did not open port `5001` on the worker and does not claim the worker process is that control plane. The name match is recorded. It is not a proof of kernel state.

Verdict: `INELIGIBLE`. Availability is not clean-host proof.

## 2. Repository evidence rows

| Plane id | Source | This force |
| --- | --- | --- |
| `wsl2-privileged-repository-evidence` | `COVERAGE-MATRIX.json` rows whose `platform_scope` is `WSL2_PRIVILEGED` | `NOT_EXECUTED`. Host not mounted. Private repository name did not resolve. |
| `kind-local-repository-evidence` | `COVERAGE-MATRIX.json` rows whose `platform_scope` is `KIND_LOCAL` | `NOT_EXECUTED`. `kind` absent on the producer pod. |

Verdict for both: `INELIGIBLE`.

## 3. Azure compute

| Attempt | Result |
| --- | --- |
| `subscription_list` | MCP error `-32001` timeout. Repeated once. Same error. |
| `AZURE_SUBSCRIPTION_ID` | unset |
| Azure CLI | absent |
| `compute_vm_get` | `Missing Required options: --subscription` |

No VM name was returned. Verdict: `NOT_INVENTORIED`.

## 4. Managed Kubernetes

P2 records managed GKE, EKS, and AKS as untested documented classes. This force did not authenticate to a cluster. Verdict: `INELIGIBLE`.
