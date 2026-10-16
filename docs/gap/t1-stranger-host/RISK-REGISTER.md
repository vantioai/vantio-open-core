# T1 risk register

UTC: 2026-10-16T21:30:00Z

Track label: **Roadmap**

| ID | Risk | What remains |
| --- | --- | --- |
| R1 | No stranger host has been run by this track | The nine-step grade is fixture-tested. A host Vantio does not own has not produced a bundle. Tier stays `UNSET`. |
| R2 | Pinned TEST trust bytes are not in this repo | `sign --claim awaiting` refuses any other hash. An outside-review signature waits on the operator who already holds that TEST key. The local proof uses a fixture key and `host_proof` false. |
| R3 | GCP uninstall recorder lacks the #300 fix | `scripts/gcp/lab-guests/enterprise-rows.sh` can still surface `programs_not_removed` when the independent listing is empty. The grade annotates `harness_fault_candidate` and still requires `VERIFIED_REMOVED` from the listing. Porting #300 is lab work, owned with the lab slot. |
| R4 | Working seal decision, 2026-10-16 | Zachary set the working seal to `6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403`. That digest was the comparison digest, so step 2 now records `working_seal` true and `comparison_seal` true together. The previous working seal was `bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d`. The public pin remains `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`. |
| R5 | Serial binding is the boot id in the console text | The operator writes `VANTIO_BOOT_MARK=<boot_id>` to `/dev/kmsg` before saving the hypervisor serial. The grade requires that boot id, the `lsm=` word, and a matching `serial_sha256`. A log from another boot does not contain this boot id. The grade does not prove the hypervisor retained every earlier byte. |
| R6 | Lockdown `confidentiality` is untested | Preflight stops. Integrity is the mode the GCP lab inferred and did not record as a file. This package records the file and does not claim a confidentiality run. |
| R7 | Lockdown `none` was not a separate GCP lab run | Preflight allows it because it is less restrictive than the integrity lab. The record shows the mode. A pass on `none` is still Roadmap. |
| R8 | Exact image was missing from lab evidence | Preflight now refuses a family-only name. The operator must supply the build they launched, or enable link-local metadata. A wrong attestation is an operator error this package cannot detect against the cloud API, because this track does not call that API. |
| R9 | Guest `descendant_pass` is weaker than this standard | Skipped cases fail here. Deny cases also require net errno 1. A guest JSON with `descendant_pass: true` can still fail step 5 or 7. |
| R10 | Loader words come from separate lab batteries | Step 4 fails closed when `loader_kill`, `loader_restart`, and `deny_attr_post_kill` are absent. The operator copies them from the rows the lab batteries emit. This track does not start those batteries. |
| R11 | `enterprise-rows.sh` mutates a lab-shaped VM | Apt offline mode, swap, and docker changes are in the guest script. Step 9 is the operator's restore or delete. This package does not perform that delete. |
| R12 | Lab workflows can change under the lab agent | `bc-8b310b16` owns the lab slot. This package pins its dependency notes to `69671e97` and does not edit those workflows. A later lab change can move field names. The grade then fails closed until this standard is revised. |
| R13 | TOCTOU on sysfs | The bundle stores the bytes one capture read. A boot id mismatch across steps fails the grade. The package does not lock the kernel. |
| R14 | Public website and README stay as they are | Nothing in this track moves a Roadmap item to Shipped. |
| R15 | `cgroup_skb_survives_container_exit` | The Phantom Engine loader loads `cgroup_skb_egress_enforce`. After the loader container exits, bpftool can still list that program. On open-core `533c0181`, run 38960187559, `vantio-loader --uninstall` then left bpftool and bpffs empty. Whether the program still denies in the window after the container exits and before uninstall is the `r15-container-exit` battery. The harness records fail-open or fail-closed and does not detach the program. Repro: `docs/gap/t1-stranger-host/CGROUP-SKB-CONTAINER-EXIT.md`. |
