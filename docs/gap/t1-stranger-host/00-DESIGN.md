# T1 design and boundary check

UTC: 2026-10-16T15:47:41Z

Base: `69671e97fa359b685232ec7dd4e9fb4badc7be57` (main, "Record the AWS reboot boot id and the uninstall result", #300).

Track label: **Roadmap**. This document is the phase-1 boundary check. It is not a host proof.

Audience: internal. The package prepares an outside operator to run installer, enforcement, reboot, teardown, and evidence collection on a clean Linux host Vantio does not own. This track does not run that host.

## Question

What has to be true, file by file, before a later outside run can be graded as a stranger-host attempt, and which failures stop the run before install?

## Threat model

The operator is outside Vantio. The host is a dedicated test VM in a project Vantio does not control. The sealed engine under test can enforce on enrolled workloads. The proof package can be lied to.

The failures this package is built to reject:

- A preflight that continues when the BPF LSM is off, BTF is missing, cgroup v2 is missing, or lockdown is `confidentiality`.
- A post-reboot pass that reuses the previous boot's rows file. Both lab runners already reject that: GCP `confirm_matches_boot` in `scripts/gcp/offline_deliver_3.py`, and AWS `_rows_disagree_with_boot` plus the descendant `post_boot != pre_boot` check in `scripts/aws/w3_lab_steps.py`.
- An uninstall pass that trusts a guest flag while pins or programs remain. The independent bar is `UNINSTALL_VERIFIED` plus an empty `bpftool` vantio listing plus no `vantio*` names on bpffs. That is the `VERIFIED_REMOVED` bar for this track.
- A bundle signed by any key other than the TEST key `test-nonprod-ed25519-2026-10-02`, including a production root or the public installer pin.
- A claim of `STRANGER_HOST_PROVED`, a customer validation, or a shipped product inside this package.
- Private-key material or provider tokens copied into the evidence tree.

Out of scope for the threat model, and for the code: prompt or answer scoring, content moderation, model evaluation, an identity provider, generic AV/WAF/DDoS, and robotic physical safety. Phantom Engine covers supported AI workloads on enrolled Linux machines only.

## What this track adds

A package beside the lab harness, under:

- `docs/gap/t1-stranger-host/` for the standard, the pen-test scope, the bundle format, the risk register, and the dependencies
- `scripts/gap/t1-stranger-host/` for operator commands
- `tests/gap/t1-stranger-host/` for the fixture proof
- `evidence/gap/t1-stranger-host/` for the local package-proof artifact

The operator commands are `preflight`, `capture-boot`, `capture-uninstall`, `assemble`, `grade`, `sign`, and `verify`. They run on the stranger host or on the operator workstation. They do not call AWS or GCP. They do not import `scripts/gcp` or `scripts/aws`.

`preflight` stops on the first failure, in this order: BPF LSM inactive, BTF missing, cgroup v2 missing, lockdown unreadable, lockdown `confidentiality`, bpffs missing, exact image missing, then a boot id that is not one line of 1 to 80 characters. A pass writes a host record that contains the lockdown mode, the exact image, and that boot id, plus the live cmdline and the live LSM list.

`capture-boot` records the new-boot rule used by the lab: boot id, live `/proc/cmdline`, live `/sys/kernel/security/lsm`, and a serial log bound to that boot id. The serial file is supplied by the operator from the hypervisor console. This package does not call `gcloud compute instances get-serial-port-output`.

`capture-uninstall` records the uninstall transcript, the `bpftool prog show` text, and the bpffs names. `grade` emits `VERIFIED_REMOVED` only when the transcript has a line that is exactly `UNINSTALL_VERIFIED`, the bpftool text has no vantio program, and the pin list has no `vantio*` name.

`sign` and `verify` use one Ed25519 trust document. A bundle that claims it is ready for outside review verifies only when that document's sha256 is `2e4a1da7bf44f0bddfc2a3ce3eda007fa6cc1455332f26769bd346fafc297876`, the single key id is `test-nonprod-ed25519-2026-10-02`, `environment` is `NON-PRODUCTION`, `label` is `TEST`, and `not_a_production_root` is true. Fixture signatures used by the local proof carry `FIXTURE_NOT_A_HOST_PROOF` and are rejected as a host proof.

Pass criteria for the nine operator steps are in `STRANGER_HOST_STANDARD.md`. The bundle layout is in `EVIDENCE-BUNDLE.md`. The outside-tester scope is in `PENTEST-SCOPE.md`.

## What this track leaves alone

Lab agent `bc-8b310b16` owns the lab slot and the `6d3ce580` seal labs. `6d3ce580` is not the working seal. The working seal remains `bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d`. The public pin remains `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`.

This track does not edit:

- `.github/workflows/gcp-lab-*.yml`
- `.github/workflows/w3-lab-*.yml`
- `scripts/gcp/**`
- `scripts/aws/**`
- `scripts/lab/**`
- `docs/planning/stranger-host-gate/**` (that packet refuses execution and hashes its own files)
- `README.md` and any public site copy

The existing guest script stays the battery. The operator runs the handover copy of `enterprise-rows.sh`. This package grades the files that command writes. It does not vendor a second copy.

## Failure mode

Fail closed. A missing control, an unreadable lockdown file, an empty serial log, a stale boot id, a digest mismatch, or a non-TEST signature stops the grade. The reason is that a stranger-host bundle which continued would let an unsupported host, or a reused pre-reboot file, look complete. The loader already refuses enforce when the BPF LSM is inactive (`INSTALL_ENFORCEMENT_READINESS_BLOCKED`, `reason=bpf_lsm_inactive` in `scripts/aws/lab-guests/baseline_diag.py`). Preflight matches that refusal before any install command is printed as next.

`programs_not_removed` on an otherwise empty independent listing is recorded as `harness_fault_candidate`. It does not by itself satisfy `VERIFIED_REMOVED`, and it does not by itself fail step 3 when every enforcement field holds. The GCP guest recorder at this base still writes `/tmp/vantio-uninstall.out` in the way #300 fixed on AWS only. That port is a lab-harness dependency, not a change in this track.

## Edge cases

- `bpf` must be its own comma token in `/sys/kernel/security/lsm` and its own `lsm=` word on the post-reboot cmdline. A longer token that merely contains the letters does not count. This matches `_bpf_listed` and `_cmdline_bpf` in `scripts/gcp/offline_deliver_3.py`.
- Lockdown text must be the three modes `none`, `integrity`, and `confidentiality` with exactly one of them in brackets. `none` and `integrity` continue. `confidentiality` stops. Any other shape stops as unreadable. Integrity is the mode the GCP lab run inferred; this package records the file instead of inferring it.
- The image family `ubuntu-os-cloud/ubuntu-2404-lts-amd64` is not an exact image. An exact image is an AMI id, a dated GCP image name such as `ubuntu-2404-noble-amd64-v20261009`, or an operator attestation that names a specific build and is not that family. `PRETTY_NAME` from os-release is supplemental.
- Metadata reads are off unless the operator passes `--allow-metadata`. The local proof never contacts link-local metadata.
- A descendant case marked skipped, including `probe_missing`, fails the stranger standard even though `descendant_b1.py` currently scores that skip as pass. `descendant_pass: true` is not sufficient.
- Deny cases in the comparison plan require file errno 13 and net errno 1. Allow cases (`ancestor_9`, `unenrolled`) require file errno 0. Net errno on an allow case is recorded and is not a fail, because `score()` in `descendant_b1.py` documents that egress can still drop past the file walk.
- Serial text must contain the post-reboot `lsm=` word and the new boot id. The operator writes that boot id to `/dev/kmsg` before saving the hypervisor serial. A log from another boot fails. `serial_sha256` is required and must match the text.
- Boot ids are a single line of 1 to 80 characters, matching the AWS runner's bound. The post-reboot id must differ from preflight.

## Memory, verifier, privileges

This package loads no eBPF program and does not change verifier limits, map sizes, or instruction limits. Those stay inside the sealed image the operator was handed.

Evidence files are refused above 2_000_000 bytes before they are parsed. The grader reads each accepted file once. That cap is the bound on the memory this package will spend on one evidence tree.

Preflight and capture read sysfs and proc. They do not change bootloader files, apt sources, docker, or swap. The handover `enterprise-rows.sh` does change apt, swap, and docker on a lab VM; the standard tells the operator to use a dedicated test VM and to restore or delete it in step 9. This package's teardown command only records an attestation. `vantio_ran_teardown` must be false.

The signer reads a private-key path outside the bundle and does not copy it. Any PEM private-key header inside the bundle fails assemble and verify. The uninstall token is not read or printed.

There is a TOCTOU window between a live read and a later kernel change. The grade uses the bytes captured into the bundle, not a second live read. A later step whose boot id disagrees with the capture fails closed.

## Permissions

The host record is Observe. The guest script the operator already runs is Enforce. This package adds no Control path. Nothing in the evidence schema grants a permission because a model produced it. No proxy hop is required. The bundle schema rejects `prompt`, `messages`, and `completion` fields so conversation content is not kept.

## Rollback

This package installs nothing. If an operator has already run the guest script, rollback is the guest `uninstall` mode and then step 9 (delete the VM in the operator's own project, or restore apt sources, remove `/etc/apt/apt.conf.d/99vantio-offline`, and remove the swapfile). A failed uninstall stays `NOT_REMOVED`. This package does not call a cloud delete API.

## Claims

Every local result of this package is Roadmap for the stranger-host question. The fixture proof can show that the grader, the preflight stops, and the TEST-key refusal behave as specified. That fixture proof is not `STRANGER_HOST_PROVED`, not `INTERNAL_CLEAN_HOST_PROOF`, and not a customer release. The public pin is not moved. No price appears in any artifact.

## Tests and proof

`tests/gap/t1-stranger-host/test_stranger_host.py` drives fixture files. `scripts/gap/t1-stranger-host/proof.py` runs those tests and writes `evidence/gap/t1-stranger-host/local-package-proof.json`. The proof does not start a workflow and does not open a cloud API.

Phase 3 requires a reviewer from a different model family on the final head. The phase-1 council verdict does not satisfy that requirement.
