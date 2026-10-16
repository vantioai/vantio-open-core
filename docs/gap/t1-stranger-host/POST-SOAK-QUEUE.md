# Post-soak queue

UTC: 2026-10-16T23:05:00Z

Working seal: `6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403` (Zachary, 2026-10-16 5:15 PM ET). The previous working seal was `bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d`.

Public installer pin: `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`. This queue does not change it.

This document is the ledger for the deferred post-soak batteries. The result table stays empty until those batteries run on the merged harness. A host run has not started from this change.

## Fresh-host review

Each battery was read for the files it copies, the units it starts, anything it leaves in `/tmp`, whether it reboots, and whether a later phase can read a stale file.

| Battery | What had to survive | Fix in this change |
| --- | --- | --- |
| `r15-container-exit` | The probe has to run after `docker stop` and `docker rm` of `vantio-lab-loader`, while `/sys/fs/cgroup/vantio-pe-lab` still exists, and before `vantio-loader --uninstall`. | `fail_open` is recorded only when the secret open was errno 13 while the loader was up and errno 0 after the container exited. An open that is already errno 0 while the container is up is `deny_not_engaged`, not `fail_open`. A missing enforce banner stops the battery and keeps the log tail. `lab_pass` stays false. |
| Red-team loader kill | The kill result was written to `/tmp/redteam-rows.json`. Descendant pre schedules a reboot, Noble mounts `/tmp` as tmpfs, and the post phase ran the kill again after the loader was gone. | The script writes `/var/lib/vantio-lab/redteam-rows.json`. The kill runs only on pre. The runner reads that path and does not fall back to `/tmp`. A missing or malformed file on descendant-b1 is `redteam_rows_missing` or `redteam_rows_malformed`. |
| `2c-upgrade-rollback` | The guest had one seal tar. `e0b19d55` is the public pin, and the bundle checker still refuses that digest as the working seal. | The runner downloads `lab-bundle/public-pin.oci.tar` from the same pinned bundle commit and keeps it only when the sha256 is `e0b19d55`. The guest loads that tar and `seal.oci.tar`, then measures enforcement and `vantio-loader --uninstall` on the public pin, the working seal, the public pin again, and the working seal again. `lab_pass` stays false. |
| `2d-crash-recovery` | Same-boot scratch under `/tmp` for the lab listener. The rows file is already `/var/lib/vantio-lab/enterprise-pe-rows.json`. No reboot. | No harness change. A file that opens with errno 0 after the loader is killed stays a product result. |
| `2e-performance` | Same-boot. The 100-open timing was recorded. Revoke-to-deny time was not. | `revoke_convergence_ms`, `revoke_errno`, and `revoke_fail_open` are recorded. The 100-open bound is unchanged. |
| `2f-tamper` | Same-boot scratch. No reboot. | No harness change. Fail-open stays a product result. |
| `2g-distro` | The grade compared the rows seal with the old working seal, so a `6d3ce580` host would fail `seal`. Ubuntu 22.04 and AL2023 were rejected before launch. Debian 12 was already accepted by the harness. A Debian launch on 2026-10-10 was `AccessDenied` for `ec2:RunInstances`. | The grade uses the seal tar hash against `6d3ce580`. Jammy (Canonical, `ubuntu-jammy-22.04-amd64-server`) and AL2023 (owner `137112412989`, `al2023-ami-2023…x86_64`) are accepted by the allowlist. SSH uses `ubuntu`, `admin`, or `ec2-user` from the image. IAM is not changed. A denied launch stays a named residual. |
| `2b-simulate` | Open-core has no host battery for simulate parity. | This queue does not invent a host pass. The row below stays fixture-only. |
| 36-hour soak | Holds `vantio-lab-slot`. `disable_api_termination` is already false, and the launch adds `--disable-api-termination` only when that flag is true. | No launch from this change. The soak stays last. Termination protection stays off. |

`lsm-guard` still uses unit `vantio-lab-lsm-reboot` with `systemd-run --on-active=45s`. The runner does not wait inside that arm. A second lsm-guard arm has to start after the reboot. That battery is not in this queue.

Phase rows stay on `/var/lib/vantio-lab/enterprise-pe-rows.json`. The runner reads that path. A missing or malformed enterprise record is `rows_missing` or `rows_malformed`.

## Results

| # | Battery | Result | Evidence |
| --- | --- | --- | --- |
| 1 | `r15-container-exit` | NOT a pass. Classification `fail_open` was stored because both the while-up open and the after-exit open were errno 0. After `docker stop` and `docker rm`, `cgroup_skb_egress_enforce` was not listed. That was not a deny that opened on exit. `detached_by_lab` is false. Uninstall printed `UNINSTALL_VERIFIED`. `lab_pass` is false. | Run `38971792328` on `i-0e2d9a8c2e009e9f5`, main `64d9ac78`, seal `6d3ce580`. https://github.com/vantioai/vantio-open-core/actions/runs/38971792328 Boot `99318de7-bdd6-484f-b9cb-ad1eddf2a855`. Image `ubuntu-noble-24.04-amd64-server-20260923`. |
| 2 | Red-team loader kill | not a kill result. On the same boot, after that uninstall, the enforce loader did not print `SCOPED (drop enrolled)` or the open/openat pin lines within 120s. Audit did print. Run `38972783768` exited on the missing banner. `pe.tamper.loader_kill` was `loader_pid_absent` because the kill ran after that failure. | https://github.com/vantioai/vantio-open-core/actions/runs/38972783768 |
| 3 | `2c-upgrade-rollback` | not run | |
| 4 | `2d-crash-recovery` | not run | |
| 5 | `2e-performance` | not run | |
| 6 | `2f-tamper` | not run | |
| 7 | `2g-distro` Debian 12, Ubuntu 22.04, AL2023 | not run | |
| 8 | `2b-simulate` | no host battery in open-core | |
| 9 | 36-hour soak on `6d3ce580` | not run | |

## Residuals named before any launch

- `2c` is on main as `d8b37f60`. It stages both tars. That battery has not been run. It runs after the enforce re-proof, and before the soak.
- `2b` has no host battery here.
- `2g` may still fail `RunInstances` for a non-Noble AMI. That is the earlier Debian denial. This change does not edit IAM.
- The soak launches only after batteries 1–8, with termination protection off.
- GCP can run a battery in parallel only after this harness is what `main` runs, and only where that battery fits the GCP guest.
