# Enforcement proof operator sheet

Hold. Zach merges this workflow to `main`, then Zach clicks `workflow_dispatch`. Leo does not dispatch, SSH, reboot, or attach. This sheet is the open-core side of Phantom Engine `docs/OPERATOR_PACKET.md` at packet head `c8b767cd`. It is not a lab result.

`live_enforcement` stays **NOT_PROVEN**. The guest script's last line is `live_enforcement=NOT_PROVEN`. This workflow does not print `PROVEN`.

`t2112u` is Zach's name for customer-install plus thoroughness. It is not a dispatch input. The `full` slice is that profile.

## Workflow

| | |
| --- | --- |
| File | `.github/workflows/gcp-lab-enforcement-proof.yml` |
| Name | GCP lab enforcement proof |
| Repo | `vantioai/vantio-open-core` |
| Ref it accepts | `refs/heads/main` |
| Project | `vantio-lab-oct08` |
| Zone | `us-central1-a` |
| Guest | Ubuntu 24.04, image family `ubuntu-2404-lts-amd64`, machine `e2-micro`, no public IP, no guest service account, OS Login, IAP |
| Git tip | `864289cb2c9c4135d74233c74c6655087de3f20d` |
| Lab directory | `/var/lib/vantio-enforcement-proof` |

`gcp-lab-provision.yml` is the wrong path. Its `seal` input is 64 hex. This tip is 40 hex and is not a seal. Do not type the tip into that workflow.

## Dispatch inputs

Zach clicks **GCP lab enforcement proof** on `main`.

| Input | What to enter |
| --- | --- |
| `pe_git_sha` | `864289cb2c9c4135d74233c74c6655087de3f20d`. Any other value fails before a VM. |
| `run_go` | Zach's own-words run go. The log masks it and does not print it. |
| `host_name` | The guest `hostname -s` Zach allows, 3 to 40 lowercase letters, digits, and hyphens. The workflow sets `VANTIO_LAB_HOST` and `VANTIO_LAB_HOST_ALLOWLIST` to that one name. It is masked. |
| `proof_slice` | `full` (default), `reboot-pre`, or `reboot-post`. |
| `instance_name` | Empty, except `reboot-post`. Then paste the `vantio-gcp-lab-` name from the earlier run. |
| `stop_after_minutes` | `120` for `full`. Allowed range is 90 through 120. |
| `uninstall_approval` | Empty unless Zach is supplying `VANTIO_LAB_UNINSTALL_APPROVAL`. Empty is not printed. The script then records `uninstall=NOT_RUN_NO_APPROVAL` when the host is enrolled, or `uninstall=REFUSED_NOT_ENROLLED` when it is not. |

The runner reaches the guest with the existing IAP helper: `gcloud compute ssh`, `--tunnel-through-iap`, `--project=vantio-lab-oct08`, `--zone=us-central1-a`, OS Login key expiry one hour. There is no laptop login in this workflow. The IAP command is `sudo bash /var/lib/vantio-lab/guest/run-proof-phase.sh PHASE`. The run go stays in a mode `0600` file on the guest, not in that command.

## Cost gate

The `gate` job calls `.github/workflows/gcp-lab-cost-gate.yml`. The proof job starts only when that job's output `expected_oop_usd` is `0`. A gate that exits 2 skips create. There is no VM to use. A green gate does not itself install Phantom Engine.

The proof job runs `scripts/gcp/lab_auto.py cost-gate` again and reads that JSON before create.

## What `full` runs

Build happens on the runner, inside an `ubuntu:24.04` container, from the pinned commit: `cargo build -p vantio-loader --release`. The e2-micro guest does not compile. The packet does not raise the machine cap. The binary is copied over IAP. Its sha256 is recorded in the proof JSON. The packet's build-host object `a7cd5f19e83a715aac37dd7b8e2b00538b11f911e98c194854d0273bbbfc5cf6` is that other machine's hash, not a seal this workflow requires. `bpf-linker` is installed the same unpinned way as the Phantom Engine Dockerfile at this tip, so two builds can differ.

Guest order for `full`:

