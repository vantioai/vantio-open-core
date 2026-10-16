# Stranger-host standard

UTC: 2026-10-16T15:47:41Z

Label: **Roadmap**. Tier written into every bundle: `UNSET`.

This is the pass criteria for one outside run: preflight, seal, enforcement, loader, descendants, reboot, descendants again, uninstall, teardown. The commands reuse the comparison plan from 2026-10-16 and the lab rules at main `69671e97fa359b685232ec7dd4e9fb4badc7be57`.

A bundle passes when all nine steps are `PASS`. A passing bundle is still waiting for an outside review. It is not `STRANGER_HOST_PROVED`.

The operator entry is:

```bash
scripts/gap/t1-stranger-host/preflight.sh --image-name <exact-image> --out host-record.json
```

The other commands are `python3 scripts/gap/t1-stranger-host/stranger_host.py` with `capture-boot`, `capture-uninstall`, `assemble`, `grade`, `sign`, and `verify`.

The battery itself stays the handover `enterprise-rows.sh`. Run it only on a dedicated test VM. It switches apt to offline mode, adds a swapfile when the host has none, and rewrites the docker daemon config. A clean customer installer is not what the lab validated.

## Shared rules

- Boot id: one line, 1 to 80 characters, no newline.
- BPF in an LSM list: a comma-separated token whose text is `bpf`.
- BPF on a cmdline: an `lsm=` word whose value contains that token.
- Lockdown continues only for bracketed `none` or `integrity`.
- Exact image: an `ami-` id (8 to 17 hex digits), a name containing `-v20` plus six digits, or an operator attestation that matches `^[A-Za-z0-9][A-Za-z0-9_.:/-]{7,159}$` and is not `ubuntu-os-cloud/ubuntu-2404-lts-amd64`.
- Evidence members are at most 2_000_000 bytes.
- `programs_not_removed` is an annotation, `harness_fault_candidate`, when the independent uninstall listing is empty. It is not a product pass by itself.

## Step 1 — Preflight

Stops on the first failure. Exit 1 prints `PREFLIGHT_FAIL <reason>`. Exit 0 prints `PREFLIGHT_OK` and writes the host record.

| Order | Reason | Pass condition |
| --- | --- | --- |
| 1 | `bpf_lsm_inactive` | `/sys/kernel/security/lsm` contains a `bpf` token |
| 2 | `btf_missing` | `/sys/kernel/btf/vmlinux` exists and its size is greater than 0 |
| 3 | `cgroup_v2_missing` | `stat -fc %T /sys/fs/cgroup` is `cgroup2fs` |
| 4 | `lockdown_unreadable` | `/sys/kernel/security/lockdown` is exactly `none`, `integrity`, and `confidentiality`, with one mode in brackets |
| 5 | `lockdown_confidentiality` | the bracketed mode is `none` or `integrity` |
| 6 | `bpffs_missing` | `/proc/mounts` has fstype `bpf` on `/sys/fs/bpf` |
| 7 | `image_exact_missing` | an exact image was recorded |
| 8 | `boot_id` | the boot id is one line of 1 to 80 characters |

The host record includes `boot_id`, `uname_release`, `uname_version`, `cmdline`, `enabled_lsm`, `lockdown_raw`, `lockdown_mode`, `cgroup_fstype`, `bpffs`, `btf_bytes`, and `image` (`exact`, `source`, `supplemental`). Supplemental os-release text does not satisfy the exact-image check.

Link-local metadata is read only with `--allow-metadata`. The default is off.

## Step 2 — Seal

The operator runs `sha256sum -c` on `seal.oci.tar` with the digest they were handed.

| Reason | When it fails |
| --- | --- |
| `seal_file_missing` | `seal.oci.tar` is absent from the recorded checksum input |
| `seal_digest_malformed` | the handover digest is not 64 lowercase hex characters |
| `seal_is_public_pin` | the digest is `e0b19d557891b1ee8bbd20e702df11669d175e4083ef5bbe2f7077cf30093b5e` |
| `seal_is_plumbing_only` | the digest is `f882dd81297b02c11c55d9df69f00d9fffa710d1a87d36066a5645922804d753` |
| `seal_is_tracking` | the digest is `16c9e5638c169e5fdd3fd7291b3225a809b18abfe464d717c2d31a398d5bda6a` |
| `seal_bytes_mismatch` | the file digest differs from the handover digest |

PASS records `sha256sum` as `seal.oci.tar: OK`. `working_seal` is true only for `bbb1025d9303e0c43e435f416772614a04ac5cc0e7e31c30ad43d7a403b2085d`. The comparison digest `6d3ce580ffb5d52fa0bfb70bdee28409fa6282f86737011e3d85c1093f5ea403` may pass this step with `working_seal` false and `comparison_seal` true. Any other well-formed handover digest may pass with both flags false. Passing step 2 does not make that digest the working seal.

## Step 3 — Enforcement

Grade `rows-enterprise.json`. The ceiling path is `/var/lib/vantio-pe-clean-host/d/secret`. The enrolled uid is `65534`.

PASS requires all of:

- `grant_loader.rc` is the integer 0, `grant_loader.audit` is true, `grant_loader.path_observe` is true
- `grant_probe.nobody_errno` is 0
- `unchanged.conflict_reason` is `VERSION_CONFLICT`
- `unchanged.generation` and `unchanged.generation_before` are both integers and they are equal
- unchanged probe is `open_ok` (`unchanged.probe`, `unchanged.probe.result`, or `unchanged.result`)
- `freeze.widen_reason` is `FROZEN`
- `unreachable.reason` is `ENTERPRISE_UNREACHABLE`
- `revoke.probe.nobody_errno` is 13
- `revoke.probe.path` or the rows `path` is the ceiling path
- `revoke.probe.uid` or the rows `uid` is 65534
- `revoke.block_event` has `ActionTaken` `DENIED`, integer `Pid` greater than 0, and integer `lineage_anchor` greater than 0
- `fail_reasons` is absent, empty, or the single entry `programs_not_removed`

