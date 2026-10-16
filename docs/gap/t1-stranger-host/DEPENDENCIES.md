# T1 dependencies

UTC: 2026-10-16T15:47:41Z

Base graded against: `69671e97fa359b685232ec7dd4e9fb4badc7be57`.

This track reads the lab harness and does not modify it. Lab agent `bc-8b310b16` owns the lab slot and the `6d3ce580` seal labs. This agent could not read that run's diff (the id was not available). The files below stay untouched so that work can land without a merge conflict from this package.

## Used as specified, not edited

| Path | What this package relies on |
| --- | --- |
| `scripts/gcp/offline_deliver_3.py` | New-boot rule: `confirm_matches_boot`, `_cmdline_bpf`, `_bpf_listed`, `live_lsm_from_probe`, and `_require_serial` (boot id, live cmdline, live LSM list, serial text for that boot). |
| `scripts/aws/w3_lab_steps.py` | Reboot boot-id wait, stale-rows rejection, descendant `post_boot != pre_boot`, and `VERIFIED_REMOVED` as the removal word. The AWS `execute_verify` status of that name is the instance-census check. This track's `VERIFIED_REMOVED` is the host uninstall listing, which is the guest-side bar #300 records. |
| `scripts/aws/lab-guests/enterprise-rows.sh` | #300 uninstall recorder: markers appended so the rows file the runner reads contains `UNINSTALL_VERIFIED`, plus the empty bpffs check. No separate `uninstall` argv on this copy. |
| `scripts/gcp/lab-guests/enterprise-rows.sh` | The `uninstall` argv in the comparison plan. The recorder here is the pre-#300 shape. See R3. |
| `scripts/aws/lab-guests/baseline_diag.py` | `lsm_list_with_bpf`, `lsm_dropin_text`, `read_boot_id`, and the readiness refusal `bpf_lsm_inactive`. |
| `scripts/aws/lab-guests/descendant_b1.py` | Case names, errno fields, and `reboot_observed`. |
| `scripts/gcp/offline_deliver_2.py` | Enterprise fail-reason fields this standard re-checks. |
| `scripts/aws/enterprise_bundle.py` | Public pin, working seal, plumbing-only seal, tracking seal, trust key id, trust sha256. |
| `.github/workflows/gcp-lab-*.yml` and `.github/workflows/w3-lab-*.yml` | Clean-host lab entrypoints. Not invoked. |

## Other tracks and gates

- Stranger-host gate packet under `docs/planning/stranger-host-gate/` remains the execution-refusal packet. This T1 package does not satisfy its founder authorization, and it does not assign `STRANGER_HOST_PROVED`.
- A GCP port of the #300 uninstall recorder is lab work. Joint-test grading should keep using the independent listing until that port lands.
- The TEST private key and the pinned trust bytes stay outside this repo.
- Hiring a pen-test vendor is a founder gate. `PENTEST-SCOPE.md` is the scope to hand across after that gate. Nothing is sent by this track.
- Cloud lab runs stay with `bc-8b310b16`. This track does not spend, does not open a lab, and does not install on a host Vantio does not own.
