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
| Git tip | the one line in `scripts/gcp/pe-pin.txt` |
| Lab directory | `/var/lib/vantio-enforcement-proof` |

`gcp-lab-provision.yml` is the wrong path. Its `seal` input is 64 hex. This tip is 40 hex and is not a seal. Do not type the tip into that workflow.

The tip moves by editing `scripts/gcp/pe-pin.txt` and the workflow input default so the two lines match. Point `build_pe_loader.sh` at the new tree. A directory with no `.git` is accepted when the pin argument matches that file. A git checkout must be clean and `HEAD` must equal the pin. The pin is not a loader hash.

## Dispatch inputs

Zach clicks **GCP lab enforcement proof** on `main`.

| Input | What to enter |
| --- | --- |
| `pe_git_sha` | The line in `scripts/gcp/pe-pin.txt`. The workflow default is that line. Any other value fails before a VM. |
| `run_go` | Zach's own-words run go. The log masks it and does not print it. |
| `host_name` | The guest `hostname -s` Zach allows, 3 to 40 lowercase letters, digits, and hyphens. The workflow sets `VANTIO_LAB_HOST` and `VANTIO_LAB_HOST_ALLOWLIST` to that one name. It is masked. |
| `proof_slice` | `full` (default), `reboot-pre`, or `reboot-post`. |
| `instance_name` | Empty, except `reboot-post`. Then paste the `vantio-gcp-lab-` name from the earlier run. |
| `stop_after_minutes` | `120` for `full`. Allowed range is 90 through 120. |
| `uninstall_approval` | Empty unless Zach is supplying `VANTIO_LAB_UNINSTALL_APPROVAL`. Empty is not printed. The script then records `uninstall=NOT_RUN_NO_APPROVAL` when the host is enrolled, or `uninstall=REFUSED_NOT_ENROLLED` when it is not. |

The runner reaches the guest with the existing IAP helper: `gcloud compute ssh`, `--tunnel-through-iap`, `--project=vantio-lab-oct08`, `--zone=us-central1-a`, OS Login key expiry one hour. There is no laptop login in this workflow. The IAP command is `sudo bash /var/lib/vantio-lab/guest/run-proof-phase.sh PHASE`. The run go stays in a mode `0600` file on the guest, not in that command.

## Cost gate

The `gate` job calls `.github/workflows/gcp-lab-cost-gate.yml`. The proof job starts only when that job's output `expected_oop_usd` is `0`. A gate that exits 2 skips create. There is no VM to use. A green gate does not itself install Phantom Engine.

The guest proof and the failure delete are a second call of that same file, with `proof_slice` set. Workload identity sees `job_workflow_ref` `vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@refs/heads/main`. That call does not run the gate job again. The proof step still runs `scripts/gcp/lab_auto.py cost-gate` and reads that JSON before create.

## What `full` runs

Build happens on the runner, inside an `ubuntu:24.04` container, from the pinned commit. Cargo's workdir is the `phantom-engine` checkout. The e2-micro guest does not compile. The packet does not raise the machine cap. The binary is copied over IAP. Its sha256 is recorded in the proof JSON. The packet's build-host object `a7cd5f19e83a715aac37dd7b8e2b00538b11f911e98c194854d0273bbbfc5cf6` is that other machine's hash, not a seal this workflow requires. `bpf-linker` is pinned to `0.12.0`. Rust is the dated `channel` in the checkout's `rust-toolchain.toml` when that line is `nightly-YYYY-MM-DD`. A missing file, or a channel that is only `nightly`, keeps `nightly-2026-10-13`. The build sets `SOURCE_DATE_EPOCH=0` and `RUSTFLAGS` `--remap-path-prefix` for the checkout (`/vantio-src`), the cargo home (`/cargo`), and the rustc sysroot (`/rustc`). Those are the same prefixes `vantio-loader/build.rs` uses for the embedded eBPF object. `CFLAGS` and `CXXFLAGS` set `-ffile-prefix-map` for the same three paths, because `ring` compiles C and assembly and `RUSTFLAGS` do not rewrite those `.file` paths. Cargo's target directory is the checkout's `target`, which is the writable mount, so it sits under the checkout prefix. `profile.release` already sets `trim-paths = "all"`. The red-team note's loader digest is two builds on that host. It says formal reproducibility is not claimed. A container build can still differ because `ring` keeps the system compiler's include path.

`full` runs these guest phases in this order: compare, root-detach, signals, file-deny, fork-inherit, unix-socket, ptrace-deny, inbound, bpffs-overmount, af-packet, stop-token, pin-absent, missing-path, host-wide, hard-link, enrolled-root, nonce-truncate, ledger-forgery, ptrace-task, host-enroll, same-boundary, oom, escapes, clock, k8s, vlan, reboot-pre, reboot, reboot-post, compare, expired-key, uninstall.

The second `compare` is after `reboot-post` and before `expired-key` and `uninstall`. Tip `48c95504` binds `expired-key` and `uninstall` to the current boot through `require_compare_pass`. The Phantom Engine packet lists those two phases after `reboot-post` and notes that they exit 2 with `phase_order=compare_required` until `compare.result` is `status=PASS` for the current boot id. This slice runs that post-reboot `compare` so those phases can run. Before that second compare, the first boot's lab directory is copied to `/var/lib/vantio-enforcement-proof-pre-reboot`.