Any other `fail_reasons` entry fails as `fail_reasons`. A lone `programs_not_removed` annotates `harness_fault_candidate` and leaves step 3 eligible to pass.

## Step 4 — Loader kill and restart

These fields live on the enterprise rows or on `loader` inside that file:

- `loader_kill` is `held`
- `loader_restart` is `held`
- `deny_attr_post_kill` is true

The lab runner fills the two words from the `2d-crash-recovery` and `2c-upgrade-rollback` batteries. The operator copies those words into the rows they assemble. This package does not launch those batteries.

## Step 5 — Descendants, pre-reboot

Grade the `pre` object in `rows-descendant-pre.json`.

Deny cases, each `pass` true, not skipped, `file_errno` 13, `net_errno` 1:

`moved`, `clone3`, `reparent`, `double_fork`, `setsid`, `unshare`, `setns`, `vfork`, `ancestor_8`

Allow cases, each `pass` true, not skipped, `file_errno` 0:

`ancestor_9`, `unenrolled`

`failed_cases` is an empty list. `pre.boot_id` equals the step 1 boot id, and that id is well formed. Each case name appears once. `skipped` is absent or false. Any other skipped value fails.

## Step 6 — Reboot

The operator reboots with the handover method (the lab drop-in is `lsm=lockdown,capability,landlock,yama,apparmor,ima,evm,bpf` when they choose it) and reconnects. On the new boot, before saving the hypervisor serial, they mark the console with this boot id:

```bash
echo "VANTIO_BOOT_MARK=$(cat /proc/sys/kernel/random/boot_id)" | sudo tee /dev/kmsg >/dev/null
```

Then:

```bash
python3 scripts/gap/t1-stranger-host/stranger_host.py capture-boot \
  --serial-file <hypervisor-serial.txt> --out boot-evidence.json
```

PASS requires:

- `boot_id` well formed and different from step 1 (`boot_id_unchanged` otherwise)
- live cmdline has a `bpf` LSM token (`cmdline_bpf_missing`)
- live `/sys/kernel/security/lsm` has a `bpf` token (`lsm_bpf_missing`)
- `serial_log` is non-empty and at most 2_000_000 bytes (`serial_missing`, `serial_too_large`)
- `serial_sha256` is present and matches that text (`serial_boot_mismatch` when it is missing or different)
- `serial_boot_id` equals `boot_id`, and the serial text contains that boot id (`serial_boot_mismatch`)
- the serial text contains the cmdline's `lsm=` word (`serial_lsm_missing`)

## Step 7 — Enforcement returns on the new boot

The operator runs `enterprise-rows.sh <seal> descendant-b1 post` with no extra loader start. Grade `rows-descendant-post.json`.

PASS requires `reboot_observed` true, `post.boot_id` equal to the step 6 boot id, `post.boot_id` different from `pre.boot_id`, and the same case rules as step 5 on `post`. A rows boot id that is not the live capture fails as `stale_rows`.

## Step 8 — Uninstall

The operator runs `enterprise-rows.sh <seal> uninstall` on the GCP guest script. Then:

```bash
python3 scripts/gap/t1-stranger-host/stranger_host.py capture-uninstall \
  --uninstall-out /tmp/vantio-uninstall.out --live --out uninstall.json
```

`--live` runs `bpftool prog show` and lists `/sys/fs/bpf` names. Fixture runs pass those texts as files.

`uninstall.json` stores `uninstall_transcript`, `bpftool_text`, `pin_listing`, the derived lists, `listing_source` (`live` or `operator-file`), and `status`. The grade recomputes the line and the lists from those texts. A boolean or a list that disagrees with the text fails.

`status` is `VERIFIED_REMOVED` only when all three hold:

- `uninstall_transcript` has a line whose entire text is `UNINSTALL_VERIFIED`, and `uninstall_verified_line` is true
- `bpftool_text` is present and its vantio lines are an empty list that matches `bpftool_vantio_lines`
- `pin_listing` is present and its vantio names are an empty list that matches `bpffs_vantio_names`

A missing list fails (`bpftool_missing` or `bpffs_pins_missing`). A non-empty list fails (`bpftool_vantio_present` or `bpffs_vantio_present`). Any other outcome is `NOT_REMOVED`.

When `fail_reasons` contains `programs_not_removed` and `status` is `VERIFIED_REMOVED`, the step records `harness_fault_candidate`. The GCP guest at this base can emit that guest flag because the #300 recorder fix is on the AWS script only.

## Step 9 — Teardown

The operator deletes the VM in their own project, or restores `*.vantio-offline` apt sources, removes `/etc/apt/apt.conf.d/99vantio-offline`, and removes the swapfile. They record `teardown.json`:

- `actor` is `outside_operator`
- `project_touched_by_vantio` is false
- `vantio_ran_teardown` is false
- either `vm_deleted` is true, or `apt_sources_restored`, `offline_conf_removed`, and `swapfile_removed` are all true

This package does not delete a VM.

## Grade output

`grade` writes one object per step: `step`, `result` (`PASS` or `FAIL`), `reasons`, and `notes`. The bundle result is `PASS` only when every step is `PASS`. `host_proof` stays false in this package's own output. `verify` sets `host_proof` true only for a signature claim `AWAITING_OUTSIDE_REVIEW` whose trust document is the pinned TEST key and whose fresh grade is `PASS`. That still leaves the tier `UNSET`.
