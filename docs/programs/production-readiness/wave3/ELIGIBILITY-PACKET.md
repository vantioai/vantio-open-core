# Eligibility packet — Wave 3 Track 4

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_ELIGIBLE_PLANE_NONE_BLOCKED_INFRA_PACKET_READY`

Plane id: `NONE`

Lifecycle: `BLOCKED_INFRA`

Evidence tier: `UNSET`

Council status: `PENDING_INDEPENDENT_COUNCIL`

Self-certified council pass: false

## 1. Decision

No existing environment this force could name meets the eligibility bar in `CLEAN-HOST-REGISTER.md`.

The selected plane id is `NONE`.

Track 5 may run no attach, load, enroll, observe, or rollback lifecycle from this packet. The lifecycle field stays `BLOCKED_INFRA`.

No baseline plan is preserved. A baseline belongs to an eligible plane, and this inventory has none.

## 2. One infrastructure requirement

Requirement id: `W3-INFRA-REQ-1`

Statement: Provide one Vantio-controlled disposable x86_64 Linux machine that is a different machine from the Cursor coding pod `pod-gc5te7zkozh5neaqpwm4mgnzpe-3239cabe` and a different machine from Cursor worker `af6a140a-5253-4d36-ab6b-6911b2eaca32` (`phantom-box`), that is not a customer host and does not carry production company operations, and that already has all of the following:

- a recorded image digest the machine can be reset to
- console or serial recovery that does not depend on the workload under test
- that same digest as the known rollback target
- an evidence-export path an independent verifier can read
- Linux kernel ≥ 5.8
- `/sys/kernel/btf/vmlinux` present
- `/lib/modules/$(uname -r)` present for that kernel

Machine-readable copy: `BLOCKED-INFRA.json`.

## 3. What provisioning that requirement takes

| Need | Value | This force |
| --- | --- | --- |
| External action | Required. A person who controls a Vantio hypervisor or cloud account has to create or designate the machine. | Not taken. |
| Money | Required when the machine is newly rented or purchased. | None spent. No purchase is authorized. |
| Credentials | Required for console recovery and for the independent verifier. | None issued. |

Until `W3-INFRA-REQ-1` is present and a later inventory marks a plane eligible, lifecycle stays `BLOCKED_INFRA`.

## 4. Observations that do not fill the requirement

- The producer pod runs Ubuntu 24.04.4 on kernel `6.12.94+`, x86_64, with cgroup v2 and an empty bpffs mount. `/sys/kernel/btf/vmlinux` is absent. `/lib/modules/6.12.94+` is absent. `unprivileged_bpf_disabled` is `2`. Root via sudo holds a full capability set, including `cap_bpf`. That pod remains ineligible.
- Worker `phantom-box` was connected and idle, with OS label `linux` and shared assignment allowed. This force did not attach to it. Availability is not clean-host proof.
- Coverage-matrix WSL2 and local `kind` rows stay `OBSERVED_FROM_REPOSITORY_EVIDENCE`. This force did not re-execute them.
- Azure virtual machines were not listed. The subscription id was unresolved. That gap is not an empty-account certificate and is not an eligible plane.
- `vantioai/vantio-phantom-engine` did not resolve with this credential, and no loader bytes were on the pod. Artifact access is a later install input. It is not `W3-INFRA-REQ-1`. This packet does not trade a missing host for a missing repository credential.

## 5. Closed actions

Host attach, eBPF load, enroll, loader mutation, credential issuance, spend, customer deploy, CLI edit, Python publish, and announcement did not occur.

## 6. Handoff

Council questions are in `02-INDEPENDENT-COUNCIL.md`. Each answer cell is `PENDING`.