1. `compare`
2. `file-deny`
3. `reboot-pre`
4. Reboot. The workflow masks `google-shutdown-scripts.service`, then schedules `systemctl reboot --force`. A plain `reboot` on this network does not have to reach a new boot. The script does not reboot itself.
5. `reboot-post` on the new boot. The script writes `reboot_restored=NOT_RUN` and does not start the loader. This workflow does not start it either.
6. `compare` again. `expired-key` and `uninstall` call `require_compare_pass`, which needs the compare marker's boot id to be the current boot. The packet lists those phases after `reboot-post`. On tip `864289cb` that call exits 2 with `phase_order=compare_required` until compare has passed on the new boot. The first boot's lab directory is copied to `/var/lib/vantio-enforcement-proof-pre-reboot` before this second compare.
7. `expired-key`
8. `uninstall` (that phase runs `uninstall-negative` itself when the host is enrolled)

Stop on the first phase that is not an accepted observation. `compare=REFUSED_LSM` stops the run. A stock Ubuntu 24.04 image can omit `bpf` from `/sys/kernel/security/lsm`. This workflow does not edit the kernel command line.

`reboot-pre` is the first dispatch when one job should not span the reboot. It runs compare, file-deny, reboot-pre, and the forced reboot, then leaves the VM up. `reboot-post` is the second dispatch on that same instance name. It runs reboot-post, compare, expired-key, and uninstall. Dispatch it before `stop_after_minutes` halts the guest.

## Close-out

A green proof job does not delete the VM. Zach records `instance_name` from the proof JSON (`vantio-gcp-lab-` plus the run id, unless the slice is `reboot-post`). Then:

1. **GCP lab teardown**. Input `instance_name` with that name. File `.github/workflows/gcp-lab-teardown.yml`.
2. **GCP lab verify removed**. Same `instance_name`. File `.github/workflows/gcp-lab-verify-removed.yml`. Pass line is `VERIFIED_REMOVED`.

`VERIFIED_REMOVED` means the instance is gone or terminated and no disk name still contains it. `UNINSTALL_VERIFIED` is the loader's stdout word. Neither one is `live_enforcement=PROVEN`.

A red proof job deletes the VM it created, or the named VM on `reboot-post`. Zach still runs verify-removed. The guest shutdown timer is not verify-removed. The sweeper switch stays false, so nothing else deletes the disk.

The concurrency group is `vantio-gce-slot`. A VM left up blocks the next lab create until teardown.

## What a green run does not prove

- It does not attach the word PROVEN. The evidence line stays `live_enforcement=NOT_PROVEN`.
- `reboot_restored` stays `NOT_RUN`.
- An offline pass of this repository does not show a new boot id, a ledger row, or that a VM was created or removed.
- `uninstall=REFUSED_NOT_ENROLLED` means compare's SIGINT detach left the host unenrolled. It is not `UNINSTALL_VERIFIED`.
- `license_exp_claim=NOT_PROVEN` and `license_exp_observation=NOT_CONSULTED` are the expected observation on this tip. They are not a license refusal.
- The workflow does not run `scripts/lab_webshell_battery.py`.

Pass and fail lines for council are in the Phantom Engine packet and in `$VANTIO_LAB_DIR/transcript.txt` for the phase that just ran. Each invocation truncates that transcript. The workflow stores each phase log under the proof artifact `gcp-lab-enforcement-proof-<run_id>`.

## Before the first click

1. This file is on `main`. A branch dispatch fails the main guard. This pull request does not merge and does not dispatch.
2. The workload identity provider attribute condition includes `vantioai/vantio-open-core/.github/workflows/gcp-lab-enforcement-proof.yml@refs/heads/main`. The full string is `python3 scripts/gcp/lab_auto.py attribute-condition`. Updating that provider is not an Actions dispatch. Until it is updated, authentication fails and no VM is created.
3. `W3_LAB_PRIVATE_BUNDLE_TOKEN` can read `vantioai/vantio-phantom-engine` at the pinned commit. The build job uses it in environment `w3-lab-auto`. If it cannot, the build fails before create.
