# Post-soak queue

UTC: 2026-10-16T21:30:00Z

Working seal: `6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403` (Zachary, 2026-10-16 5:15 PM ET). The previous working seal was `bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d`.

Public installer pin: `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e`. This queue does not change it.

This document is the ledger for the deferred post-soak batteries. The result table stays empty until those batteries run on the merged harness. A host run has not started from this change.

## Fresh-host review

Each battery was read for the files it copies, the units it starts, anything it leaves in `/tmp`, whether it reboots, and whether a later phase can read a stale file.

| Battery | What had to survive | Fix in this change |
| --- | --- | --- |
| `r15-container-exit` | The probe has to run after `docker stop` and `docker rm` of `vantio-lab-loader`, while `/sys/fs/cgroup/vantio-pe-lab` still exists, and before `vantio-loader --uninstall`. | New phase. It records `fail_open`, `fail_closed`, `mixed`, or `unmeasured`. It does not detach the program. `lab_pass` stays false. |
| Red-team loader kill | The kill result was written to `/tmp/redteam-rows.json`. Descendant pre schedules a reboot, Noble mounts `/tmp` as tmpfs, and the post phase ran the kill again after the loader was gone. | The script writes `/var/lib/vantio-lab/redteam-rows.json`. The kill runs only on pre. The runner reads that path and does not fall back to `/tmp`. A missing or malformed file on descendant-b1 is `redteam_rows_missing` or `redteam_rows_malformed`. |
| `2c-upgrade-rollback` | The guest has one seal tar. `e0b19d55` is the public pin, and the bundle refuses it as a seal. Reloading the same tar is not an upgrade to `6d3ce580` and back. | The battery records `rollback_image_absent` with `from_pin` and `to_seal`. `host_rollback` stays `NOT_RUN`. It does not `docker load` the same tar and call that an upgrade. |
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
| 1 | `r15-container-exit` | not run | |
| 2 | Red-team loader kill | not run | |
| 3 | `2c-upgrade-rollback` | not run | |
| 4 | `2d-crash-recovery` | not run | |
| 5 | `2e-performance` | not run | |
| 6 | `2f-tamper` | not run | |
| 7 | `2g-distro` Debian 12, Ubuntu 22.04, AL2023 | not run | |
| 8 | `2b-simulate` | no host battery in open-core | |
| 9 | 36-hour soak on `6d3ce580` | not run | |

## Residuals named before any launch

- `2c` cannot perform the public-pin upgrade and rollback until a second image is copied to the guest as `VANTIO_ROLLBACK_OCI`. The public pin is not that image.
- `2b` has no host battery here.
- `2g` may still fail `RunInstances` for a non-Noble AMI. That is the earlier Debian denial. This change does not edit IAM.
- The soak launches only after batteries 1–8, with termination protection off.
- GCP can run a battery in parallel only after this harness is what `main` runs, and only where that battery fits the GCP guest.