1. `compare` on the boot that was just installed.
2. `root-detach` on that same boot. As root, outside the loader, the guest runs the loader canaries for program detach, link detach, map update, pin unlink, and pin rename. The phase passes only when every canary returns errno 1, the programs and pins are still present, and an enrolled connect is still blocked with a `NETWORK_BLOCK` row, `DropPath` `cgroup_skb`, and `BytesSevered` equal to the full packet length. Errno 13, a successful detach, and an inactive BPF LSM are failures.
3. `file-deny` on that same boot.
4. `reboot-pre` on that same boot. The script records state and does not reboot.
5. Reboot. The workflow masks `google-shutdown-scripts.service`, then schedules `systemctl reboot --force`. A plain `reboot` on this network does not have to reach a new boot.
6. `reboot-post` on the new boot. A new boot id is required, and enforcement has to be applied again. `reboot_restored=NOT_RUN` is not a pass. The enrolled connect on that boot has to be blocked.
7. `compare` on the new boot.
8. `expired-key` on the new boot.
9. `uninstall` on the new boot. That phase runs `uninstall-negative` itself when the host is enrolled.

Stop on the first phase that is not an accepted observation. `compare=REFUSED_LSM` stops the run. A stock Ubuntu 24.04 image can omit `bpf` from `/sys/kernel/security/lsm`. This workflow does not edit the kernel command line.

`reboot-pre` is the first dispatch when one job should not span the reboot. It runs compare, root-detach, file-deny, reboot-pre, and the forced reboot, then leaves the VM up. `reboot-post` is the second dispatch on that same instance name. It runs reboot-post, compare, expired-key, and uninstall. Dispatch it before `stop_after_minutes` halts the guest.

## Close-out

A green proof job does not delete the VM. Zach records `instance_name` from the proof JSON (`vantio-gcp-lab-` plus the run id, unless the slice is `reboot-post`). Then:

1. **GCP lab teardown**. Input `instance_name` with that name. File `.github/workflows/gcp-lab-teardown.yml`.
2. **GCP lab verify removed**. Same `instance_name`. File `.github/workflows/gcp-lab-verify-removed.yml`. Pass line is `VERIFIED_REMOVED`.

`VERIFIED_REMOVED` means the instance is gone or terminated and no disk name still contains it. `UNINSTALL_VERIFIED` is the loader's stdout word. Neither one is `live_enforcement=PROVEN`.

A red proof job deletes the VM it created, or the named VM on `reboot-post`. Zach still runs verify-removed. The guest shutdown timer is not verify-removed. The sweeper switch stays false, so nothing else deletes the disk.

The concurrency group is `vantio-gce-slot`. A VM left up blocks the next lab create until teardown.

## What a green run does not prove

- It does not attach the word PROVEN. The evidence line stays `live_enforcement=NOT_PROVEN`.
- `reboot_restored=NOT_RUN` is not a pass. The post-reboot phase has to block an enrolled connect on the new boot id.
- An offline pass of this repository does not show a new boot id, a ledger row, or that a VM was created or removed.
- `uninstall=REFUSED_NOT_ENROLLED` means the host is not enrolled after the signed stop. It is not `UNINSTALL_VERIFIED`.
- `license_exp_claim=NOT_PROVEN` fails the `expired-key` phase. It is not an accepted observation. `license_exp_claim=REFUSED` with `license_exp_observation=REFUSED` is the line that means the loader refused an expired signature.
- `compare=PASS` is accepted only when the enrolled connect times out or returns errno 1, the outside connect succeeds, an nft, iptables, or tcpdump counter confirms the drop, and the ledger row is `NETWORK_BLOCK` with `DropPath` `cgroup_skb` and `BytesSevered` equal to the full packet, headers included. A `CGROUP_BLOCK` row does not pass. A length equal to the payload alone does not pass. The loader ndjson is not the counter.
- `file-deny` passes only when the enrolled open returns errno 13 and the outside open returns 0.
- `reboot-post` passes only when the boot id changed.
- `fork-inherit` passes when the parent, the fork child, the grandchild, and the clone3 child are blocked, an outsider connects, and every `NETWORK_BLOCK` row shares one positive `lineage_anchor` with `DropPath` `cgroup_skb` and a non-zero `TraceId`. Different `TraceId` values are that field's `0xA110000000000000 | tgid` form. They are not a failed anchor.
- Teardown of an enforcing loader is a signed stop token from a per-run `dev-nonprod-lab-` key. Signals do not detach. `live_enforcement` stays `NOT_PROVEN`.
- The workflow does not run `scripts/lab_webshell_battery.py`.

Pass and fail lines for council are in the Phantom Engine packet and in `$VANTIO_LAB_DIR/transcript.txt` for the phase that just ran. Each invocation truncates that transcript. The workflow stores each phase log under the proof artifact `gcp-lab-enforcement-proof-<run_id>`.

## Before the first click

1. This file is on `main`. A branch dispatch fails the main guard. This pull request does not merge and does not dispatch.
2. The guest jobs authenticate from `.github/workflows/gcp-lab-cost-gate.yml`. The live provider already allows `vantioai/vantio-open-core/.github/workflows/gcp-lab-cost-gate.yml@refs/heads/main`. Zach does not add `gcp-lab-enforcement-proof.yml` for this dispatch. `python3 scripts/gcp/lab_auto.py attribute-condition` still prints a clause for that file. That clause is not required to authenticate the guest jobs.
3. `W3_LAB_PRIVATE_BUNDLE_TOKEN` can read `vantioai/vantio-phantom-engine` at the pinned commit. The build job uses it in environment `w3-lab-auto`. If it cannot, the build fails before create.
